#!/usr/bin/env python3
"""
Labor Heritage Media Archive — local search server.

Stdlib only. No pip install, no venv:

    python3 serve.py            # http://localhost:8000
    python3 serve.py --port 9000

Swap to FastAPI later without touching the front end — the JSON contract
(/api/search, /api/facets) is what the UI talks to.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))
STATIC = os.path.join(ROOT, "static")

# Search cards are deliberately paged. Fifty keeps the first response and DOM
# small even when a blank search matches the complete archive. The public API
# accepts a somewhat larger page for integrations, but never the old 1,000-row
# browser payload; export calls search() directly with its own 5,000-row limit.
SEARCH_PAGE_SIZE = 50
SEARCH_LIMIT = 200


EPISODE_SQL = """SELECT e.id, e.title, e.published_at, e.duration_sec,
                        e.audio_url, e.episode_url, e.guid, s.name AS show_name
                 FROM episodes e JOIN shows s ON s.id = e.show_id"""


def guid_hash(guid):
    """Short, stable fingerprint of an episode's feed id.

    Eight hex characters — 32 bits. Enough that a collision across a few
    hundred episodes is not going to happen, and short enough that a shared
    link stays readable. This is an integrity check on a link, not a secret:
    it answers "is row 123 still the episode this link was made for", so a
    truncated hash is the right tool and sha1 is a fine one.
    """
    return hashlib.sha1((guid or "").encode("utf-8")).hexdigest()[:8]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, name):
    """
    The extraction tables are optional — the archive works without them, and a
    database that has never had extract.py run against it must not 500 on a
    filter that references them. Filters have to check before they build SQL;
    decorate() can get away with catching OperationalError, but a WHERE clause
    that mentions a missing table poisons the whole query including the count.
    """
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


# Anything here means the user is writing a real query, not just typing words.
# Covers LC/library conventions: boolean operators, grouping, phrases,
# truncation, proximity, and field-scoped search (title:strike).
EXPERT_SYNTAX = re.compile(
    r'(?:(?<=\s)|^)(?:AND|OR|NOT|NEAR)(?:(?=\s)|$)'   # boolean, uppercase only
    r'|[()"*]'                                         # grouping, phrase, truncation
    r'|\b(?:title|description_text|transcript_text)\s*:'   # fielded
)


def fts_query(raw):
    """
    Two modes, decided by what the user typed.

    EXPERT — the query contains boolean operators, parentheses, quotes,
    truncation or a field prefix. Pass it to FTS5 essentially as written so
    `(strike OR walkout) NOT encore` and `title:organiz*` mean exactly what a
    cataloguer expects. A malformed query returns a syntax error, which is far
    better than silently running something else.

    PLAIN — bare words. Implicit AND, and the final token is prefix-matched so
    results stay useful mid-word while typing.

    Note on truncation: the index uses unicode61 (no stemming), so `organiz*`
    matches organize/organized/organizing/organizers exactly as written. See
    schema.sql for why stemming was rejected.
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    if EXPERT_SYNTAX.search(raw):
        # Balance stray quotes so one unclosed " doesn't error the whole query.
        if raw.count('"') % 2:
            raw += '"'
        return raw

    words = re.findall(r"[\w'-]+", raw, re.UNICODE)
    if not words:
        return None
    parts = [f'"{w}"' for w in words[:-1]]
    parts.append(f'"{words[-1]}"*')          # prefix-match the token in progress
    return " ".join(parts)


