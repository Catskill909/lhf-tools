#!/usr/bin/env python3
"""Pure tests for feed stamping and rotated-out detection.

    python3 tests/test-ingest.py

The rest of the suite is `.mjs` because the rest of the app is JavaScript.
This one is Python because the thing under test is, and the alternative was
leaving the bug it covers untested.

**What it is really defending.** `last_seen_in_feed` is the only record of
which episodes the feed still carries. Once a channel passes Podbean's
100-episode cap it is what distinguishes live RSS entries from the history this
database retains. A wrong answer here is not a cosmetic reporting bug.

Both tests below reproduce a *class*, not the instance that was shipped:

1. The stamp for a pass must come from one place, not be re-read per row. It
   was `datetime('now')` inside the row loop; writing a hundred episodes spans
   several seconds, so a single pass wrote several distinct stamps and only the
   rows landing in the final second matched `MAX(...)`. `--stats` reported 84
   of 203 episodes as gone when the true number was 3. A test that stamps two
   rows quickly would pass against the broken code — so this asserts the stored
   value *equals the value handed in*, which fails the moment anything reads a
   clock per row.

2. "No longer in the feed" must be decided within a show. The feeds are read in
   sequence, and a conditional request means an unchanged feed is not restamped
   at all — so the two shows' stamps routinely differ, and any global
   comparison condemns whichever show is behind.
"""

import os
import sqlite3
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ingest"))

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


def add_show(conn, slug):
    conn.execute("INSERT INTO shows (slug, name, feed_url) VALUES (?,?,?)",
                 (slug, slug, f"https://example.invalid/{slug}.xml"))
    return conn.execute("SELECT id FROM shows WHERE slug = ?", (slug,)).fetchone()["id"]


def item(guid, title="Episode"):
    """The smallest <item> upsert_episode will accept."""
    node = ET.fromstring(
        f"<item><guid>{guid}</guid><title>{title}</title>"
        f"<pubDate>Thu, 06 Aug 2026 14:00:00 GMT</pubDate></item>")
    return node


# ---------------------------------------------------------------------------
print("\nOne stamp per pass, not one per row")

conn = fresh_db()
show = add_show(conn, "power-hour")

# A sentinel no clock would ever produce. If anything inside upsert_episode
# reads the time itself, the stored value cannot equal this.
STAMP = "1999-12-31 23:59:59"
for i in range(25):
    ingest.upsert_episode(conn, show, item(f"guid-{i}"), STAMP)

stamps = [r["last_seen_in_feed"]
          for r in conn.execute("SELECT last_seen_in_feed FROM episodes")]
check("every inserted row carries the pass stamp", set(stamps), {STAMP})
check("a pass writes exactly one distinct stamp", len(set(stamps)), 1)

# The same must hold on the UPDATE path — the bug existed in both statements,
# and an episode is inserted once but updated on every pass thereafter.
STAMP2 = "2000-01-01 00:00:00"
for i in range(25):
    ingest.upsert_episode(conn, show, item(f"guid-{i}"), STAMP2)

stamps = [r["last_seen_in_feed"]
          for r in conn.execute("SELECT last_seen_in_feed FROM episodes")]
check("re-running a pass restamps every row identically", set(stamps), {STAMP2})


# ---------------------------------------------------------------------------
print("\nRotated out is decided within a show, not across all of them")

conn = fresh_db()
ph = add_show(conn, "power-hour")
lht = add_show(conn, "labor-history-today")

OLD = "2026-08-01 00:00:00"      # the pass that last saw the departed episode
PH_NOW = "2026-08-13 10:00:00"   # power-hour read first…
LHT_NOW = "2026-08-13 10:00:07"  # …and labor-history-today seven seconds later

for i in range(5):
    ingest.upsert_episode(conn, ph, item(f"ph-{i}"), PH_NOW)
for i in range(5):
    ingest.upsert_episode(conn, lht, item(f"lht-{i}"), LHT_NOW)

# One Power Hour episode has fallen off the feed: it kept an older stamp.
ingest.upsert_episode(conn, ph, item("ph-gone"), OLD)

gone = [r["guid"] for r in conn.execute(
    f"SELECT guid FROM episodes WHERE {ingest.GONE_FROM_FEED}")]
check("only the episode that left the feed is reported", sorted(gone), ["ph-gone"])

# The heart of it: power-hour is stamped earlier than labor-history-today on
# every single run, because it is read first. Against a global MAX, all five
# of its still-present episodes are reported gone.
check("a show read earlier is not condemned by the other's later stamp",
      [g for g in gone if g.startswith("ph-") and g != "ph-gone"], [])

# And the 304 case, which is now the common one: a feed that has not changed is
# not restamped at all, so its stamps fall arbitrarily far behind the other
# show's. Nothing about that means its episodes left the feed.
conn.execute("UPDATE episodes SET last_seen_in_feed = ? WHERE show_id = ?",
             ("2026-08-13 10:00:31", lht))
gone = [r["guid"] for r in conn.execute(
    f"SELECT guid FROM episodes WHERE {ingest.GONE_FROM_FEED}")]
check("a feed answering 304 is not read as having lost its episodes",
      sorted(gone), ["ph-gone"])


# ---------------------------------------------------------------------------
print("\nConditional fetch")

# fetch() must report "unchanged" as a value, not raise. urllib turns 304 into
# an HTTPError because it is non-2xx, and an early version let that reach the
# caller, which logged it as a failed feed and backed off.
import urllib.error  # noqa: E402

_real_urlopen = ingest.urllib.request.urlopen


class _NotModified:
    def __call__(self, req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 304, "Not Modified", {}, None)


ingest.urllib.request.urlopen = _NotModified()
try:
    body, etag = ingest.fetch("https://example.invalid/feed.xml", etag='"abc"')
    check("304 returns no body", body, None)
    check("304 keeps the etag we sent", etag, '"abc"')
finally:
    ingest.urllib.request.urlopen = _real_urlopen


print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    sys.exit(1)
print("All ingest tests passed.")
