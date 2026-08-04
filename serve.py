#!/usr/bin/env python3
"""
LHF Digital Asset Manager — local search server.

Stdlib only. No pip install, no venv:

    python3 serve.py            # http://localhost:8000
    python3 serve.py --port 9000

Swap to FastAPI later without touching the front end — the JSON contract
(/api/search, /api/facets) is what the UI talks to.
"""

import argparse
import json
import os
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))
STATIC = os.path.join(ROOT, "static")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    """Attach re-airs, tags, and (when searching) matching spoken moments."""
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
        else:
            r["excerpt"], r["excerpt_from"] = desc, "description"
    ids = [r["id"] for r in out]
    marks = ",".join("?" * len(ids))
    by_id = {r["id"]: r for r in out}
    for r in out:
        r["reairs"], r["mentions"], r["moments"] = [], [], []

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

    # Matching moments: the passage-level index tells us *where* in the audio
    # the phrase occurs, which is what a timestamp link needs.
    if match:
        for r in out:
            r["moments"] = []
        try:
            for m in conn.execute(
                f"""SELECT s.episode_id, s.start_sec, s.text,
                           snippet(segments_fts, 0, '<mark>', '</mark>', '…', 18) AS excerpt
                    FROM segments_fts f
                    JOIN segments s ON s.id = f.rowid
                    WHERE segments_fts MATCH ? AND s.episode_id IN ({marks})
                    ORDER BY s.episode_id, rank""", [match] + ids):
                bucket = by_id[m["episode_id"]]["moments"]
                if len(bucket) < 3:
                    bucket.append({"start_sec": m["start_sec"], "excerpt": m["excerpt"]})
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
    "relevance": "rank",
    "newest":    "e.published_at DESC",
    "oldest":    "e.published_at ASC",
    "title":     "e.title COLLATE NOCASE ASC",
    "longest":   "e.duration_sec DESC NULLS LAST",
    "shortest":  "e.duration_sec ASC NULLS LAST",
}


def search(conn, q="", show=None, year=None, encore=None, person=None,
           sort=None, limit=200):
    where, params = [], []

    match = fts_query(q)
    if match:
        sql = """
            SELECT e.id, e.title, e.published_at, e.duration_sec, e.episode_url,
                   e.audio_url, e.is_encore, s.name AS show_name, s.slug AS show_slug,
                   snippet(episodes_fts, 1, '<mark>', '</mark>', '…', 28) AS snip_desc,
                   snippet(episodes_fts, 2, '<mark>', '</mark>', '…', 28) AS snip_tx,
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
                   substr(e.description_text, 1, 240) AS snip_desc,
                   NULL AS snip_tx,
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
        where.append(
            "e.id IN (SELECT episode_id FROM mentions "
            "WHERE norm_text = ? AND is_boilerplate = 0)")
        params.append(person)

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
        rows = conn.execute(f"{sql} {order} LIMIT ?", params + [limit]).fetchall()
    except sqlite3.OperationalError as exc:
        return {"error": f"search error: {exc}", "results": [], "count": 0, "total": 0}

    return {
        "count": len(rows),
        "total": total,
        "truncated": total > len(rows),
        "query": q,
        "sort": key,
        "results": decorate(conn, rows, match),
    }


def entities(conn, limit=400):
    rows = conn.execute(
        """SELECT text, norm_text, COUNT(DISTINCT episode_id) AS n,
                  MAX(url) AS url
           FROM mentions WHERE is_boilerplate = 0
           GROUP BY norm_text
           ORDER BY n DESC, text COLLATE NOCASE
           LIMIT ?""", (limit,)).fetchall()
    return {"count": len(rows), "entities": [dict(r) for r in rows]}


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
    return {
        "shows": [dict(r) for r in shows],
        "years": [dict(r) for r in years],
        "totals": dict(totals),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):        # quieter console
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
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
                data = search(
                    conn,
                    q=one("q") or "",
                    show=one("show"),
                    year=one("year"),
                    encore=one("encore"),
                    person=one("person"),
                    sort=one("sort"),
                    limit=min(int(one("limit") or 200), 1000),
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

        if path == "/api/facets":
            conn = connect()
            try:
                data = facets(conn)
            finally:
                conn.close()
            return self._send(200, json.dumps(data))

        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(STATIC, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._send(404, b"static/index.html missing", "text/plain")

        return self._send(404, json.dumps({"error": "not found"}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        raise SystemExit(
            f"No database at {DB_PATH}\nRun:  python3 ingest/ingest.py"
        )

    conn = connect()
    n = conn.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
    conn.close()

    print(f"LHF Digital Asset Manager — {n} episodes")
    print(f"  http://localhost:{args.port}")
    print("  ctrl-c to stop")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