def decorate(conn, rows, match=None):
    """Attach re-airs, tags, topics, people and matching spoken moments."""
    if not rows:
        return []
    out = [dict(r) for r in rows]
    # FTS gives a snippet per column; show whichever one actually contains the
    # match. Without this, a hit in the spoken transcript renders a snippet of
    # the show notes with nothing highlighted in it.
    for r in out:
        tx = r.pop("snip_tx", None)
        desc = r.pop("snip_desc", None)
        if tx and "<mark>" in tx:
            r["excerpt"], r["excerpt_from"] = tx, "transcript"
        elif desc:
            r["excerpt"], r["excerpt_from"] = desc, "description"
        else:
            # Browsing: no query, so no snippet. The card renders the full
            # notes instead and clamps them, which is the only mode where
            # the reader can see everything the feed actually published.
            r["excerpt"], r["excerpt_from"] = None, "full"
    ids = [r["id"] for r in out]
    marks = ",".join("?" * len(ids))
    by_id = {r["id"]: r for r in out}
    for r in out:
        r["reairs"], r["mentions"], r["moments"] = [], [], []
        r["topics"], r["people"] = [], []

    # Enrichment tables may not exist yet (fresh database, or a refresh still
    # in flight). Search should still work — degrade, don't 500.
    try:
        for m in conn.execute(
            f"""SELECT episode_id, text, url, norm_text FROM mentions
                WHERE episode_id IN ({marks}) AND is_boilerplate = 0
                ORDER BY text""", ids):
            by_id[m["episode_id"]]["mentions"].append(dict(m))
    except sqlite3.OperationalError:
        pass

    # Topics and people come from the AI extraction pass, which is optional —
    # the archive is fully usable without it, so an un-extracted database must
    # degrade to empty lists rather than erroring.
    try:
        for t in conn.execute(
            f"""SELECT et.episode_id, t.name, t.normalized_name
                FROM episode_topics et JOIN topics t ON t.id = et.topic_id
                WHERE et.episode_id IN ({marks})
                ORDER BY t.name COLLATE NOCASE""", ids):
            by_id[t["episode_id"]]["topics"].append(dict(t))
    except sqlite3.OperationalError:
        pass

    try:
        # Role order, not alphabetical: a card should read "interviewed by X,
        # with guests Y and Z", which is the order a producer thinks in.
        for p in conn.execute(
            f"""SELECT ep.episode_id, p.name, p.normalized_name, ep.role, ep.confidence
                FROM episode_people ep JOIN people p ON p.id = ep.person_id
                WHERE ep.episode_id IN ({marks})
                ORDER BY CASE ep.role WHEN 'host' THEN 0 WHEN 'interviewer' THEN 1
                                      WHEN 'guest' THEN 2 ELSE 3 END,
                         p.name COLLATE NOCASE""", ids):
            by_id[p["episode_id"]]["people"].append(dict(p))
    except sqlite3.OperationalError:
        pass

    # Matching moments: the passage-level index tells us *where* in the audio
    # the phrase occurs, which is what a timestamp link needs.
    if match:
        for r in out:
            r["moments"] = []
        try:
            for m in conn.execute(
                f"""SELECT s.episode_id, s.start_sec, s.end_sec, s.text,
                           snippet(segments_fts, 0, '<mark>', '</mark>', '…', 18) AS excerpt
                    FROM segments_fts f
                    JOIN segments s ON s.id = f.rowid
                    WHERE segments_fts MATCH ? AND s.episode_id IN ({marks})
                    ORDER BY s.episode_id, rank""", [match] + ids):
                bucket = by_id[m["episode_id"]]["moments"]
                if len(bucket) < 3:
                    bucket.append({"start_sec": m["start_sec"],
                                   "end_sec": m["end_sec"],
                                   "excerpt": m["excerpt"]})
        except sqlite3.OperationalError:
            pass          # malformed query already surfaced by the main search

    try:
        for a in conn.execute(
            f"""SELECT ra.episode_id, ra.kind, e.id, e.title, e.published_at,
                       s.name AS show_name, e.episode_url
                FROM reairs ra
                JOIN episodes e ON e.id = ra.related_id
                JOIN shows s    ON s.id = e.show_id
                WHERE ra.episode_id IN ({marks})
                ORDER BY e.published_at""", ids):
            by_id[a["episode_id"]]["reairs"].append(dict(a))
    except sqlite3.OperationalError:
        pass

    return out


# Sort keys the UI offers. "relevance" only means anything with a query, so
# it silently falls back to newest when browsing.
SORTS = {
    # Every order ends in a unique key. Without that tie-breaker two episodes
    # sharing a date/title/duration can drift between OFFSET pages and appear
    # twice (or not at all) as the reader loads more.
    "relevance": "rank, e.published_at DESC, e.id DESC",
    "newest":    "e.published_at DESC, e.id DESC",
    "oldest":    "e.published_at ASC, e.id ASC",
    "title":     "e.title COLLATE NOCASE ASC, e.id ASC",
    "longest":   "e.duration_sec DESC NULLS LAST, e.id DESC",
    "shortest":  "e.duration_sec ASC NULLS LAST, e.id ASC",
}


