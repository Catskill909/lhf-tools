#!/usr/bin/env python3
"""
LHF Digital Asset Manager — take a consistent snapshot of the archive.

    python3 backup.py                       # snapshot to data/backups/
    python3 backup.py --dest /mnt/nas/lhf   # snapshot somewhere else
    python3 backup.py --keep 30             # how many to retain
    python3 backup.py --verify-only FILE    # check an existing snapshot

WHY THIS EXISTS, in one paragraph. Podbean serves only the most recent 100
episodes per show. Both shows are at exactly that number, and `ingest` never
deletes an episode — so the moment either show publishes again, the database
holds a recording the feed no longer offers, and no amount of re-scraping will
bring it back. Until now the database was disposable: `refresh.py` could
rebuild it from the feeds in 143 seconds. That has stopped being true, silently,
with nothing in the interface to mark the change. See HANDOFF.md, "Backups".

WHY NOT `cp`. The database runs in WAL mode with a live writer (the refresh
loop) on the same file. Copying `lhf.sqlite` with `cp`, `rsync` or a volume
snapshot can capture a torn page or miss committed transactions still sitting in
the -wal file, and the result is a file that often *opens fine* and is quietly
incomplete — the worst possible failure for a backup. `sqlite3.Connection.backup()`
is SQLite's online backup API: it takes a consistent snapshot of a live database
without blocking readers or the writer. It is stdlib, so this file adds no
dependency, which is the same rule the rest of the pipeline follows.

WHAT THIS DOES NOT PROTECT AGAINST. By default the snapshot lands next to the
database, which means **inside the same Docker volume**. That defends against
corruption, a bad migration and an accidental `DELETE`, and against nothing at
all if the volume itself is lost — which is the failure this whole exercise is
worried about. A backup is only a backup once a copy exists somewhere the
volume's destruction cannot reach. Point --dest at a mounted path off the
volume, or copy the output off the host after each run. The script prints its
output path loudly for exactly this reason.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "data", "lhf.sqlite"))


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def describe(path):
    """What a snapshot contains, in the terms that matter for this archive.

    Counting rows is the point. A backup that opens without error can still be
    empty or truncated, and 'the file exists and is 53 MB' is not evidence that
    the episodes are in it.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        eps = conn.execute("SELECT count(*) FROM episodes").fetchone()[0]
        segs = conn.execute("SELECT count(*) FROM segments").fetchone()[0]
        shows = conn.execute(
            "SELECT count(*) FROM (SELECT DISTINCT show_id FROM episodes)"
        ).fetchone()[0]
        return eps, segs, shows
    finally:
        conn.close()


def integrity(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def verify(path):
    """Open a snapshot and prove it is usable. Returns True on success."""
    try:
        result = integrity(path)
        if result != "ok":
            print(f"FAILED integrity check: {result}", file=sys.stderr)
            return False
        eps, segs, shows = describe(path)
    except sqlite3.Error as e:
        print(f"FAILED to read the snapshot: {e}", file=sys.stderr)
        return False

    print(f"  verified: {eps} episodes, {segs} segments, {shows} shows, "
          f"{human(os.path.getsize(path))}")
    if eps == 0:
        print("  WARNING: the snapshot has no episodes in it.", file=sys.stderr)
        return False
    return True


def rotate(dest, keep):
    """Delete the oldest snapshots beyond `keep`.

    Names are ISO-ordered, so lexical sort is chronological. Nothing else in
    the directory is touched — a stray file cannot be deleted by this.
    """
    snaps = sorted(f for f in os.listdir(dest)
                   if f.startswith("lhf-") and f.endswith(".sqlite"))
    for old in snaps[:-keep] if keep > 0 else []:
        os.remove(os.path.join(dest, old))
        print(f"  removed old snapshot {old}")


def backup(src, dest, keep):
    if not os.path.exists(src):
        print(f"No database at {src}", file=sys.stderr)
        return 1

    os.makedirs(dest, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out = os.path.join(dest, f"lhf-{stamp}.sqlite")

    print(f"Backing up {src}")
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(out)
    try:
        # pages=0 copies the whole database in one step. The archive is ~53 MB;
        # a page-by-page copy with a progress callback would be slower and would
        # give a live writer more chances to force a restart of the copy.
        src_conn.backup(dst_conn)
        # The snapshot inherits the source's journal mode, and the source runs
        # in WAL. That is wrong for an archive file in two ways: a WAL database
        # is really three files, and opening one read-only requires creating a
        # -shm side file, so `mode=ro` on a snapshot fails outright with
        # "unable to open database file". DELETE mode makes the snapshot a
        # single self-contained file that copies with `cp` and opens read-only
        # anywhere — which is the entire point of a backup.
        dst_conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.Error as e:
        print(f"FAILED: {e}", file=sys.stderr)
        dst_conn.close()
        src_conn.close()
        if os.path.exists(out):
            os.remove(out)          # never leave a half-written file that looks like a backup
        return 1
    finally:
        dst_conn.close()
        src_conn.close()

    # The -shm and -wal side files were created while the destination was still
    # in WAL mode, and SQLite does not always clear them on close. They are
    # ignored by a DELETE-mode database, but leaving them means the snapshot
    # looks like three files when it is one — and somebody copying "the backup"
    # off the host would reasonably wonder which parts they need.
    for sidecar in (out + "-shm", out + "-wal"):
        if os.path.exists(sidecar):
            os.remove(sidecar)

    if not verify(out):
        # A snapshot that fails verification is worse than no snapshot, because
        # it will sit in the directory looking like protection.
        os.rename(out, out + ".FAILED")
        print(f"Renamed to {out}.FAILED — do not rely on it.", file=sys.stderr)
        return 1

    rotate(dest, keep)
    print(f"\nWrote {out}")

    # The one thing a reader of the logs must not miss.
    if os.path.realpath(dest).startswith(os.path.realpath(os.path.dirname(src))):
        print("\nNOTE: this snapshot is beside the database, so it shares the\n"
              "      volume's fate. Copy it off the host — or pass --dest — or\n"
              "      this protects against corruption but not against loss.")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Consistent snapshot of the LHF archive database")
    ap.add_argument("--dest", default=None, metavar="DIR",
                    help="where to write snapshots (default: alongside the database)")
    ap.add_argument("--keep", type=int, default=7, metavar="N",
                    help="how many snapshots to retain, 0 for all (default: 7)")
    ap.add_argument("--verify-only", metavar="FILE",
                    help="check an existing snapshot and exit")
    args = ap.parse_args()

    if args.verify_only:
        return 0 if verify(args.verify_only) else 1

    dest = args.dest or os.path.join(os.path.dirname(DB_PATH), "backups")
    return backup(DB_PATH, dest, args.keep)


if __name__ == "__main__":
    sys.exit(main())
