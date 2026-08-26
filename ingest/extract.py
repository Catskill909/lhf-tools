#!/usr/bin/env python3
"""
Labor Heritage Media Archive — AI extraction (Tier 2). The one AI step.

Everything else in this pipeline reads structure the producers already made.
This reads the words themselves, because three things in the original brief
are simply not written down anywhere:

  1. Topics      — show notes describe an episode, they don't classify it.
  2. Guests      — the producers hyperlink most guests, but not all. The
                   unlinked ones are invisible to enrich.py.
  3. Interviewer — who was actually asking the questions this week.

Deliberately NOT a replacement for enrich.py. The hyperlinks it found are
hand-curated ground truth and win on conflict; they're also fed to the model
as hints so it spells names the way the producers do.

    python3 ingest/extract.py --dry-run     # build the batch, cost it, send nothing
    python3 ingest/extract.py               # submit, wait, collect, build
    python3 ingest/extract.py --rebuild     # re-derive tables from stored output

DEV-ONLY DEPENDENCY. This is the one file in the project that isn't stdlib —
it needs `pip install anthropic` and an API key. It runs offline, on demand,
against the database; the server and the container never import it and stay
dependency-free. Nothing downstream can tell how a topic got there.

Cost: the archive is ~1.2M tokens of transcript. Batched, that's a few dollars
once. Re-runs off stored output are free.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))
BATCH_STATE = os.path.join(ROOT, "data", "extract-batch.json")

MODEL = "claude-opus-5"

# Bumped whenever the prompt or schema changes. Stored per row so a partial
# re-run can tell which episodes were done under which prompt.
PROMPT_VERSION = "topics-v1"

# Transcripts run to ~10k words. Past a point more text doesn't sharpen the
# topics, it just costs money, so long ones are sampled head/middle/tail
# rather than truncated — the guest is introduced at the top and thanked at
# the bottom, and truncation would throw the second one away.
MAX_TRANSCRIPT_WORDS = 9000

# ---------------------------------------------------------------- vocabulary
#
# Seeded, not free-form. Asked to invent topics from scratch across 200
# episodes, a model produces "unions", "labor unions" and "unionization" as
# three separate topics — the exact duplication the normalized_name key was
# put in the schema to prevent. A fixed list it must prefer collapses that at
# source, and costs nothing extra because it rides in the cached prefix.
#
# It is allowed to coin terms when nothing here fits (see NEW_TOPIC_LIMIT) —
# a closed list would quietly file everything unusual under the nearest
# wrong heading, which is worse than an untidy vocabulary.
TAXONOMY = [
    # what happened
    "Strikes and picket lines", "Union organizing", "Collective bargaining",
    "Contract negotiations", "Labor law and the NLRB", "Union democracy",
    "Solidarity actions", "Workplace safety", "Wages and inequality",
    "Layoffs and plant closures", "Immigration and migrant labor",
    "Technology and automation", "Public sector unions", "Healthcare and benefits",
    "Education and teachers", "Transportation and logistics",
    "Building trades and construction", "Service and hospitality work",
    "Agriculture and farmworkers", "Mining and extraction",
    "Media and journalism", "Arts and entertainment unions",
    # who
    "Women in the labor movement", "Race and labor", "LGBTQ workers",
    "Youth and student organizing", "Disability and work",
    "Retirees and pensions", "International labor solidarity",
    # how it's told
    "Labor history", "Labor music and song", "Poetry and spoken word",
    "Film and documentary", "Books and authors", "Theater and performance",
    "Museums and archives", "Labor education", "Oral history",
    "Commemoration and anniversaries", "Awards and tributes", "Obituaries",
    # politics
    "Elections and politics", "Legislation and policy", "Civil rights",
    "Economic justice", "Climate and environment", "War and peace",
]

NEW_TOPIC_LIMIT = 2

SYSTEM_PROMPT = f"""\
You are cataloguing a public radio archive for the Labor Heritage Foundation.
Two weekly shows: The Labor Heritage Power Hour and Labor History Today. The
catalogue is used by producers deciding what to re-air and by researchers
looking for coverage of a subject.

For each episode you are given the show notes and, usually, a machine-made
transcript. Return the topics it covers, and the people in it.

TOPICS
Between two and five. Prefer terms from this list, exactly as spelled:

{chr(10).join('  ' + t for t in TAXONOMY)}

