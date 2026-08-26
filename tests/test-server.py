#!/usr/bin/env python3
"""Pure server checks that depend on the complete historical archive size."""

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import serve  # noqa: E402

failures = []


def check(name, got, want):
    if got == want:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")
        failures.append(name)


conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
with open(os.path.join(ROOT, "ingest", "schema.sql")) as fh:
    conn.executescript(fh.read())
conn.execute(
    "INSERT INTO shows (slug, name, feed_url) VALUES (?,?,?)",
    ("archive", "Archive", "https://example.invalid/feed.xml"),
)
show_id = conn.execute("SELECT id FROM shows").fetchone()["id"]
conn.executemany(
    """INSERT INTO episodes
       (show_id, guid, title, published_at, episode_url, description_text)
       VALUES (?,?,?,?,?,?)""",
    [
        (
            show_id, f"guid-{i}", f"Episode {i:03}", f"2020-01-{(i % 28) + 1:02}",
            f"https://example.invalid/e/{i}/", "Description",
        )
        for i in range(785)
    ],
)

print("\nPaged complete-archive search")
first = serve.search(conn, sort="oldest")
second = serve.search(conn, sort="oldest", offset=serve.SEARCH_PAGE_SIZE)
last = serve.search(conn, sort="oldest", offset=750)

check("the browser-sized first page contains 50 episodes", first["count"], 50)
check("the full match count is still reported", first["total"], 785)
check("the first page reports more results", first["has_more"], True)
check("the next offset follows the returned rows", first["next_offset"], 50)
check("the second page starts at offset 50", second["offset"], 50)
check("adjacent pages do not overlap",
      bool({r["id"] for r in first["results"]}
           & {r["id"] for r in second["results"]}), False)
match_first = serve.search(conn, q="Description", sort="relevance")
match_second = serve.search(
    conn, q="Description", sort="relevance", offset=serve.SEARCH_PAGE_SIZE
)
check("tied relevance pages do not overlap",
      bool({r["id"] for r in match_first["results"]}
           & {r["id"] for r in match_second["results"]}), False)
check("the partial final page contains 35 episodes", last["count"], 35)
check("the final page reports completion", last["has_more"], False)
check("the public per-request ceiling remains finite", serve.SEARCH_LIMIT, 200)

all_rows = serve.search(conn, sort="oldest", limit=5000)
check("the internal export-sized path still reaches all episodes",
      all_rows["count"], 785)
check("the export-sized path is complete", all_rows["truncated"], False)
exported, error = serve.export_rows(conn, "https://archive.example")
check("the actual export path has no search error", error, None)
check("the actual export contains all 785 episodes", len(exported), 785)

print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    sys.exit(1)
print("All server tests passed.")