def search(conn, q="", show=None, year=None, encore=None, person=None,
           topic=None, role=None, sort=None, limit=SEARCH_PAGE_SIZE, offset=0):
    where, params = [], []

    match = fts_query(q)
    if match:
        sql = """
            SELECT e.id, e.title, e.published_at, e.duration_sec, e.episode_url,
                   e.audio_url, e.is_encore, s.name AS show_name, s.slug AS show_slug,
                   snippet(episodes_fts, 1, '<mark>', '</mark>', '…', 28) AS snip_desc,
                   snippet(episodes_fts, 2, '<mark>', '</mark>', '…', 28) AS snip_tx,
                   e.description_text AS description,
                   (e.transcript_text IS NOT NULL) AS has_transcript,
                   rank AS score
            FROM episodes_fts f
            JOIN episodes e ON e.id = f.rowid
            JOIN shows s    ON s.id = e.show_id
            WHERE episodes_fts MATCH ?
        """
        params.append(match)
    else:
        sql = """
            SELECT e.id, e.title, e.published_at, e.duration_sec, e.episode_url,
                   e.audio_url, e.is_encore, s.name AS show_name, s.slug AS show_slug,
                   -- Browsing has no match to snippet around, so the card shows
                   -- the notes themselves and the UI clamps them. This used to
                   -- be substr(...,1,240), which cut every single episode --
                   -- the median note is 1,064 characters -- mid-word and with
                   -- no ellipsis, so it read as corrupted rather than shortened.
                   NULL AS snip_desc,
                   NULL AS snip_tx,
                   e.description_text AS description,
                   (e.transcript_text IS NOT NULL) AS has_transcript,
                   0 AS score
            FROM episodes e
            JOIN shows s ON s.id = e.show_id
            WHERE 1=1
        """


    if show:
        where.append("s.slug = ?")
        params.append(show)
    if year:
        where.append("substr(e.published_at,1,4) = ?")
        params.append(str(year))
    if encore == "1":
        where.append("e.is_encore = 1")
    if person:
        # A name can reach the catalogue two ways: the producers hyperlinked it,
        # or the extraction pass heard it. Clicking a name must find every
        # episode either way, so this is a union rather than a choice — and the
        # people half is wrapped, because that table only exists after
        # extraction has been run at least once.
        clauses = ["e.id IN (SELECT episode_id FROM mentions "
                   "WHERE norm_text = ? AND is_boilerplate = 0)"]
        params.append(person)
        if table_exists(conn, "episode_people"):
            clauses.append(
                "e.id IN (SELECT ep.episode_id FROM episode_people ep "
                "JOIN people p ON p.id = ep.person_id "
                "WHERE p.normalized_name = ?" +
                (" AND ep.role = ?)" if role else ")"))
            params.append(person)
            if role:
                params.append(role)
        where.append("(" + " OR ".join(clauses) + ")")

    if topic and table_exists(conn, "episode_topics"):
        where.append(
            "e.id IN (SELECT et.episode_id FROM episode_topics et "
            "JOIN topics t ON t.id = et.topic_id WHERE t.normalized_name = ?)")
        params.append(topic)

    if where:
        sql += " AND " + " AND ".join(where)

    # relevance is only meaningful against a MATCH; fall back when browsing
    key = sort if sort in SORTS else ("relevance" if match else "newest")
    if key == "relevance" and not match:
        key = "newest"
    order = "ORDER BY " + SORTS[key]

    try:
        # True match count first, so the UI can say "showing 50 of 107"
        # instead of silently truncating and reporting the truncated number.
        total = conn.execute(
            f"SELECT COUNT(*) FROM ({sql})", params
        ).fetchone()[0]
        rows = conn.execute(
            f"{sql} {order} LIMIT ? OFFSET ?", params + [limit, offset]
        ).fetchall()
    except sqlite3.OperationalError as exc:
        return {"error": f"search error: {exc}", "results": [], "count": 0, "total": 0}

    return {
        "count": len(rows),
        "total": total,
        "offset": offset,
        "truncated": offset + len(rows) < total,
        "has_more": offset + len(rows) < total,
        "next_offset": offset + len(rows),
        "query": q,
        "sort": key,
        "results": decorate(conn, rows, match),
    }


def entities(conn, limit=400):
    # mentions is created by enrich.py, not schema.sql, so it genuinely does
    # not exist on a first boot — the container serves an empty database while
    # it fills in behind itself, and this endpoint used to 500 for that whole
    # window. Same guard the topics/people endpoints use.
    if not table_exists(conn, "mentions"):
        return {"count": 0, "entities": []}
    rows = conn.execute(
        """SELECT text, norm_text, COUNT(DISTINCT episode_id) AS n,
                  MAX(url) AS url
           FROM mentions WHERE is_boilerplate = 0
           GROUP BY norm_text
           ORDER BY n DESC, text COLLATE NOCASE
           LIMIT ?""", (limit,)).fetchall()
    return {"count": len(rows), "entities": [dict(r) for r in rows]}


def segments(conn, ep_id, q=""):
    """
    One episode's transcript, line by line, for the transcript modal.

    Highlighting is done here rather than in the browser so that finding a
    phrase inside an episode behaves exactly like finding it across the
    archive — `"exact phrase"`, AND/OR/NOT, organiz*, NEAR() all work, because
    it's the same FTS index answering. Reimplementing that client-side would
    drift from the real search the first time anyone typed an operator.

    highlight() rather than snippet(): snippet truncates to a window, and this
    view wants the whole line with the matched words marked inside it.
    """
    ep = conn.execute(
        """SELECT e.id, e.title, e.published_at, e.duration_sec, e.audio_url,
                  e.episode_url, e.transcript_url, e.transcript_source,
                  s.name AS show_name
           FROM episodes e JOIN shows s ON s.id = e.show_id
           WHERE e.id = ?""", (ep_id,)).fetchone()
    if not ep:
        return None

    rows = conn.execute(
        """SELECT id, start_sec, end_sec, text FROM segments
           WHERE episode_id = ? ORDER BY start_sec, id""", (ep_id,)).fetchall()

    out = {"episode": dict(ep), "segments": [dict(r) for r in rows],
           "matches": 0, "query": q or ""}

    match = fts_query(q)
    if match and rows:
        try:
            marked = {
                m["id"]: m["marked"] for m in conn.execute(
                    """SELECT s.id,
                              highlight(segments_fts, 0, '<mark>', '</mark>') AS marked
                       FROM segments_fts f JOIN segments s ON s.id = f.rowid
                       WHERE segments_fts MATCH ? AND s.episode_id = ?""",
                    (match, ep_id))
            }
            for seg in out["segments"]:
                if seg["id"] in marked:
                    seg["marked"] = marked[seg["id"]]
            out["matches"] = len(marked)
        except sqlite3.OperationalError as exc:
            # A malformed query should grey out the match count, not blank the
            # transcript — the words are still worth reading.
            out["error"] = f"search error: {exc}"
    return out


def to_timecode(sec, comma=False):
    """SRT wants 00:00:12,340; WebVTT wants 00:00:12.340."""
    sec = max(0.0, float(sec or 0))
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"