Coin a new topic only when nothing on the list fits, at most {NEW_TOPIC_LIMIT}
per episode, phrased in the same style (sentence case, plural nouns, no
abbreviations). Topics describe what the episode is ABOUT, not what gets
mentioned in passing — a song played between segments is not a topic.

PEOPLE
Everyone who speaks or is substantially discussed, with their role:

  host        — presents the programme week to week
  interviewer — asks the questions in this episode; often but not always the
                host, and there may be more than one
  guest       — interviewed or featured in this episode
  mentioned   — discussed substantially but not present

Give the fullest form of each name that appears, spelled as in the show notes
where the notes and the transcript disagree. The transcripts are machine-made
and mangle names — if a name appears only in the transcript and you are not
confident of the spelling, mark its confidence low rather than guessing.
Omit people who are only named in passing.

Do not include people who appear solely in boilerplate: network credits,
sponsors, or the sign-off read at the end of every episode.

SUMMARY
One sentence, under 25 words, saying what the episode is. No preamble.

Base everything on the material given. An empty list is a correct answer when
the material does not support one; do not infer a guest from a topic, or a
topic from a name."""

SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
        },
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": ["host", "interviewer", "guest", "mentioned"],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": ["name", "role", "confidence"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["topics", "people", "summary"],
    "additionalProperties": False,
}

CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}


# ---------------------------------------------------------------- schema

DDL = """
-- Raw model output, one row per episode. The point of keeping it is that
-- parsing is free and the API call is not: a better prompt means re-running
-- the API, but a better *parser* means --rebuild, which costs nothing.
CREATE TABLE IF NOT EXISTS extractions (
    episode_id     INTEGER PRIMARY KEY REFERENCES episodes(id) ON DELETE CASCADE,
    model          TEXT,
    prompt_version TEXT,
    raw_json       TEXT NOT NULL,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_episode_topics_topic  ON episode_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_episode_people_person ON episode_people(person_id);
"""


def connect():
    if not os.path.exists(DB_PATH):
        sys.exit(f"No database at {DB_PATH}\nRun:  python3 refresh.py")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn):
    conn.executescript(DDL)
    conn.commit()


# ---------------------------------------------------------------- normalising

HONORIFICS = r"(?:dr|mr|mrs|ms|prof|professor|rev|sen|senator|rep|hon)"


def norm_person(name):
    """
    The dedup hook from schema.sql, implemented. "Dr. Jeffrey Johnson",
    "Jeffrey Johnson" and "jeff  johnson " must land on one record, or the
    catalogue lists the same guest three times and the counts are all wrong.
    """
    t = (name or "").replace("’", "'").strip()
    t = re.sub(rf"^{HONORIFICS}\.?\s+", "", t, flags=re.I)
    t = re.sub(r"\s*,\s*(jr|sr|ph\.?d|m\.?d|esq)\.?$", "", t, flags=re.I)
    t = re.sub(r"[^\w\s'-]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def norm_topic(name):
    t = (name or "").replace("’", "'").strip()
    t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.I)
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def looks_like_person(name):
    """
    Cheap guard against the model filing an organisation, a book or a headline
    under people. The producers' hyperlinks are fed in as spelling hints and
    they mix guests with films, books and museums, so this is the failure mode
    to expect — and a wrong person record is worse than a missing one, because
    it shows up in the guest list as if someone verified it.

    Deliberately conservative rather than clever: anything questionable is
    dropped, and the mentions table still carries it as a tag either way.
    """
    n = (name or "").strip()
    if not (3 <= len(n) <= 60):
        return False
    if not re.search(r"[A-Za-z]", n):
        return False
    # Quotes and terminal punctuation mark a title, not a name.
    if re.search(r"[\"“”:;?!]|\.\.\.|…", n):
        return False
    # Real names run one to five tokens ("Martin Luther King Jr"); a longer
    # string is a headline that arrived with a person's role attached.
    if len(n.split()) > 5:
        return False
    # Corporate and organisational suffixes — the mentions table handles these
    # better anyway, because a human chose to link them.
    if re.search(r"\b(inc|llc|ltd|union|local\s*\d+|afl|cio|council|federation"
                 r"|museum|press|podcast|festival|foundation|institute"
                 r"|committee|association|society|project)\b", n, re.I):
        return False
    return True


# ---------------------------------------------------------------- input build

def sample_words(text, limit):
    """Head, middle and tail rather than a straight truncation — see above."""
    words = (text or "").split()
    if len(words) <= limit:
        return " ".join(words)
    head = limit // 2
    tail = limit // 4
    mid = limit - head - tail
    m0 = (len(words) - mid) // 2
    return (
        " ".join(words[:head])
        + "\n\n[…]\n\n" + " ".join(words[m0:m0 + mid])
        + "\n\n[…]\n\n" + " ".join(words[-tail:])
    )


def build_user_content(conn, ep):
    """One episode's material, in the order the model should weigh it."""
    hints = [
        r["text"] for r in conn.execute(
            """SELECT DISTINCT text FROM mentions
               WHERE episode_id = ? AND is_boilerplate = 0
               ORDER BY text""", (ep["id"],))
    ]

    parts = [
        f"SHOW: {ep['show_name']}",
        f"TITLE: {ep['title']}",
        f"PUBLISHED: {(ep['published_at'] or '')[:10]}",
        "",
        "SHOW NOTES:",
        (ep["description_text"] or "").strip() or "(none)",
    ]

    if hints:
        parts += [
            "",
            "NAMES THE PRODUCERS HYPERLINKED IN THE NOTES "
            "(hand-curated, spelled correctly — prefer these spellings, and "
            "note that some are organisations or books rather than people):",
            "; ".join(hints),
        ]

    tx = (ep["transcript_text"] or "").strip()
    if tx:
        parts += ["", "TRANSCRIPT (machine-made, names may be mangled):",
                  sample_words(tx, MAX_TRANSCRIPT_WORDS)]
    else:
        parts += ["", "TRANSCRIPT: none published for this episode. "
                  "Work from the show notes alone and be correspondingly "
                  "cautious about people."]

    return "\n".join(parts)


def pending_episodes(conn, redo=False, limit=None):
    sql = """SELECT e.id, e.title, e.published_at, e.description_text,
                    e.transcript_text, s.name AS show_name
             FROM episodes e JOIN shows s ON s.id = e.show_id"""
    if not redo:
        sql += """ WHERE e.id NOT IN (SELECT episode_id FROM extractions
                                      WHERE prompt_version = ?)"""
        params = (PROMPT_VERSION,)
    else:
        params = ()
    sql += " ORDER BY e.published_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql, params).fetchall()


def build_requests(conn, episodes, effort, max_tokens):
    """
    The batch payload. The system prompt is identical across every request and
    carries the whole taxonomy, so it gets a cache breakpoint — it's the same
    ~1.5k tokens 200 times over.
    """
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    out = []
    for ep in episodes:
        out.append(Request(
            custom_id=f"ep-{ep['id']}",
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=max_tokens,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": SCHEMA},
                },
                messages=[{"role": "user",
                           "content": build_user_content(conn, ep)}],
            ),
        ))
    return out


