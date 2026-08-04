#!/usr/bin/env python3
"""
LHF Podcast Archive — transcript ingest from the podcast feed.

145 of 200 episodes publish a full .srt via the Podcast 2.0
<podcast:transcript> tag. This fetches and parses them into `segments`.

Descript is a *source*, never a dependency: we read the feed, store the parsed
text locally, and never touch a vendor API. If LHF changes editors, nothing
here breaks. If the CDN URLs rot, we already have the text.

    python3 ingest/transcripts.py              # fetch everything outstanding
    python3 ingest/transcripts.py --limit 5    # try a few first
    python3 ingest/transcripts.py --stats      # coverage only
    python3 ingest/transcripts.py --retry      # re-attempt previous failures

Stdlib only.
"""

import argparse
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))

USER_AGENT = "LHF-Podcast-Archive/0.1 (+transcripts)"

# One at a time with a pause. The box shares an uplink with everything else
# Coolify is running, and there is no deadline here.
PAUSE_SEC = 0.4

# A cue averages ~5 words, so indexing them raw would break phrase searches
# across cue boundaries and produce useless snippets. Merge into passages.
PASSAGE_SEC = 25.0
PASSAGE_MAX_WORDS = 90

TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
TAG_RE = re.compile(r"<[^>]+>")


def secs(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt(raw):
    """SRT -> [(start_sec, end_sec, text)]. Tolerates WEBVTT headers and CRLF."""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"^﻿", "", raw)
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        block = block.strip()
        if not block or block.upper().startswith("WEBVTT"):
            continue
        m = TIME_RE.search(block)
        if not m:
            continue
        start = secs(*m.group(1, 2, 3, 4))
        end = secs(*m.group(5, 6, 7, 8))
        # Text is whatever follows the timing line
        lines = block[m.end():].strip().split("\n")
        text = " ".join(l.strip() for l in lines if l.strip())
        text = TAG_RE.sub("", text).strip()
        if text:
            cues.append((start, end, text))
    return cues


def to_passages(cues):
    """Merge short cues into ~25s passages so phrase search and snippets work."""
    out, buf = [], []
    for start, end, text in cues:
        if not buf:
            buf = [start, end, [text]]
            continue
        words = sum(len(t.split()) for t in buf[2])
        if (end - buf[0] >= PASSAGE_SEC) or words >= PASSAGE_MAX_WORDS:
            out.append((buf[0], buf[1], " ".join(buf[2])))
            buf = [start, end, [text]]
        else:
            buf[1] = end
            buf[2].append(text)
    if buf:
        out.append((buf[0], buf[1], " ".join(buf[2])))
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # Podbean 302-redirects transcript URLs; urlopen follows by default, but
    # a naive fetch that doesn't will silently get 0 bytes.
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def connect():
    if not os.path.exists(DB_PATH):
        sys.exit(f"No database at {DB_PATH}\nRun:  python3 ingest/ingest.py")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def coverage(conn):
    rows = conn.execute("""
        SELECT s.name,
               COUNT(*) AS total,
               SUM(e.transcript_url IS NOT NULL) AS has_url,
               SUM(e.transcript_status = 'done') AS done,
               SUM(e.transcript_status = 'failed') AS failed
        FROM episodes e JOIN shows s ON s.id = e.show_id
        GROUP BY s.id ORDER BY s.name""").fetchall()
    print("\nCoverage")
    for r in rows:
        print(f"  {r['name']}")
        print(f"    {r['done'] or 0}/{r['total']} transcribed "
              f"({r['has_url'] or 0} available in feed"
              f"{', ' + str(r['failed']) + ' failed' if r['failed'] else ''})")
    seg = conn.execute("SELECT COUNT(*) c FROM segments").fetchone()["c"]
    words = conn.execute(
        "SELECT SUM(LENGTH(transcript_text) - LENGTH(REPLACE(transcript_text,' ',''))) w "
        "FROM episodes WHERE transcript_text IS NOT NULL").fetchone()["w"] or 0
    gap = conn.execute("""
        SELECT COUNT(*) n, COALESCE(SUM(duration_sec),0)/60.0 m FROM episodes
        WHERE transcript_url IS NULL""").fetchone()
    print(f"\n  {seg:,} passages · ~{int(words):,} words indexed")
    print(f"  {gap['n']} episodes have no feed transcript "
          f"({gap['m']:.0f} min → ~${gap['m']*0.004:.2f} via Google STT)")


def run(conn, limit=None, retry=False):
    states = "('pending','failed')" if retry else "('pending')"
    rows = conn.execute(f"""
        SELECT id, title, transcript_url FROM episodes
        WHERE transcript_url IS NOT NULL
          AND transcript_status IN {states}
        ORDER BY published_at DESC""").fetchall()
    if limit:
        rows = rows[:limit]

    if not rows:
        print("Nothing outstanding.")
        return

    print(f"Fetching {len(rows)} transcript(s)…\n")
    ok = failed = 0
    for i, r in enumerate(rows, 1):
        label = r["title"][:46]
        try:
            cues = parse_srt(fetch(r["transcript_url"]))
            if not cues:
                raise ValueError("no cues parsed")
            passages = to_passages(cues)
            full = " ".join(t for _, _, t in passages)

            conn.execute("DELETE FROM segments WHERE episode_id = ?", (r["id"],))
            conn.executemany(
                "INSERT INTO segments (episode_id, start_sec, end_sec, text) "
                "VALUES (?,?,?,?)",
                [(r["id"], s, e, t) for s, e, t in passages])
            conn.execute("""
                UPDATE episodes SET transcript_text = ?, transcript_status = 'done',
                       transcript_source = 'feed', updated_at = datetime('now')
                WHERE id = ?""", (full, r["id"]))
            conn.commit()
            ok += 1
            print(f"  [{i}/{len(rows)}] {label:<48} "
                  f"{len(passages):>4} passages  {len(full.split()):>6,} words")
        except Exception as exc:                          # noqa: BLE001
            conn.execute(
                "UPDATE episodes SET transcript_status='failed' WHERE id = ?",
                (r["id"],))
            conn.commit()
            failed += 1
            print(f"  [{i}/{len(rows)}] {label:<48} FAILED: {exc}", file=sys.stderr)
        time.sleep(PAUSE_SEC)

    print(f"\n{ok} transcribed, {failed} failed")


def main():
    ap = argparse.ArgumentParser(description="Ingest feed transcripts (.srt)")
    ap.add_argument("--limit", type=int, help="only process N episodes")
    ap.add_argument("--retry", action="store_true", help="retry previous failures")
    ap.add_argument("--stats", action="store_true", help="coverage only, no fetching")
    args = ap.parse_args()

    conn = connect()
    # Episodes the feed offers no transcript for aren't 'pending', they're a
    # known gap — mark them so the queue reflects only real work.
    conn.execute("""UPDATE episodes SET transcript_status = 'missing'
                    WHERE transcript_url IS NULL AND transcript_status = 'pending'""")
    conn.commit()

    if not args.stats:
        run(conn, limit=args.limit, retry=args.retry)
    coverage(conn)
    conn.close()


if __name__ == "__main__":
    main()
