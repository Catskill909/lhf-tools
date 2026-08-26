#!/usr/bin/env python3
"""
Labor Heritage Media Archive — deterministic enrichment. NO AI.

Everything here is extracted from structure the producers already created,
so it's exact rather than inferred:

  1. Re-airs      — episodes whose titles normalise to the same thing,
                    within a show (encores) or across programs
                    (a segment that ran on more than one). This is the
                    "have we already run this?" question, answered.

  2. Mentions     — text and URL of every hyperlink in the show notes.
                    Producers link guests, bands, museums and books; those
                    links are a hand-curated entity list nobody had to write.
                    Boilerplate (network, sponsor, contact) is filtered by
                    how many episodes it appears in.

The AI extraction pass (Tier 2) layers on top of this — it does NOT replace
it. Anything found here is ground truth and should win on conflict.

    python3 ingest/enrich.py
"""

import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))

# A link on more than this share of episodes is site furniture, not content.
BOILERPLATE_SHARE = 0.10

DDL = """
ALTER TABLE episodes ADD COLUMN norm_title TEXT;
"""

MENTIONS_DDL = """
CREATE TABLE IF NOT EXISTS mentions (
    id           INTEGER PRIMARY KEY,
    episode_id   INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    url          TEXT,
    norm_text    TEXT NOT NULL,
    is_boilerplate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_mentions_episode ON mentions(episode_id);
CREATE INDEX IF NOT EXISTS idx_mentions_norm    ON mentions(norm_text, is_boilerplate);

CREATE TABLE IF NOT EXISTS reairs (
    episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    related_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,      -- encore | cross_show | repeat
    PRIMARY KEY (episode_id, related_id)
);
"""

ENCORE_WORDS = r"encore|rebroadcast|replay|re-?air"


def norm_title(title):
    t = re.sub(rf"\(({ENCORE_WORDS})[^)]*\)", " ", title or "", flags=re.I)
    t = re.sub(rf"\b({ENCORE_WORDS})\b[:\s\-–—]*", " ", t, flags=re.I)
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def norm_entity(text):
    t = (text or "").replace("’", "'").strip().rstrip(".,;:")
    t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t.lower())


LINK_RE = re.compile(r"<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

# Link text that is never an entity, regardless of frequency.
JUNK = {
    "here", "click here", "read more", "more", "link", "listen", "subscribe",
    "this week's show", "download", "learn more", "sign up", "donate",
}


def connect():
    if not os.path.exists(DB_PATH):
        sys.exit(f"No database at {DB_PATH}\nRun:  python3 ingest/ingest.py")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(episodes)")}
    if "norm_title" not in cols:
        conn.execute(DDL)
    conn.executescript(MENTIONS_DDL)
    conn.commit()


def build_reairs(conn):
    conn.execute("DELETE FROM reairs")
    rows = conn.execute(
        """SELECT e.id, e.title, e.published_at, e.is_encore, e.show_id
           FROM episodes e"""
    ).fetchall()

    groups = {}
    for r in rows:
        nt = norm_title(r["title"])
        conn.execute("UPDATE episodes SET norm_title = ? WHERE id = ?", (nt, r["id"]))
        if nt:
            groups.setdefault(nt, []).append(r)

    pairs = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        members = sorted(members, key=lambda r: r["published_at"] or "")
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if a["show_id"] != b["show_id"]:
                    kind = "cross_show"
                elif b["is_encore"] or a["is_encore"]:
                    kind = "encore"
                else:
                    kind = "repeat"
                conn.execute(
                    "INSERT OR REPLACE INTO reairs (episode_id, related_id, kind) VALUES (?,?,?)",
                    (a["id"], b["id"], kind))
                conn.execute(
                    "INSERT OR REPLACE INTO reairs (episode_id, related_id, kind) VALUES (?,?,?)",
                    (b["id"], a["id"], kind))
                pairs += 1
    conn.commit()
    return pairs, sum(1 for g in groups.values() if len(g) > 1)


def build_mentions(conn):
    conn.execute("DELETE FROM mentions")
    rows = conn.execute(
        "SELECT id, description_html FROM episodes WHERE description_html IS NOT NULL"
    ).fetchall()

    total_eps = conn.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"] or 1
    staged = []
    for r in rows:
        seen = set()
        for url, inner in LINK_RE.findall(r["description_html"] or ""):
            text = TAG_RE.sub("", inner)
            text = re.sub(r"\s+", " ", text).strip()
            if not text or len(text) > 80:
                continue
            if text.lower().startswith(("http", "www.")):
                continue
            n = norm_entity(text)
            if not n or n in JUNK or len(n) < 3:
                continue
            if n in seen:
                continue
            seen.add(n)
            staged.append((r["id"], text, url, n))

    conn.executemany(
        "INSERT INTO mentions (episode_id, text, url, norm_text) VALUES (?,?,?,?)",
        staged)

    # Anything on more than BOILERPLATE_SHARE of episodes is furniture.
    cutoff = max(3, int(total_eps * BOILERPLATE_SHARE))
    conn.execute(
        """UPDATE mentions SET is_boilerplate = 1
           WHERE norm_text IN (
               SELECT norm_text FROM mentions
               GROUP BY norm_text HAVING COUNT(DISTINCT episode_id) >= ?
           )""", (cutoff,))
    conn.commit()

    kept = conn.execute(
        "SELECT COUNT(DISTINCT norm_text) c FROM mentions WHERE is_boilerplate = 0"
    ).fetchone()["c"]
    dropped = conn.execute(
        "SELECT COUNT(DISTINCT norm_text) c FROM mentions WHERE is_boilerplate = 1"
    ).fetchone()["c"]
    return len(staged), kept, dropped, cutoff


def main():
    conn = connect()
    ensure_schema(conn)

    print("Re-airs — same episode running more than once")
    pairs, groups = build_reairs(conn)
    for kind in ("cross_show", "encore", "repeat"):
        n = conn.execute(
            "SELECT COUNT(*)/2 c FROM reairs WHERE kind = ?", (kind,)).fetchone()["c"]
        label = {"cross_show": "ran on multiple programs",
                 "encore": "encore of an earlier episode",
                 "repeat": "repeated within one show"}[kind]
        print(f"  {n:3}  {label}")
    print(f"  {groups} titles involved\n")

    print("Mentions — hyperlinks the producers already put in the show notes")
    total, kept, dropped, cutoff = build_mentions(conn)
    print(f"  {total} links across the archive")
    print(f"  {kept} distinct entities kept")
    print(f"  {dropped} treated as boilerplate (on >= {cutoff} episodes)\n")

    top = conn.execute(
        """SELECT text, COUNT(DISTINCT episode_id) n FROM mentions
           WHERE is_boilerplate = 0
           GROUP BY norm_text ORDER BY n DESC, text LIMIT 10"""
    ).fetchall()
    print("  most-linked entities:")
    for t in top:
        print(f"    {t['n']:2}  {t['text'][:56]}")

    conn.close()


if __name__ == "__main__":
    main()