# ---------------------------------------------------------------- API steps

def client():
    try:
        import anthropic
    except ImportError:
        sys.exit(
            "This step needs the Anthropic SDK, the one dependency in the "
            "project:\n"
            "    pip install anthropic\n"
            "It is used here only. The server and the container stay stdlib-only."
        )
    return anthropic.Anthropic()


def submit(conn, episodes, effort, max_tokens):
    reqs = build_requests(conn, episodes, effort, max_tokens)
    batch = client().messages.batches.create(requests=reqs)
    with open(BATCH_STATE, "w") as fh:
        json.dump({"id": batch.id, "episodes": len(reqs),
                   "prompt_version": PROMPT_VERSION}, fh)
    print(f"  submitted {len(reqs)} episodes as {batch.id}")
    print(f"  state written to {os.path.relpath(BATCH_STATE, ROOT)}")
    return batch.id


def wait(batch_id, poll=30):
    c = client()
    while True:
        b = c.messages.batches.retrieve(batch_id)
        counts = b.request_counts
        if b.processing_status == "ended":
            print(f"  done — {counts.succeeded} succeeded, {counts.errored} errored")
            return b
        print(f"  {b.processing_status}: {counts.processing} processing, "
              f"{counts.succeeded} done", flush=True)
        time.sleep(poll)


