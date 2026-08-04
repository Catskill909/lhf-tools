#!/usr/bin/env python3
"""
LHF Podcast Archive — RSS ingest.

Pulls both Podbean feeds into SQLite. Idempotent: keys on the RSS <guid>,
so re-running updates existing rows rather than duplicating them.

Stdlib only — no pip install required.

    python3 ingest/ingest.py            # ingest both shows
    python3 ingest/ingest.py --stats    # show what's in the database
"""

import argparse
import html
import os
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))
SCHEMA_PATH = os.path.join(HERE, "schema.sql")

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}

SHOWS = [
    {
        "slug": "power-hour",
        "name": "Labor Heritage Power Hour",
        "feed_url": "https://feed.podbean.com/yourrightsatwork/feed.xml",
    },
    {
        "slug": "labor-history-today",
        "name": "Labor History Today",
        "feed_url": "https://feed.podbean.com/laborhistorytoday/feed.xml",
    },
]

USER_AGENT = "LHF-Podcast-Archive/0.1 (+ingest)"


# ---------------------------------------------------------------- helpers

class _Stripper(HTMLParser):
    """Turn description HTML into readable plain text for search/extraction."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "br", "div", "li"):
            self.parts.append("\n")

    def text(self):
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def strip_html(value):
    if not value:
        return ""
    p = _Stripper()
    p.feed(html.unescape(value))
    return p.text()


def parse_duration(value):
    """iTunes duration is either seconds, MM:SS, or HH:MM:SS."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    parts = value.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def parse_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


ENCORE_RE = re.compile(r"\bencore\b", re.IGNORECASE)


def text_of(node, path, default=None):
    if node is None:
        return default
    found = node.find(path, NS) if ":" in path else node.find(path)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


# ---------------------------------------------------------------- database

def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    with open(SCHEMA_PATH) as fh:
        conn.executescript(fh.read())
    conn.commit()


def upsert_show(conn, show, channel):
    conn.execute(
        """
        INSERT INTO shows (slug, name, feed_url, site_url, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            feed_url = excluded.feed_url,
            site_url = excluded.site_url,
            description = excluded.description
        """,
        (
            show["slug"],
            text_of(channel, "title") or show["name"],
            show["feed_url"],
            text_of(channel, "link"),
            strip_html(text_of(channel, "description")),
        ),
    )
    row = conn.execute("SELECT id FROM shows WHERE slug = ?", (show["slug"],)).fetchone()
    return row["id"]