def transcript_as(rows, fmt):
    """Rebuild subtitle files from the segment rows we already store."""
    if fmt == "srt":
        return "\n".join(
            f"{i}\n{to_timecode(r['start_sec'], True)} --> "
            f"{to_timecode(r['end_sec'] if r['end_sec'] is not None else (r['start_sec'] or 0) + 4, True)}\n"
            f"{r['text']}\n"
            for i, r in enumerate(rows, 1))
    # WebVTT — what a browser <track> and most captioning tools want.
    body = "\n".join(
        f"{to_timecode(r['start_sec'])} --> "
        f"{to_timecode(r['end_sec'] if r['end_sec'] is not None else (r['start_sec'] or 0) + 4)}\n"
        f"{r['text']}\n"
        for r in rows)
    return "WEBVTT\n\n" + body


def topics(conn, limit=400):
    """The subject vocabulary, commonest first — the topic browse list."""
    if not table_exists(conn, "episode_topics"):
        return {"count": 0, "topics": [], "extracted": False}
    rows = conn.execute(
        """SELECT t.name, t.normalized_name, COUNT(DISTINCT et.episode_id) AS n
           FROM episode_topics et JOIN topics t ON t.id = et.topic_id
           GROUP BY t.id ORDER BY n DESC, t.name COLLATE NOCASE
           LIMIT ?""", (limit,)).fetchall()
    # schema.sql creates these tables up front, so their existence proves
    # nothing — "extracted" has to mean "has rows", or the UI renders an empty
    # topics panel on every archive that has never run the pass.
    return {"count": len(rows), "topics": [dict(r) for r in rows],
            "extracted": bool(rows)}


def people(conn, role=None, limit=400):
    """Guests and interviewers, for the browse lists and the ?person= links."""
    if not table_exists(conn, "episode_people"):
        return {"count": 0, "people": [], "extracted": False}
    sql = """SELECT p.name, p.normalized_name, ep.role,
                    COUNT(DISTINCT ep.episode_id) AS n
             FROM episode_people ep JOIN people p ON p.id = ep.person_id"""
    params = []
    if role:
        sql += " WHERE ep.role = ?"
        params.append(role)
    sql += """ GROUP BY p.id, ep.role
               ORDER BY n DESC, p.name COLLATE NOCASE LIMIT ?"""
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return {"count": len(rows), "people": [dict(r) for r in rows],
            "extracted": bool(rows)}


# ---------------------------------------------------------------- export

# One row per episode keeps the sheet pivotable. Header names carry units so
# the values can stay numeric (54, not "54 min") and remain sortable/summable.
EXPORT_COLUMNS = [
    ("show",             "Show"),
    ("title",            "Title"),
    ("published",        "Published"),
    ("duration_min",     "Duration (min)"),
    ("is_encore",        "Encore"),
    ("topics",           "Topics"),
    ("guests",           "Guests"),
    ("interviewer",      "Interviewer"),
    ("tags",             "Tags"),
    ("reair_dates",      "Also aired"),
    ("has_transcript",   "Transcript"),
    ("transcript_words", "Words"),
    ("episode_url",      "Episode page"),
    ("source_url",       "Source transcript"),
    ("archive_url",      "Archive transcript"),
    ("audio_url",        "Audio"),
    # Last on purpose. A spreadsheet reader does not want to meet a 40-character
    # identifier first, but it is the only column here that survives the
    # database being rebuilt — so anything referencing an episode from outside
    # the file keys on this rather than on a row number.
    ("guid",             "Feed ID"),
]


def export_rows(conn, base_url, **kw):
    """Flatten search results into spreadsheet-shaped rows."""
    kw.setdefault("limit", 5000)
    data = search(conn, **kw)
    if data.get("error"):
        return None, data["error"]

    ids = [r["id"] for r in data["results"]]
    words, src, guids = {}, {}, {}
    if ids:
        marks = ",".join("?" * len(ids))
        for r in conn.execute(
            f"""SELECT id, transcript_url, guid,
                       CASE WHEN transcript_text IS NULL THEN 0
                            ELSE LENGTH(transcript_text)
                                 - LENGTH(REPLACE(transcript_text,' ','')) + 1 END AS w
                FROM episodes WHERE id IN ({marks})""", ids):
            words[r["id"]] = r["w"]
            src[r["id"]] = r["transcript_url"]
            guids[r["id"]] = r["guid"]

    rows = []
    for r in data["results"]:
        has_tx = bool(words.get(r["id"]))
        rows.append({
            "show": r["show_name"],
            "title": r["title"],
            # ISO so a spreadsheet parses it as a real date, not text.
            "published": (r["published_at"] or "")[:10],
            "duration_min": round((r["duration_sec"] or 0) / 60) or "",
            # TRUE/FALSE gives Sheets checkbox filtering; 1/0 would be numeric.
            "is_encore": "TRUE" if r["is_encore"] else "FALSE",
            "topics": "; ".join(t["name"] for t in r.get("topics", [])),
            "guests": "; ".join(p["name"] for p in r.get("people", [])
                                if p["role"] == "guest"),
            "interviewer": "; ".join(p["name"] for p in r.get("people", [])
                                     if p["role"] == "interviewer"),
            "tags": "; ".join(m["text"] for m in r.get("mentions", [])),
            "reair_dates": "; ".join(
                (a["published_at"] or "")[:10] for a in r.get("reairs", [])),
            "has_transcript": "TRUE" if has_tx else "FALSE",
            "transcript_words": words.get(r["id"]) or "",
            "episode_url": r["episode_url"] or "",
            "source_url": src.get(r["id"]) or "",
            "archive_url": f"{base_url}/episode/{r['id']}/transcript" if has_tx else "",
            "audio_url": r["audio_url"] or "",
            # Last, because a spreadsheet reader does not want to meet it
            # first — but present, because it is the only identifier here that
            # survives the database being rebuilt. Everything that references
            # an episode from outside this file uses it.
            "guid": guids.get(r["id"]) or "",
        })
    return rows, None


