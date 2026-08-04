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
import csv
import io
import json
import os
import re
import sqlite3
from datetime import date
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


# ---------------------------------------------------------------- export

# One row per episode keeps the sheet pivotable. Header names carry units so
# the values can stay numeric (54, not "54 min") and remain sortable/summable.
EXPORT_COLUMNS = [
    ("show",             "Show"),
    ("title",            "Title"),
    ("published",        "Published"),
    ("duration_min",     "Duration (min)"),
    ("is_encore",        "Encore"),
    ("tags",             "Tags"),
    ("reair_dates",      "Also aired"),
    ("has_transcript",   "Transcript"),
    ("transcript_words", "Words"),
    ("episode_url",      "Episode page"),
    ("source_url",       "Source transcript"),
    ("archive_url",      "Archive transcript"),
    ("audio_url",        "Audio"),
]


def export_rows(conn, base_url, **kw):
    """Flatten search results into spreadsheet-shaped rows."""
    kw.setdefault("limit", 5000)
    data = search(conn, **kw)
    if data.get("error"):
        return None, data["error"]

    ids = [r["id"] for r in data["results"]]
    words, src = {}, {}
    if ids:
        marks = ",".join("?" * len(ids))
        for r in conn.execute(
            f"""SELECT id, transcript_url,
                       CASE WHEN transcript_text IS NULL THEN 0
                            ELSE LENGTH(transcript_text)
                                 - LENGTH(REPLACE(transcript_text,' ','')) + 1 END AS w
                FROM episodes WHERE id IN ({marks})""", ids):
            words[r["id"]] = r["w"]
            src[r["id"]] = r["transcript_url"]

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
            "tags": "; ".join(m["text"] for m in r.get("mentions", [])),
            "reair_dates": "; ".join(
                (a["published_at"] or "")[:10] for a in r.get("reairs", [])),
            "has_transcript": "TRUE" if has_tx else "FALSE",
            "transcript_words": words.get(r["id"]) or "",
            "episode_url": r["episode_url"] or "",
            "source_url": src.get(r["id"]) or "",
            "archive_url": f"{base_url}/episode/{r['id']}/transcript" if has_tx else "",
            "audio_url": r["audio_url"] or "",
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

        if path == "/api/export":
            fmt = (one("format") or "csv").lower()
            conn = connect()
            try:
                rows, err = export_rows(
                    conn, f"http://{self.headers.get('Host', 'localhost:8000')}",
                    q=one("q") or "", show=one("show"), year=one("year"),
                    encore=one("encore"), person=one("person"), sort=one("sort"))
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
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)

        # One episode, for shared moment links (?ep=&from=&to=) that open the
        # clip editor without running a search first.
        m = re.fullmatch(r"/api/episode/(\d+)", path)
        if m:
            conn = connect()
            try:
                row = conn.execute(
                    """SELECT e.id, e.title, e.published_at, e.duration_sec,
                              e.audio_url, e.episode_url, s.name AS show_name
                       FROM episodes e JOIN shows s ON s.id = e.show_id
                       WHERE e.id = ?""", (int(m.group(1)),)).fetchone()
            finally:
                conn.close()
            if not row:
                return self._send(404, json.dumps({"error": "no such episode"}))
            return self._send(200, json.dumps(dict(row)))

        m = re.fullmatch(r"/episode/(\d+)/transcript", path)
        if m:
            conn = connect()
            try:
                row = conn.execute(
                    """SELECT e.title, e.published_at, e.transcript_text, s.name AS show
                       FROM episodes e JOIN shows s ON s.id = e.show_id
                       WHERE e.id = ?""", (int(m.group(1)),)).fetchone()
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
    print(f"LHF Digital Asset Manager — {n} episodes")
    print(f"  http://{shown}:{args.port}  (bound to {args.host})")
    print("  ctrl-c to stop")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