def collect(conn, batch_id):
    """Results arrive in any order — key on custom_id, never on position."""
    stored = errors = 0
    for result in client().messages.batches.results(batch_id):
        ep_id = int(result.custom_id.split("-", 1)[1])
        if result.result.type != "succeeded":
            errors += 1
            detail = getattr(result.result, "error", None)
            print(f"  ! episode {ep_id}: {result.result.type} "
                  f"{getattr(detail, 'type', '')}")
            continue

        msg = result.result.message
        if msg.stop_reason == "refusal":
            errors += 1
            print(f"  ! episode {ep_id}: refused")
            continue

        text = next((b.text for b in msg.content if b.type == "text"), None)
        if not text:
            errors += 1
            print(f"  ! episode {ep_id}: no text block "
                  f"(stop_reason={msg.stop_reason})")
            continue

        conn.execute(
            """INSERT INTO extractions (episode_id, model, prompt_version, raw_json)
               VALUES (?,?,?,?)
               ON CONFLICT(episode_id) DO UPDATE SET
                 model=excluded.model, prompt_version=excluded.prompt_version,
                 raw_json=excluded.raw_json, created_at=datetime('now')""",
            (ep_id, MODEL, PROMPT_VERSION, text))
        stored += 1
    conn.commit()
    return stored, errors


# ---------------------------------------------------------------- build tables

def build_tables(conn):
    """
    Turn stored model output into the topics/people tables. Pure local work —
    no API, no key. This is what --rebuild re-runs when the parsing changes.
    """
    conn.execute("DELETE FROM episode_topics")
    conn.execute("DELETE FROM episode_people")
    conn.execute("DELETE FROM topics")
    conn.execute("DELETE FROM people")

    # Producer hyperlinks are ground truth; a name they linked keeps their
    # spelling even if the model wrote it differently.
    canonical = {}
    for r in conn.execute(
        "SELECT DISTINCT text FROM mentions WHERE is_boilerplate = 0"
    ):
        canonical.setdefault(norm_person(r["text"]), r["text"])

    topic_ids, person_ids = {}, {}
    bad_json = 0

    for row in conn.execute("SELECT episode_id, raw_json FROM extractions"):
        try:
            data = json.loads(row["raw_json"])
        except json.JSONDecodeError:
            bad_json += 1
            continue

        seen_t = set()
        for name in data.get("topics") or []:
            n = norm_topic(name)
            if not n or len(n) < 3 or n in seen_t:
                continue
            seen_t.add(n)
            if n not in topic_ids:
                cur = conn.execute(
                    "INSERT INTO topics (name, normalized_name) VALUES (?,?)",
                    (name.strip(), n))
                topic_ids[n] = cur.lastrowid
            conn.execute(
                "INSERT OR IGNORE INTO episode_topics (episode_id, topic_id, confidence)"
                " VALUES (?,?,?)", (row["episode_id"], topic_ids[n], 1.0))

        seen_p = set()
        for entry in data.get("people") or []:
            raw = (entry or {}).get("name") or ""
            role = (entry or {}).get("role") or "guest"
            if not looks_like_person(raw):
                continue
            n = norm_person(raw)
            if not n or (n, role) in seen_p:
                continue
            seen_p.add((n, role))
            display = canonical.get(n, raw.strip())
            if n not in person_ids:
                cur = conn.execute(
                    "INSERT INTO people (name, normalized_name) VALUES (?,?)",
                    (display, n))
                person_ids[n] = cur.lastrowid
            conn.execute(
                "INSERT OR IGNORE INTO episode_people "
                "(episode_id, person_id, role, confidence) VALUES (?,?,?,?)",
                (row["episode_id"], person_ids[n], role,
                 CONFIDENCE.get((entry or {}).get("confidence"), 0.6)))

    conn.commit()
    return len(topic_ids), len(person_ids), bad_json


# ---------------------------------------------------------------- reporting

def report(conn):
    eps = conn.execute("SELECT COUNT(*) c FROM extractions").fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
    print(f"\n  {eps} of {total} episodes extracted\n")

    top = conn.execute(
        """SELECT t.name, COUNT(*) n FROM episode_topics et
           JOIN topics t ON t.id = et.topic_id
           GROUP BY t.id ORDER BY n DESC, t.name LIMIT 12""").fetchall()
    if top:
        print("  most common topics:")
        for t in top:
            print(f"    {t['n']:3}  {t['name']}")

    for role, label in (("guest", "guests"), ("interviewer", "interviewers")):
        rows = conn.execute(
            """SELECT p.name, COUNT(*) n FROM episode_people ep
               JOIN people p ON p.id = ep.person_id
               WHERE ep.role = ? GROUP BY p.id
               ORDER BY n DESC, p.name LIMIT 6""", (role,)).fetchall()
        if rows:
            n = conn.execute(
                "SELECT COUNT(DISTINCT person_id) c FROM episode_people WHERE role = ?",
                (role,)).fetchone()["c"]
            print(f"\n  {n} distinct {label}, most frequent:")
            for r in rows:
                print(f"    {r['n']:3}  {r['name']}")

    # The headline number: guests the hyperlinks never had.
    new = conn.execute(
        """SELECT COUNT(*) c FROM people p
           WHERE p.id IN (SELECT person_id FROM episode_people
                          WHERE role IN ('guest','interviewer'))
             AND p.normalized_name NOT IN (
                 SELECT DISTINCT norm_text FROM mentions WHERE is_boilerplate = 0)"""
    ).fetchone()["c"]
    print(f"\n  {new} guests/interviewers that were never hyperlinked")