def to_delimited(rows, delimiter, bom):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL,
                   lineterminator="\r\n")
    w.writerow([label for _, label in EXPORT_COLUMNS])
    for r in rows:
        w.writerow([r[key] for key, _ in EXPORT_COLUMNS])
    text = buf.getvalue()
    # BOM so Excel reads UTF-8 — without it "No Pasarán" arrives as mojibake.
    return ("\ufeff" + text if bom else text).encode("utf-8")


def export_filename(ext, filters):
    bits = ["lhf-archive", date.today().isoformat()]
    bits += [v for v in filters if v]
    slug = "_".join(re.sub(r"[^a-z0-9]+", "-", str(b).lower()).strip("-") for b in bits)
    return f"{slug[:120]}.{ext}"


def facets(conn):
    shows = conn.execute(
        """
        SELECT s.slug, s.name, COUNT(e.id) AS n
        FROM shows s LEFT JOIN episodes e ON e.show_id = s.id
        GROUP BY s.id ORDER BY s.name
        """
    ).fetchall()
    years = conn.execute(
        """
        SELECT substr(published_at,1,4) AS y, COUNT(*) AS n
        FROM episodes WHERE published_at IS NOT NULL
        GROUP BY y ORDER BY y DESC
        """
    ).fetchall()
    totals = conn.execute(
        """
        SELECT COUNT(*) AS episodes,
               ROUND(SUM(duration_sec)/3600.0,1) AS hours,
               SUM(is_encore) AS encores
        FROM episodes
        """
    ).fetchone()
    # When the feeds were last successfully read. Surfaced because nothing in
    # this application has ever shown it: on 13 August 2026 the only way to
    # tell whether the archive was current was to open Podbean and compare by
    # hand, and an hour went into deciding whether a ten-hour-old episode meant
    # the updater was broken. A stale archive should be visible by looking.
    #
    # `shows.feed_checked_at`, not `episodes.last_seen_in_feed`. The second only
    # moves when a feed actually changed, and both shows are weekly — so on a
    # 15-minute poll it is days old almost all the time, and a footer built on
    # it would report a perfectly healthy updater as stale. What the reader
    # wants to know is when we last *looked*.
    #
    # Guarded on the column existing, which is not defensive habit: a deployed
    # database predates it, `schema.sql` only creates *missing* tables, and the
    # ALTER lives in ingest.py's migrate() — which does not run until the first
    # poll after a deploy. serve.py answers immediately, and this endpoint is
    # also the container health check, so raising here would fail the check and
    # restart the container in a loop until a poll happened to land. A missing
    # column means exactly "never polled", which the footer already renders as
    # nothing at all.
    have = {r["name"] for r in conn.execute("PRAGMA table_info(shows)")}
    updated = None
    if "feed_checked_at" in have:
        updated = conn.execute(
            "SELECT MAX(feed_checked_at) m FROM shows").fetchone()["m"]

    return {
        "shows": [dict(r) for r in shows],
        "years": [dict(r) for r in years],
        "totals": dict(totals),
        "updated": updated,
    }


def bundle(conn, base_url, want_transcripts, want_passages, **kw):
    """Everything the archive package needs, in one request.

    The browser assembles the .zip itself — that is the constraint this project
    keeps, and it is why the media never touches our disk — but it should not
    have to make 288 requests to do it. One call, one set of queries, and the
    client does the packaging.

    Everything is keyed on `guid`. Episode ids are assigned in ingest order, so
    a package keyed on them stops meaning anything the first time the database
    is rebuilt from empty, and this project has already been burned by exactly
    that (HANDOFF.md, "Small things that were wrong").
    """
    rows, err = export_rows(conn, base_url, **kw)
    if err:
        return None, err

    # export_rows calls search() with these same arguments, so this returns the
    # same episodes in the same order. Matching on guid rather than position
    # anyway, because "these two lists line up" is the kind of assumption that
    # is true until someone adds a filter to one of them.
    ids = [r["id"] for r in search(conn, **{**kw, "limit": 5000})["results"]]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "episode_count": len(rows),
        "episodes": rows,
    }

    if not ids:
        if want_transcripts:
            out["transcripts"] = {}
        if want_passages:
            out["passages"] = []
        return out, None

    marks = ",".join("?" * len(ids))
    guid_of = {r["id"]: r["guid"] for r in conn.execute(
        f"SELECT id, guid FROM episodes WHERE id IN ({marks})", ids)}

    if want_transcripts:
        out["transcripts"] = {
            guid_of[r["id"]]: r["transcript_text"]
            for r in conn.execute(
                f"""SELECT id, transcript_text FROM episodes
                    WHERE id IN ({marks}) AND transcript_text IS NOT NULL
                      AND transcript_text <> ''""", ids)
        }

    if want_passages:
        out["passages"] = [
            {"guid": guid_of[r["episode_id"]],
             "start_sec": r["start_sec"],
             "end_sec": r["end_sec"],
             "text": r["text"]}
            for r in conn.execute(
                f"""SELECT episode_id, start_sec, end_sec, text FROM segments
                    WHERE episode_id IN ({marks})
                    ORDER BY episode_id, start_sec, id""", ids)
        ]

    return out, None


