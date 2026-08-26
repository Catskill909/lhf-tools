#!/usr/bin/env python3
"""Pure tests for the Podbean public-archive backfill.

    python3 tests/test-backfill.py

No network and no files: representative Podbean page state is embedded below,
and SQLite runs in memory.
"""

import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ingest"))

import backfill  # noqa: E402
import ingest  # noqa: E402

failures = []


def check(name, got, want):
    if got == want:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")
        failures.append(name)


def fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(os.path.join(os.path.dirname(HERE), "ingest", "schema.sql")) as fh:
        conn.executescript(fh.read())
    ingest.migrate(conn)
    return conn


def episode(source_id="pb123", title="Historical episode", timestamp=1583434800,
            permalink="/e/historical-episode/", transcript=None):
    return {
        "id": source_id,
        "title": title,
        "publishTimestamp": timestamp,
        "duration": 3600,
        "mediaUrl": f"https://mcdn.podbean.com/{source_id}.mp3",
        "permalink": permalink,
        "largeLogo": f"https://pbcdn1.podbean.com/{source_id}.jpg",
        "previewContent": "A <b>complete</b> description.",
        "transcriptUrl": transcript,
    }


def page_html(rows, page=1, pages=2, count=12):
    state = {"store": {
        "listEpisodes": rows,
        "listTotalPage": pages,
        "listTotalCount": count,
        "listPage": page,
    }}
    # Podbean writes JSON inside a JavaScript JSON string.
    payload = json.dumps(json.dumps(state, separators=(",", ":")))
    ld_rows = [
        {
            "@type": "PodcastEpisode",
            "url": row["permalink"],
            "datePublished": "2020-03-05",
        }
        for row in rows
    ]
    return (
        '<html><script type="application/ld+json">'
        f'{json.dumps(ld_rows)}</script>'
        f'<script>window.__INITIAL_STATE__={payload}</script></html>'
    )


print("\nPodbean page parsing")
rows, pages, count, page = backfill.parse_page(page_html([episode()]))
check("the episode list is decoded", rows[0]["id"], "pb123")
check("the advertised page count is decoded", pages, 2)
check("the advertised episode count is decoded", count, 12)
check("the returned page is decoded", page, 1)
check("the publisher-local JSON-LD date is retained",
      rows[0]["_datePublished"], "2020-03-05")

try:
    backfill.parse_page("<html>changed markup</html>")
except ValueError:
    changed_markup_failed = True
else:
    changed_markup_failed = False
check("changed Podbean markup fails loudly", changed_markup_failed, True)


print("\nProgram classification")
combined = backfill.ARCHIVES[0]
lht = backfill.ARCHIVES[1]
check("the first Power Hour date belongs to Power Hour",
      backfill.show_for(combined, episode(timestamp=1681499940))["slug"],
      "power-hour")
check("the preceding day belongs to Your Rights at Work",
      backfill.show_for(combined, episode(timestamp=1681344000))["slug"],
      "your-rights-at-work")
check("the Labor History archive always stays Labor History Today",
      backfill.show_for(lht, episode(timestamp=1681499940))["slug"],
      "labor-history-today")


print("\nInsert and rerun")
conn = fresh_db()
yraw_id = backfill.ensure_show(conn, backfill.YOUR_RIGHTS)
action, moved = backfill.upsert_page_episode(conn, combined, episode(), yraw_id)
row = conn.execute("SELECT * FROM episodes").fetchone()
check("a historical page episode is inserted", action, "inserted")
check("its synthetic identity is explicit", row["guid"], "podbean-page:pb123")
check("an absent transcript is recorded as a known gap", row["transcript_status"], "missing")
check("HTML is retained", row["description_html"], "A <b>complete</b> description.")
check("search text is stripped", row["description_text"], "A complete description.")

action, moved = backfill.upsert_page_episode(conn, combined, episode(), yraw_id)
check("an unchanged rerun is a no-op", action, "matched")
check("a rerun creates no duplicate", conn.execute(
    "SELECT COUNT(*) FROM episodes").fetchone()[0], 1)

with_tx = episode(transcript="https://mcdn.podbean.com/pb123.srt")
action, moved = backfill.upsert_page_episode(conn, combined, with_tx, yraw_id)
row = conn.execute("SELECT * FROM episodes").fetchone()
check("a newly published transcript is noticed", row["transcript_url"],
      "https://mcdn.podbean.com/pb123.srt")
check("a newly published transcript returns to the queue",
      row["transcript_status"], "pending")


print("\nRSS and public-page identity reconciliation")
conn = fresh_db()
ph_id = backfill.ensure_show(conn, backfill.POWER_HOUR)
yraw_id = backfill.ensure_show(conn, backfill.YOUR_RIGHTS)

# Simulate a row that originally came from RSS under the channel's current name.
rss_item = ET.fromstring(
    "<item><guid>rss-original-guid</guid><title>RSS title wins</title>"
    "<pubDate>Thu, 13 Apr 2023 14:00:00 GMT</pubDate>"
    "<link>https://yourrightsatwork.podbean.com/e/shared/</link>"
    "<enclosure url='https://mcdn.podbean.com/rss.mp3'/></item>"
)
ingest.upsert_episode(conn, ph_id, rss_item, "2026-08-01 00:00:00")

public = episode(
    source_id="pb-shared", title="Page title",
    timestamp=1681394400, permalink="/e/shared/",
)
action, moved = backfill.upsert_page_episode(conn, combined, public, yraw_id)
row = conn.execute("SELECT * FROM episodes").fetchone()
check("the permalink matches the existing RSS row", conn.execute(
    "SELECT COUNT(*) FROM episodes").fetchone()[0], 1)
check("the RSS GUID is preserved", row["guid"], "rss-original-guid")
check("the RSS title remains ground truth", row["title"], "RSS title wins")
check("the historical row is assigned to the precursor program", row["show_id"], yraw_id)
check("the reassignment is reported", moved, True)

# The opposite order matters for a fresh database: page first, then RSS.
conn = fresh_db()
ph_id = backfill.ensure_show(conn, backfill.POWER_HOUR)
page_current = episode(
    source_id="pb-current", title="Page title", timestamp=1681499940,
    permalink="/e/current/",
)
backfill.upsert_page_episode(conn, combined, page_current, ph_id)
rss_current = ET.fromstring(
    "<item><guid>real-rss-guid</guid><title>Current RSS title</title>"
    "<pubDate>Fri, 14 Apr 2023 18:00:00 GMT</pubDate>"
    "<link>https://yourrightsatwork.podbean.com/e/current/</link>"
    "<enclosure url='https://mcdn.podbean.com/current-rss.mp3'/></item>"
)
ingest.upsert_episode(conn, ph_id, rss_current, "2026-08-01 00:00:00")
row = conn.execute("SELECT * FROM episodes").fetchone()
check("RSS claims a page-first row without duplicating it", conn.execute(
    "SELECT COUNT(*) FROM episodes").fetchone()[0], 1)
check("the synthetic GUID is upgraded to the RSS GUID", row["guid"], "real-rss-guid")
check("RSS metadata replaces page metadata", row["title"], "Current RSS title")
check("RSS appearance stamps the reclaimed row", row["last_seen_in_feed"],
      "2026-08-01 00:00:00")


print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    sys.exit(1)
print("All backfill tests passed.")