def upsert_episode(conn, show_id, item):
    guid = text_of(item, "guid")
    title = text_of(item, "title") or text_of(item, "itunes:title") or "(untitled)"
    if not guid:
        # Fall back to the episode page URL — better than dropping the row,
        # but log it, because a feed without stable GUIDs will churn.
        guid = text_of(item, "link")
        if not guid:
            return None, "skipped"

    description_html = text_of(item, "description") or text_of(item, "content:encoded") or ""
    description_text = strip_html(description_html)

    enclosure = item.find("enclosure")
    audio_url = enclosure.get("url") if enclosure is not None else None

    image = item.find("itunes:image", NS)
    image_url = image.get("href") if image is not None else None

    # Prefer SRT; a couple of episodes offer JSON instead.
    tx_url = tx_type = None
    tx = item.findall("podcast:transcript", NS)
    if tx:
        pick = next((t for t in tx if "srt" in (t.get("type") or "").lower()), tx[0])
        tx_url, tx_type = pick.get("url"), pick.get("type")

    row = {
        "show_id": show_id,
        "guid": guid,
        "title": title,
        "published_at": parse_date(text_of(item, "pubDate")),
        "duration_sec": parse_duration(text_of(item, "itunes:duration")),
        "episode_url": text_of(item, "link"),
        "audio_url": audio_url,
        "image_url": image_url,
        "description_html": description_html,
        "description_text": description_text,
        "is_encore": 1 if ENCORE_RE.search(title) else 0,
        "transcript_url": tx_url,
        "transcript_type": tx_type,
    }

    existing = conn.execute("SELECT id FROM episodes WHERE guid = ?", (guid,)).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE episodes SET
                show_id = :show_id, title = :title, published_at = :published_at,
                duration_sec = :duration_sec, episode_url = :episode_url,
                audio_url = :audio_url, image_url = :image_url,
                description_html = :description_html,
                description_text = :description_text,
                is_encore = :is_encore,
                transcript_url = :transcript_url,
                transcript_type = :transcript_type,
                updated_at = datetime('now')
            WHERE guid = :guid
            """,
            row,
        )
        return existing["id"], "updated"

    cur = conn.execute(
        """
        INSERT INTO episodes (
            show_id, guid, title, published_at, duration_sec, episode_url,
            audio_url, image_url, description_html, description_text, is_encore,
            transcript_url, transcript_type
        ) VALUES (
            :show_id, :guid, :title, :published_at, :duration_sec, :episode_url,
            :audio_url, :image_url, :description_html, :description_text, :is_encore,
            :transcript_url, :transcript_type
        )
        """,
        row,
    )
    return cur.lastrowid, "inserted"


# ---------------------------------------------------------------- commands

def ingest(conn):
    totals = {"inserted": 0, "updated": 0, "skipped": 0}

    for show in SHOWS:
        print(f"\n{show['name']}")
        print(f"  fetching {show['feed_url']}")
        try:
            raw = fetch(show["feed_url"])
        except Exception as exc:                       # noqa: BLE001
            print(f"  ERROR fetching feed: {exc}", file=sys.stderr)
            continue

        root = ET.fromstring(raw)
        channel = root.find("channel")
        if channel is None:
            print("  ERROR: no <channel> in feed", file=sys.stderr)
            continue

        show_id = upsert_show(conn, show, channel)
        items = channel.findall("item")
        print(f"  {len(items)} episodes in feed")

        counts = {"inserted": 0, "updated": 0, "skipped": 0}
        for item in items:
            _, action = upsert_episode(conn, show_id, item)
            counts[action] += 1
            totals[action] += 1

        conn.commit()
        print(f"  {counts['inserted']} new, {counts['updated']} updated, "
              f"{counts['skipped']} skipped")

    print(f"\nTotal: {totals['inserted']} new, {totals['updated']} updated, "
          f"{totals['skipped']} skipped")
    print(f"Database: {DB_PATH}")


def stats(conn):
    print(f"Database: {DB_PATH}\n")
    rows = conn.execute(
        """
        SELECT s.name,
               COUNT(e.id)                     AS episodes,
               MIN(e.published_at)             AS earliest,
               MAX(e.published_at)             AS latest,
               ROUND(AVG(e.duration_sec)/60.0) AS avg_min,
               ROUND(SUM(e.duration_sec)/3600.0, 1) AS total_hours,
               SUM(e.is_encore)                AS encores
        FROM shows s LEFT JOIN episodes e ON e.show_id = s.id
        GROUP BY s.id ORDER BY s.name
        """
    ).fetchall()

    for r in rows:
        print(f"{r['name']}")
        print(f"  episodes    {r['episodes']}")
        print(f"  date range  {(r['earliest'] or '')[:10]} → {(r['latest'] or '')[:10]}")
        print(f"  avg length  {r['avg_min'] or 0:.0f} min")
        print(f"  total audio {r['total_hours'] or 0} hours")
        print(f"  encores     {r['encores'] or 0}")
        print()

    total = conn.execute("SELECT COUNT(*) c FROM episodes").fetchone()["c"]
    hours = conn.execute(
        "SELECT ROUND(SUM(duration_sec)/3600.0,1) h FROM episodes"
    ).fetchone()["h"]
    print(f"ALL: {total} episodes, {hours} hours of audio")

    if total:
        print("\nSearch sanity check — FTS5 query for 'strike':")
        hits = conn.execute(
            """
            SELECT e.title, substr(e.published_at,1,10) AS d
            FROM episodes_fts f JOIN episodes e ON e.id = f.rowid
            WHERE episodes_fts MATCH 'strike'
            ORDER BY rank LIMIT 5
            """
        ).fetchall()
        for h in hits:
            print(f"  {h['d']}  {h['title'][:60]}")
        print(f"  ({len(hits)} shown)")


def main():
    ap = argparse.ArgumentParser(description="Ingest LHF podcast feeds into SQLite")
    ap.add_argument("--stats", action="store_true", help="show database stats and exit")
    args = ap.parse_args()

    conn = connect()
    init_schema(conn)

    if args.stats:
        stats(conn)
    else:
        ingest(conn)
        print()
        stats(conn)

    conn.close()


if __name__ == "__main__":
    main()
