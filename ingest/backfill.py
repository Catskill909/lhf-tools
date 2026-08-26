#!/usr/bin/env python3
"""
Labor Heritage Media Archive — complete Podbean public-archive backfill.

RSS remains the ongoing source for new episodes, but Podbean caps each RSS feed
at 100 items. Its public `/page/N/` archive exposes the complete published
catalogue. This one-time recovery command imports that history without storing
audio and is safe to resume or rerun.

    python3 ingest/backfill.py

Run the normal downstream passes afterwards:

    python3 refresh.py
    python3 ingest/enrich.py

Stdlib only. Existing RSS rows are matched by their stable episode permalink,
so the page source's lack of RSS GUIDs cannot create duplicates.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urljoin

import ingest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))
USER_AGENT = "LHF-Podcast-Archive/0.1 (+historical-backfill)"
PAUSE_SEC = 0.15
PAGE_GUID_PREFIX = "podbean-page:"
POWER_HOUR_FIRST_DATE = "2023-04-14"

POWER_HOUR = {
    "slug": "power-hour",
    "name": "Labor Heritage Power Hour",
    "feed_url": "https://feed.podbean.com/yourrightsatwork/feed.xml",
    "site_url": "https://yourrightsatwork.podbean.com",
    "description": "A weekly radio show produced by the Labor Heritage Foundation.",
}
YOUR_RIGHTS = {
    "slug": "your-rights-at-work",
    "name": "Your Rights at Work",
    "feed_url": "https://feed.podbean.com/yourrightsatwork/feed.xml",
    "site_url": "https://yourrightsatwork.podbean.com",
    "description": "The precursor program to Labor Heritage Power Hour.",
}
LABOR_HISTORY = {
    "slug": "labor-history-today",
    "name": "Labor History Today",
    "feed_url": "https://feed.podbean.com/laborhistorytoday/feed.xml",
    "site_url": "https://laborhistorytoday.podbean.com",
    "description": "Labor history podcast produced by the Labor Heritage Foundation.",
}

ARCHIVES = [
    {
        "name": "Labor Heritage Power Hour + Your Rights at Work",
        "base_url": "https://yourrightsatwork.podbean.com",
        "expected_first": "Coronavirus and worker rights",
    },
    {
        "name": "Labor History Today",
        "base_url": "https://laborhistorytoday.podbean.com",
        "expected_first": (
            "Our First Show: Black Tuesday, Philly's General Strike & "
            "Debs Gets a Million Votes"
        ),
    },
]

STATE_RE = re.compile(
    r"<script[^>]*>\s*window\.__INITIAL_STATE__\s*=\s*(\".*?\")\s*</script>",
    re.DOTALL,
)
LD_JSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def fetch_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    return data.decode("utf-8", "replace")


def parse_page(raw):
    """Return `(episodes, total_pages, total_count, page)` from Podbean HTML."""
    match = STATE_RE.search(raw)
    if not match:
        raise ValueError("Podbean page has no window.__INITIAL_STATE__ payload")
    try:
        # Podbean serializes the state as a JSON string containing JSON.
        state = json.loads(json.loads(match.group(1)))
        store = state["store"]
        episodes = store["listEpisodes"]
        total_pages = int(store["listTotalPage"])
        total_count = int(store["listTotalCount"])
        page = int(store["listPage"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable Podbean page state: {exc}") from exc
    if not isinstance(episodes, list):
        raise ValueError("Podbean listEpisodes is not a list")

    # The Unix timestamp is absolute, while the catalogue date shown by
    # Podbean is the publisher's local date. A late-evening Eastern release can
    # cross midnight in UTC (the first LHT show is the real example), so use
    # the standard JSON-LD datePublished value for display and sorting.
    ld_match = LD_JSON_RE.search(raw)
    if ld_match:
        try:
            ld_rows = json.loads(ld_match.group(1))
            if isinstance(ld_rows, dict):
                ld_rows = [ld_rows]
            dates = {
                str(item.get("url") or "").rstrip("/"): item.get("datePublished")
                for item in ld_rows
                if isinstance(item, dict)
                and item.get("@type") == "PodcastEpisode"
                and item.get("url")
                and item.get("datePublished")
            }
            for episode in episodes:
                key = str(episode.get("permalink") or "").rstrip("/")
                if key in dates:
                    episode["_datePublished"] = dates[key]
        except (TypeError, ValueError, json.JSONDecodeError):
            # Initial state still carries a timestamp. JSON-LD is preferred for
            # its local date, but a malformed optional block must not erase the
            # usable catalogue payload.
            pass
    return episodes, total_pages, total_count, page


def published_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()


def published_date(episode):
    return episode.get("_datePublished") or published_iso(
        episode["publishTimestamp"]
    )[:10]


def show_for(archive, episode):
    if archive["base_url"] == LABOR_HISTORY["site_url"]:
        return LABOR_HISTORY
    if published_date(episode) >= POWER_HOUR_FIRST_DATE:
        return POWER_HOUR
    return YOUR_RIGHTS


def transcript_type(url):
    path = (url or "").lower().split("?", 1)[0]
    if path.endswith(".srt"):
        return "application/srt"
    if path.endswith(".json"):
        return "application/json"
    return None


def ensure_show(conn, show):
    conn.execute(
        """
        INSERT INTO shows (slug, name, feed_url, site_url, description)
        VALUES (:slug, :name, :feed_url, :site_url, :description)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            feed_url = excluded.feed_url,
            site_url = COALESCE(shows.site_url, excluded.site_url),
            description = COALESCE(shows.description, excluded.description)
        """,
        show,
    )
    return conn.execute(
        "SELECT id FROM shows WHERE slug = ?", (show["slug"],)
    ).fetchone()["id"]


def page_row(archive, episode, show_id):
    required = ("id", "title", "publishTimestamp", "duration", "mediaUrl", "permalink")
    missing = [key for key in required if episode.get(key) in (None, "")]
    if missing:
        raise ValueError(
            f"episode {episode.get('id', '(unknown)')} lacks {', '.join(missing)}"
        )
    tx_url = episode.get("transcriptUrl") or None
    return {
        "show_id": show_id,
        "guid": f"{PAGE_GUID_PREFIX}{episode['id']}",
        "title": episode["title"],
        "published_at": published_date(episode),
        "duration_sec": int(episode["duration"]),
        "episode_url": urljoin(archive["base_url"], episode["permalink"]),
        "audio_url": episode["mediaUrl"],
        "image_url": episode.get("largeLogo") or episode.get("logo"),
        "description_html": episode.get("previewContent") or "",
        "description_text": ingest.strip_html(episode.get("previewContent") or ""),
        "is_encore": 1 if ingest.ENCORE_RE.search(episode["title"]) else 0,
        "transcript_url": tx_url,
        "transcript_type": transcript_type(tx_url),
    }


def find_existing(conn, row):
    by_url = conn.execute(
        """SELECT * FROM episodes
           WHERE RTRIM(episode_url, '/') = RTRIM(?, '/') LIMIT 1""",
        (row["episode_url"],),
    ).fetchone()
    by_guid = conn.execute(
        "SELECT * FROM episodes WHERE guid = ?", (row["guid"],)
    ).fetchone()
    if by_url and by_guid and by_url["id"] != by_guid["id"]:
        raise ValueError(
            f"episode identity conflict for {row['episode_url']}: "
            f"URL row {by_url['id']}, GUID row {by_guid['id']}"
        )
    return by_url or by_guid


def upsert_page_episode(conn, archive, episode, show_id):
    """Insert one page episode or safely merge it into an RSS-sourced row."""
    row = page_row(archive, episode, show_id)
    existing = find_existing(conn, row)
    if not existing:
        conn.execute(
            """
            INSERT INTO episodes (
                show_id, guid, title, published_at, duration_sec, episode_url,
                audio_url, image_url, description_html, description_text,
                is_encore, transcript_url, transcript_type, transcript_status
            ) VALUES (
                :show_id, :guid, :title, :published_at, :duration_sec,
                :episode_url, :audio_url, :image_url, :description_html,
                :description_text, :is_encore, :transcript_url,
                :transcript_type, :transcript_status
            )
            """,
            {
                **row,
                "transcript_status": "pending" if row["transcript_url"] else "missing",
            },
        )
        return "inserted", False

    updates = {}
    reclassified = existing["show_id"] != row["show_id"]
    if reclassified:
        updates["show_id"] = row["show_id"]

    page_owned = (existing["guid"] or "").startswith(PAGE_GUID_PREFIX)
    for key in (
        "title", "published_at", "duration_sec", "episode_url", "audio_url",
        "image_url", "description_html", "description_text", "is_encore",
        "transcript_url", "transcript_type",
    ):
        new = row[key]
        old = existing[key]
        # Refresh values on rows created by this importer. RSS-created rows are
        # ground truth and only accept values that RSS did not provide.
        should_take = page_owned or old in (None, "")
        if should_take and new not in (None, "") and new != old:
            updates[key] = new

    if row["transcript_url"] and existing["transcript_status"] == "missing":
        updates["transcript_status"] = "pending"

    if updates:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE episodes SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            (*updates.values(), existing["id"]),
        )
        return "updated", reclassified
    return "matched", reclassified


def connect():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ingest.init_schema(conn)
    return conn


def run(conn, limit_pages=None, pause=PAUSE_SEC):
    show_ids = {
        show["slug"]: ensure_show(conn, show)
        for show in (POWER_HOUR, YOUR_RIGHTS, LABOR_HISTORY)
    }
    conn.commit()

    totals = {"inserted": 0, "updated": 0, "matched": 0, "reclassified": 0}
    for archive in ARCHIVES:
        print(f"\n{archive['name']}")
        first_html = fetch_page(f"{archive['base_url']}/page/1/")
        first_rows, page_count, expected_count, returned_page = parse_page(first_html)
        if returned_page != 1:
            raise ValueError(f"Podbean returned page {returned_page} for page 1")
        pages_to_read = min(page_count, limit_pages) if limit_pages else page_count
        print(f"  {expected_count} episodes across {page_count} pages")

        seen = set()
        oldest_episode = None
        for page in range(1, pages_to_read + 1):
            if page == 1:
                episodes = first_rows
            else:
                raw = fetch_page(f"{archive['base_url']}/page/{page}/")
                episodes, pages_now, count_now, returned_page = parse_page(raw)
                if returned_page != page:
                    raise ValueError(
                        f"Podbean returned page {returned_page} for page {page}"
                    )
                if pages_now != page_count or count_now != expected_count:
                    raise ValueError(
                        "Podbean archive changed during the run; rerun to get a "
                        "consistent page set"
                    )

            counts = {"inserted": 0, "updated": 0, "matched": 0}
            for episode in episodes:
                source_id = str(episode.get("id") or "")
                if not source_id or source_id in seen:
                    continue
                seen.add(source_id)
                if (
                    oldest_episode is None
                    or int(episode["publishTimestamp"])
                    < int(oldest_episode["publishTimestamp"])
                ):
                    oldest_episode = episode
                show = show_for(archive, episode)
                action, reclassified = upsert_page_episode(
                    conn, archive, episode, show_ids[show["slug"]]
                )
                counts[action] += 1
                totals[action] += 1
                if reclassified:
                    totals["reclassified"] += 1
            conn.commit()
            print(
                f"  page {page:>2}/{pages_to_read}: "
                f"{counts['inserted']} new, {counts['updated']} updated, "
                f"{counts['matched']} matched"
            )
            if page < pages_to_read and pause:
                time.sleep(pause)

        if not limit_pages:
            if len(seen) != expected_count:
                raise ValueError(
                    f"expected {expected_count} unique episodes, parsed {len(seen)}"
                )
            first_title = oldest_episode["title"] if oldest_episode else None
            if first_title != archive["expected_first"]:
                raise ValueError(
                    f"oldest episode mismatch: {first_title!r}; expected "
                    f"{archive['expected_first']!r}"
                )

    print(
        f"\nTotal: {totals['inserted']} new, {totals['updated']} updated, "
        f"{totals['matched']} matched, {totals['reclassified']} reclassified"
    )
    print(f"Database: {DB_PATH}")
    return totals


def main():
    ap = argparse.ArgumentParser(
        description="Backfill the complete published Podbean archive"
    )
    ap.add_argument(
        "--limit-pages", type=int, metavar="N",
        help="development check: read only the first N pages of each archive",
    )
    ap.add_argument(
        "--no-pause", action="store_true",
        help="do not pause briefly between public archive pages",
    )
    args = ap.parse_args()
    if args.limit_pages is not None and args.limit_pages < 1:
        ap.error("--limit-pages must be at least 1")

    conn = connect()
    try:
        run(conn, limit_pages=args.limit_pages, pause=0 if args.no_pause else PAUSE_SEC)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
