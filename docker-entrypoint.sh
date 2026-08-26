#!/bin/sh
# One image, two jobs. `serve` runs the site; `refresh` runs the update loop.
#
# The important thing this script does is open the port immediately.
#
# The first version built the whole archive before starting the server, and
# that failed to deploy: the container isn't listening during the build, so
# every health check fails, the orchestrator calls the container unhealthy and
# restarts it, and the build begins again. A deploy loop that never finishes.
# Coolify allowed about 55 seconds; the build takes around 143.
#
# So now an empty database is created in under a second, the server starts
# against it, and the archive is fetched in the background. The site answers
# straight away — briefly with nothing in it — and fills in behind itself.
set -e

DB="${DATABASE_PATH:-/data/lhf.sqlite}"
MARK="$(dirname "$DB")/.bootstrapped"

# schema.sql alone is enough for the API to answer: searches return nothing and
# the tag/re-air lookups degrade gracefully on the tables enrich.py adds later.
init_schema() {
  python3 - "$DB" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.executescript(open("/app/ingest/schema.sql").read())
conn.close()
PY
}

# Keeps the archive current in a single-container deploy. Coolify deploys the
# Dockerfile, not the compose file, so without this the site is frozen at
# whatever the feeds held on deploy day — the one thing an archive of a weekly
# show must not be. Set LHF_AUTO_REFRESH=0 when a dedicated worker is running,
# or two processes will ingest the same feeds into one SQLite file.
refresh_loop_in_background() {
  [ "${LHF_AUTO_REFRESH:-1}" = "0" ] && return 0
  (
    while [ ! -f "$MARK" ]; do sleep 15; done
    echo "Update loop started — checking the feeds every 15m."
    exec python3 /app/refresh.py --loop 15m --quiet-if-nothing-new
  ) &
}

build_in_background() {
  (
    # A fresh volume should become the complete archive, not merely the latest
    # 100 items from each RSS channel. Backfill first; refresh then lets RSS
    # claim the current rows by permalink, fetches every published transcript,
    # and rebuilds enrichment. The web server is already answering throughout.
    if python3 /app/ingest/backfill.py \
       && python3 /app/refresh.py \
       && python3 /app/ingest/enrich.py; then
      touch "$MARK"
      echo "First build complete — the archive is now populated."
    else
      # Leaving the marker absent is deliberate: the refresh worker waits for
      # it, so a failed first build doesn't get compounded by a second process.
      echo "First build FAILED. The site is up but empty; see the errors above." >&2
    fi
  ) &
}

case "${1:-serve}" in
  serve)
    if [ ! -f "$DB" ]; then
      echo "No database at $DB."
      echo "Creating an empty one so the site can answer immediately;"
      echo "the archive will fill in behind it (a couple of minutes)."
      init_schema
      build_in_background
    else
      # An existing database from an older deploy won't have the marker, and
      # the refresh worker would wait for it forever.
      [ -f "$MARK" ] || touch "$MARK"
    fi
    refresh_loop_in_background
    exec python3 /app/serve.py
    ;;
  refresh)
    # The web container owns the first build. Two processes ingesting the same
    # feeds into one SQLite file would race, so wait for it to finish.
    #
    # Running this service on its own? Use `once` first to build the database.
    if [ ! -f "$MARK" ]; then
      echo "Waiting for the first build to finish before starting the loop."
      while [ ! -f "$MARK" ]; do sleep 15; done
    fi
    # Both shows are weekly, but a daily check meant a new episode could sit
    # unseen for most of a day — not good enough for a live podcast. A tick is
    # now nearly free: the feeds are fetched conditionally, so an unchanged one
    # answers 304 with an empty body, and the expensive enrichment pass only
    # runs when something new actually arrived. --quiet-if-nothing-new keeps the
    # logs readable so a real failure stands out.
    exec python3 /app/refresh.py --loop 15m --quiet-if-nothing-new
    ;;
  once)
    init_schema
    python3 /app/ingest/backfill.py
    python3 /app/refresh.py
    # RSS matches the page-first rows rather than inserting them, so refresh's
    # "only when new" gate correctly sees zero. Enrichment still needs one
    # explicit complete-archive rebuild after this historical import.
    python3 /app/ingest/enrich.py
    touch "$MARK"
    ;;
  backfill)
    init_schema
    python3 /app/ingest/backfill.py
    python3 /app/refresh.py
    python3 /app/ingest/enrich.py
    ;;
  *)
    exec "$@"
    ;;
esac