_VERSION = {"key": None, "value": None}


def app_version():
    """A fingerprint of the files a browser is running.

    Exists because `Cache-Control` cannot help a page that is already open. A
    tab left running for a fortnight is executing a fortnight-old script, not
    because anything was cached but because it never asked again. This gives a
    running page a way to notice, and the UI turns that into a reload prompt.

    Hashed by content rather than by mtime, so a redeploy that changes no files
    does not announce a new version — nobody trusts a prompt that cries wolf.
    Stat first and hash only when something moved: an unchanged fingerprint
    costs three stat calls, which is what this endpoint mostly does.
    """
    # Every front-end file the browser holds, or the prompt lies by omission.
    # zip.js was missing here from the day it was added: ship a fix to the
    # archive packager alone and no open tab would ever be told. Adding a
    # module means adding it to this tuple — there is nothing that derives it.
    names = ("index.html", "mp3cut.js", "waveform.js", "zip.js", "clips.js")
    stamps = []
    for name in names:
        try:
            st = os.stat(os.path.join(STATIC, name))
            stamps.append(f"{name}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            stamps.append(f"{name}:missing")
    key = "|".join(stamps)

    if _VERSION["key"] != key:
        h = hashlib.blake2b(digest_size=8)
        for name in names:
            try:
                with open(os.path.join(STATIC, name), "rb") as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b"\0missing\0")
        # Assign the value before the key: another thread reading mid-update
        # should see a stale-but-consistent pair, never a new key pointing at
        # an old digest.
        _VERSION["value"] = h.hexdigest()
        _VERSION["key"] = key
    return _VERSION["value"]