def dry_run(conn, episodes, effort, max_tokens):
    """Build every request and cost it without an API key or a network call."""
    payload, chars = [], 0
    for ep in episodes:
        body = build_user_content(conn, ep)
        chars += len(body) + len(SYSTEM_PROMPT)
        payload.append({"custom_id": f"ep-{ep['id']}", "model": MODEL,
                        "effort": effort, "max_tokens": max_tokens,
                        "system_chars": len(SYSTEM_PROMPT),
                        "user_chars": len(body), "user_content": body})

    out = os.path.join(ROOT, "data", "extract-dryrun.json")
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=2)

    # ~3.7 chars/token on English prose. An estimate, deliberately labelled as
    # one — the exact figure needs count_tokens, which needs a key.
    tokens = chars / 3.7
    cached = len(SYSTEM_PROMPT) / 3.7 * max(0, len(episodes) - 1)
    billed = tokens - cached * 0.9
    print(f"  {len(episodes)} episodes, ~{tokens/1e6:.2f}M input tokens")
    print(f"  ~${billed / 1e6 * 2.50:.2f} at batch rates "
          f"(50% off, cached system prompt) — estimate, not a quote")
    print(f"  full payload written to {os.path.relpath(out, ROOT)}")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="build and cost the batch, send nothing (no key needed)")
    ap.add_argument("--rebuild", action="store_true",
                    help="re-derive topics/people from stored output (no key needed)")
    ap.add_argument("--submit", action="store_true", help="submit and exit")
    ap.add_argument("--collect", metavar="BATCH_ID", nargs="?", const="",
                    help="collect a submitted batch (defaults to the last one)")
    ap.add_argument("--redo", action="store_true",
                    help="re-extract episodes already done under this prompt")
    ap.add_argument("--limit", type=int, help="only the N most recent episodes")
    ap.add_argument("--effort", default="medium",
                    choices=["low", "medium", "high", "xhigh", "max"],
                    help="thinking depth (default medium)")
    ap.add_argument("--max-tokens", type=int, default=8000,
                    help="output ceiling per episode, thinking included")
    args = ap.parse_args()

    conn = connect()
    ensure_schema(conn)

    if args.rebuild:
        print("Rebuilding topics and people from stored model output")
        t, p, bad = build_tables(conn)
        print(f"  {t} topics, {p} people" + (f", {bad} unparseable rows" if bad else ""))
        report(conn)
        return conn.close()

    if args.collect is not None:
        batch_id = args.collect or json.load(open(BATCH_STATE))["id"]
        print(f"Collecting {batch_id}")
        stored, errors = collect(conn, batch_id)
        print(f"  {stored} stored, {errors} failed")
        t, p, bad = build_tables(conn)
        print(f"  {t} topics, {p} people")
        report(conn)
        return conn.close()

    episodes = pending_episodes(conn, redo=args.redo, limit=args.limit)
    if not episodes:
        print("Nothing to extract — every episode is done under "
              f"prompt {PROMPT_VERSION}. Use --redo to force.")
        return conn.close()

    if args.dry_run:
        print(f"Dry run — {PROMPT_VERSION}, {MODEL}, effort {args.effort}")
        dry_run(conn, episodes, args.effort, args.max_tokens)
        return conn.close()

    print(f"Extracting {len(episodes)} episodes — {MODEL}, effort {args.effort}")
    batch_id = submit(conn, episodes, args.effort, args.max_tokens)
    if args.submit:
        print(f"  collect later with:  python3 ingest/extract.py --collect")
        return conn.close()

    print("  waiting (most batches finish well inside an hour)")
    wait(batch_id)
    stored, errors = collect(conn, batch_id)
    print(f"  {stored} stored, {errors} failed")
    t, p, bad = build_tables(conn)
    print(f"  {t} topics, {p} people")
    report(conn)
    conn.close()


if __name__ == "__main__":
    main()
