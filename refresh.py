#!/usr/bin/env python3
"""
LHF Digital Asset Manager — run the whole pipeline, in order.

    python3 refresh.py                 # once, now
    python3 refresh.py --loop 24h      # now, then every 24h (stays running)
    python3 refresh.py --loop 6h --quiet-if-nothing-new

Three steps that must run in sequence, because each depends on the last:

    1. ingest.py      feeds  -> episodes (+ transcript URLs)
    2. transcripts.py .srt   -> segments, transcript_text
    3. enrich.py      links  -> mentions, re-airs

Running one without the others leaves the app half-built. This exists so that
can't happen by accident.

ingest/extract.py — the AI pass for topics, guests and interviewers — is
deliberately NOT one of them. It is the only step that needs a dependency, an
API key and money, and this loop runs unattended inside the container. A daily
job that can fail on an expired key, or quietly spend, is a different kind of
thing from one that re-reads a public feed. Run it by hand after a batch of new
episodes; the archive is fully usable in the meantime, just without topics on
the newest few.

Everything is idempotent: a re-run with no new episodes is a cheap no-op that
updates existing rows in place. Both shows publish weekly, so daily is ample.

--loop keeps the process alive and reschedules itself, which works identically
on a laptop, in Docker, and on Coolify without depending on the host having
cron. For a host scheduler instead, see the crontab example in README.md.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

# The third field is "only run this when the feed actually brought something
# new". It exists so the loop can poll often without doing expensive work on
# every tick — see the note on interval below.
#
#   Feeds        two conditional GETs; a 304 costs nothing, and even a full
#                read is ~1 MB and a couple of hundred no-op upserts.
#   Transcripts  one indexed SELECT for `transcript_status = 'pending'` and
#                nothing else when there is nothing outstanding. Always runs,
#                because Podbean sometimes attaches a transcript to an episode
#                days after publishing it — gating it on new episodes would
#                mean never picking those up.
#   Enrichment   `DELETE FROM reairs` + `DELETE FROM mentions` and a full
#                rebuild across every episode. This is the one that must not
#                run every few minutes.
STEPS = [
    ("Feeds",       ["ingest", "ingest.py"],      False),
    ("Transcripts", ["ingest", "transcripts.py"], False),
    ("Enrichment",  ["ingest", "enrich.py"],      True),
]


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def parse_interval(text):
    """'24h' / '90m' / '3600' -> seconds."""
    m = re.fullmatch(r"(\d+)\s*([hmd]?)", (text or "").strip().lower())
    if not m:
        raise argparse.ArgumentTypeError(
            f"bad interval {text!r} — use e.g. 24h, 90m, 3600")
    n, unit = int(m.group(1)), m.group(2)
    return n * {"": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def run_once(passthrough, owed=None):
    """Returns (exit_code, summary_line, owed).

    `owed` carries steps that still have to run even though this tick brought
    nothing new — a step that failed on the tick which *did* bring something
    new. Without it the retry looks like an ordinary quiet tick, the step is
    skipped as "no new episodes", the run reports success, and the failure is
    swallowed for as long as the feeds stay unchanged. That is precisely the
    silently-broken updater this loop is supposed to avoid.
    """
    started = time.time()
    new_episodes = transcribed = 0
    owed = set(owed or ())

    for i, (label, path, only_when_new) in enumerate(STEPS, 1):
        # Both shows publish weekly, so on all but two ticks a week the feeds
        # bring nothing. Rebuilding the whole mentions/re-airs graph on those
        # ticks is pure waste, and it is what made a short interval look
        # expensive. `Feeds` runs first, so its count is known by the time this
        # is checked.
        if only_when_new and new_episodes == 0 and label not in owed:
            print(f"\n{'=' * 62}\n  {i}/{len(STEPS)}  {label} — skipped, "
                  f"no new episodes\n{'=' * 62}", flush=True)
            continue

        script = os.path.join(HERE, *path)
        print(f"\n{'=' * 62}\n  {i}/{len(STEPS)}  {label}\n{'=' * 62}", flush=True)
        proc = subprocess.run([sys.executable, script] + passthrough,
                              capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)

        if proc.returncode != 0:
            # Only the skippable steps need remembering; the others run every
            # tick anyway.
            if only_when_new:
                owed.add(label)
            return (proc.returncode,
                    f"{label} failed (exit {proc.returncode})", owed)

        owed.discard(label)

        m = re.search(r"Total:\s*(\d+) new", proc.stdout)
        if m:
            new_episodes = int(m.group(1))
        m = re.search(r"^(\d+) transcribed", proc.stdout, re.M)
        if m:
            transcribed = int(m.group(1))

    took = time.time() - started
    return 0, (f"{new_episodes} new episode(s), {transcribed} transcript(s) "
               f"in {took:.0f}s"), owed


def main():
    ap = argparse.ArgumentParser(description="Run the LHF ingest pipeline")
    ap.add_argument("--loop", type=parse_interval, metavar="INTERVAL",
                    help="run repeatedly, e.g. 24h / 90m / 3600")
    ap.add_argument("--quiet-if-nothing-new", action="store_true",
                    help="in loop mode, only print a line when something changed")
    args, passthrough = ap.parse_known_args()

    if not args.loop:
        code, summary, _ = run_once(passthrough)
        print(f"\n{'=' * 62}\n  {summary}\n{'=' * 62}")
        return code

    interval = args.loop
    print(f"[{stamp()}] refresh loop started — every {interval}s "
          f"({interval / 60:.0f}m). Ctrl-C to stop.", flush=True)
    failures = 0
    owed = set()
    while True:
        code, summary, owed = run_once(passthrough, owed)
        if code == 0:
            failures = 0
            if not (args.quiet_if_nothing_new and summary.startswith("0 new episode(s), 0")):
                print(f"[{stamp()}] OK — {summary}", flush=True)
            wait = interval
        else:
            failures += 1
            # Back off on repeated failure so a broken feed doesn't hammer
            # anyone, but keep trying — transient network errors are normal.
            wait = min(interval, 300 * (2 ** min(failures - 1, 4)))
            print(f"[{stamp()}] FAILED ({failures}x) — {summary}; "
                  f"retrying in {wait}s", file=sys.stderr, flush=True)
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            print(f"\n[{stamp()}] stopped.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