def gzip_bytes(payload):
    """Deterministic gzip: the same bytes in must give the same bytes out.

    `gzip.compress()` writes the current time into the GZIP header's MTIME
    field (RFC 1952, bytes 4-8), so compressing identical input a second apart
    produces different output. That is harmless for transport and fatal for a
    validator: `_send` hashes the *compressed* body to build the ETag, so the
    ETag changed every second and a browser's `If-None-Match` almost never
    matched. 304s were not happening for any real client - every browser sends
    `Accept-Encoding: gzip` - which is the exact failure the ETag was added to
    fix, surviving inside the fix for it.

    mtime=0 makes the output a pure function of the input. Nothing reads the
    field; gzip stores it only so `gunzip` can restore a filename's date.
    """
    return gzip.compress(payload, 6, mtime=0)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):        # quieter console
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")

        # This content compresses extremely well — a default search response
        # goes from 216 KB to about 51 KB, the page itself from 93 KB to 25 KB.
        # On a phone those bytes cost far more than the CPU to produce them.
        # Level 6 rather than 9: nearly the same size for a fraction of the work.
        # Small bodies are left alone; below a kilobyte the header and the CPU
        # outweigh anything saved.
        gz = len(payload) > 1024 and "gzip" in self.headers.get("Accept-Encoding", "")
        if gz:
            payload = gzip_bytes(payload)

        # An ETag is what makes `no-cache` cheap. Without a validator the
        # browser has nothing to revalidate *with*, so "check before you reuse
        # it" degrades into "download it all again, every time" — which is what
        # this server did for its whole life, while a comment here claimed the
        # 304s were costing nothing. They were not happening.
        #
        # The hash is taken after compression on purpose: a gzipped body and a
        # plain one are different representations of the same resource, and
        # giving them one ETag would let a cache hand the wrong bytes to a
        # client whose Accept-Encoding differs. That is the same failure `Vary`
        # is there to prevent, so the two agree.
        etag = None
        if code == 200:
            etag = '"%s"' % hashlib.blake2b(payload, digest_size=16).hexdigest()
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                if gz:
                    self.send_header("Vary", "Accept-Encoding")
                self.end_headers()
                return

        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if gz:
            self.send_header("Content-Encoding", "gzip")
            # Any cache between here and the browser must key on this, or it
            # will hand compressed bytes to a client that didn't ask for them.
            self.send_header("Vary", "Accept-Encoding")
        if etag:
            self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(payload)))
        # Without this the server sends no cache headers at all and browsers
        # cache heuristically, so a deploy can leave someone running the old
        # app indefinitely with no way to tell. That cost real debugging time:
        # a fixed bug looked unfixed locally because the page was months-stale
        # in one tab and current in another. There is no build step and no
        # fingerprinted filenames here, so the URL never changes when the
        # contents do — revalidating every time is the only thing that works.
        # Applied to everything, API responses included: the archive updates
        # daily, and a heuristically cached search result is the same trap
        # wearing a hat.
        #
        # None of this reaches a tab that is already open. `no-cache` governs
        # what happens when the browser asks; a running page never asks. That
        # is what /api/version and the reload prompt in the UI are for.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        one = lambda k: (qs.get(k) or [None])[0]  # noqa: E731

        if path == "/api/search":
            conn = connect()
            try:
                try:
                    limit = int(one("limit") or SEARCH_PAGE_SIZE)
                    offset = int(one("offset") or 0)
                except ValueError:
                    limit, offset = SEARCH_PAGE_SIZE, 0
                data = search(
                    conn,
                    q=one("q") or "",
                    show=one("show"),
                    year=one("year"),
                    encore=one("encore"),
                    person=one("person"),
                    topic=one("topic"),
                    role=one("role"),
                    sort=one("sort"),
                    limit=max(1, min(limit, SEARCH_LIMIT)),
                    offset=max(0, offset),
                )
            finally:
                conn.close()
            return self._send(200, json.dumps(data))

        if path == "/api/entities":
            conn = connect()
            try:
                data = entities(conn)
            finally:
                conn.close()
            return self._send(200, json.dumps(data))

        if path == "/api/topics":
            conn = connect()
            try:
                data = topics(conn)
            finally:
                conn.close()
            return self._send(200, json.dumps(data))

        if path == "/api/people":
            conn = connect()
            try:
                data = people(conn, role=one("role"))
            finally:
                conn.close()
            return self._send(200, json.dumps(data))

        if path == "/api/export":
            fmt = (one("format") or "csv").lower()
            # `limit` exists so the export dialogue can show a couple of real
            # rows before you commit to the file. Deliberately the same code
            # path as the download rather than a preview built in JS — a
            # preview that could disagree with the file would be worse than
            # none. Only passed when valid, because export_rows sets its own
            # default and None would override it.
            extra = {}
            try:
                if one("limit"):
                    extra["limit"] = max(1, min(5000, int(one("limit"))))
            except ValueError:
                pass
            conn = connect()
            try:
                rows, err = export_rows(
                    conn, f"http://{self.headers.get('Host', 'localhost:8000')}",
                    q=one("q") or "", show=one("show"), year=one("year"),
                    encore=one("encore"), person=one("person"),
                    topic=one("topic"), role=one("role"), sort=one("sort"),
                    **extra)
            finally:
                conn.close()
            if err:
                return self._send(400, json.dumps({"error": err}))

            name = export_filename(
                "csv" if fmt == "csv" else "tsv" if fmt == "tsv" else "json",
                [one("show"), one("year"), (one("q") or "")[:24]])

            if fmt == "json":
                body = json.dumps(rows, indent=2).encode("utf-8")
                ctype = "application/json; charset=utf-8"
            elif fmt == "tsv":
                body = to_delimited(rows, "\t", bom=False)
                ctype = "text/tab-separated-values; charset=utf-8"
            else:
                body = to_delimited(rows, ",", bom=True)
                ctype = "text/csv; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("X-Row-Count", str(len(rows)))
            # Same reasoning as _send: an export must reflect the archive as it
            # is now, not as it was when this URL was last visited.
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)

        # One episode, for shared moment links (?ep=&from=&to=) that open the
        # clip editor without running a search first.
        # `?g=` is an integrity token, not a security one.
        #
        # Episode ids are INTEGER PRIMARY KEY assigned in ingest order, so
        # rebuilding the database from an empty volume can hand the same number
        # to a different episode. A `?ep=123&from=&to=` link emailed in March
        # would then open a different show at the same timecode, silently — the
        # same class of mistake as the `ep-<id>` peaks cache that once served a
        # returning visitor another show's waveform.
        #
        # So a link also carries the first 8 hex of sha1(guid). Resolve the id,
        # compare; on a mismatch the id has drifted and the hash is believed
        # instead. Read-only, one branch, and an old link without `g` behaves
        # exactly as it always did.
        m = re.fullmatch(r"/api/episode/(\d+)", path)
        if m:
            want = (one("g") or "").lower()
            conn = connect()
            try:
                row = conn.execute(EPISODE_SQL + " WHERE e.id = ?",
                                   (int(m.group(1)),)).fetchone()
                if want and (not row or guid_hash(row["guid"]) != want):
                    # The id no longer names the episode the link was made for.
                    # Find the recording itself.
                    for cand in conn.execute(EPISODE_SQL):
                        if guid_hash(cand["guid"]) == want:
                            row = cand
                            break
                    else:
                        row = None
            finally:
                conn.close()
            if not row:
                return self._send(404, json.dumps({"error": "no such episode"}))
            out = {k: row[k] for k in row.keys() if k != "guid"}
            out["guid_hash"] = guid_hash(row["guid"])
            return self._send(200, json.dumps(out))

        # The transcript modal's data: every line with its timing, plus
        # server-side highlighting for whatever query opened it.
        m = re.fullmatch(r"/api/episode/(\d+)/segments", path)
        if m:
            conn = connect()
            try:
                data = segments(conn, int(m.group(1)), one("q") or "")
            finally:
                conn.close()
            if data is None:
                return self._send(404, json.dumps({"error": "no such episode"}))
            return self._send(200, json.dumps(data))

        m = re.fullmatch(r"/episode/(\d+)/transcript", path)
        if m:
            ep_id = int(m.group(1))
            fmt = (one("format") or "txt").lower()

            # Subtitle formats are rebuilt from the segment rows rather than
            # stored: same data, and it means a re-ingest can't leave a stale
            # .srt lying around disagreeing with the timings in the database.
            if fmt in ("srt", "vtt"):
                conn = connect()
                try:
                    rows = conn.execute(
                        """SELECT start_sec, end_sec, text FROM segments
                           WHERE episode_id = ? ORDER BY start_sec, id""",
                        (ep_id,)).fetchall()
                    title = conn.execute(
                        "SELECT title FROM episodes WHERE id = ?", (ep_id,)).fetchone()
                finally:
                    conn.close()
                if not rows:
                    return self._send(404, "No timed transcript for that episode.",
                                      "text/plain; charset=utf-8")
                body = transcript_as(rows, fmt).encode("utf-8")
                slug = re.sub(r"[^a-z0-9]+", "-",
                              (title["title"] if title else "episode").lower()).strip("-")
                self.send_response(200)
                self.send_header("Content-Type",
                                 f"text/{'vtt' if fmt == 'vtt' else 'plain'}; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{slug[:80]}.{fmt}"')
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)

            conn = connect()
            try:
                row = conn.execute(
                    """SELECT e.title, e.published_at, e.transcript_text, s.name AS show
                       FROM episodes e JOIN shows s ON s.id = e.show_id
                       WHERE e.id = ?""", (ep_id,)).fetchone()
            finally:
                conn.close()
            if not row or not row["transcript_text"]:
                return self._send(404, "No transcript for that episode.",
                                  "text/plain; charset=utf-8")
            head = (f"{row['title']}\n{row['show']} — "
                    f"{(row['published_at'] or '')[:10]}\n"
                    + "-" * 60 + "\n\n")
            return self._send(200, head + row["transcript_text"],
                              "text/plain; charset=utf-8")

        if path == "/api/facets":
            conn = connect()
            try:
                data = facets(conn)
            finally:
                conn.close()
            return self._send(200, json.dumps(data))

        # Deliberately tiny and database-free: the page asks for this every time
        # it regains focus, and it must stay cheap enough that nobody thinks
        # twice about the frequency.
        # One request instead of 288: everything the browser needs to build the
        # archive package, for exactly the scope the dialogue is showing.
        if path == "/api/bundle":
            conn = connect()
            try:
                data, err = bundle(
                    conn, f"http://{self.headers.get('Host', 'localhost:8000')}",
                    one("transcripts") == "1", one("passages") == "1",
                    q=one("q") or "", show=one("show"), year=one("year"),
                    encore=one("encore"), person=one("person"),
                    topic=one("topic"), role=one("role"), sort=one("sort"))
            finally:
                conn.close()
            if err:
                return self._send(400, json.dumps({"error": err}))
            return self._send(200, json.dumps(data))

        if path == "/api/version":
            return self._send(200, json.dumps({"version": app_version()}))

        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(STATIC, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._send(404, b"static/index.html missing", "text/plain")

        # index.html carries an inline SVG icon, so browsers shouldn't ask for
        # this at all — but crawlers and older clients do, and a 404 in the
        # console reads as something being broken.
        if path == "/favicon.ico":
            icon = (
                b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
                b"<rect width='32' height='32' rx='7' fill='#1b1a17'/>"
                b"<g fill='#d8503a'>"
                b"<rect x='6' y='13' width='3' height='6' rx='1.5'/>"
                b"<rect x='11.5' y='9' width='3' height='14' rx='1.5'/>"
                b"<rect x='17' y='5.5' width='3' height='21' rx='1.5'/>"
                b"<rect x='22.5' y='11' width='3' height='10' rx='1.5'/>"
                b"</g></svg>"
            )
            return self._send(200, icon, "image/svg+xml")

        # The UI was one file until the audio editor arrived; its modules load
        # as real ES modules, so they need to be served with a JS mime type.
        if path.endswith((".js", ".css")):
            name = os.path.basename(path)          # basename kills ../ traversal
            full = os.path.join(STATIC, name)
            kind = "text/javascript" if name.endswith(".js") else "text/css"
            try:
                with open(full, "rb") as fh:
                    return self._send(200, fh.read(), kind + "; charset=utf-8")
            except FileNotFoundError:
                return self._send(404, b"not found", "text/plain")

        return self._send(404, json.dumps({"error": "not found"}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    # Loopback by default: running this on a laptop should not quietly expose
    # the archive to the rest of the network. A container has to be told to
    # listen on 0.0.0.0 or the proxy in front of it can't reach the process.
    ap.add_argument("--host", default=os.environ.get("LHF_HOST", "127.0.0.1"),
                    help="bind address (default 127.0.0.1; use 0.0.0.0 in a container)")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        raise SystemExit(
            f"No database at {DB_PATH}\nRun:  python3 refresh.py"
        )

    conn = connect()
    n = conn.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
    conn.close()

    shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    print(f"Labor Heritage Media Archive — {n} episodes")
    print(f"  http://{shown}:{args.port}  (bound to {args.host})")
    print("  ctrl-c to stop")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
