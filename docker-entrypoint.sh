#!/bin/sh
# One image, two jobs. `serve` runs the site; `refresh` runs the update loop.
#
# The reason this script exists rather than a bare CMD: on a first deploy the
# volume is empty, and serve.py exits when there is no database. Without a
# bootstrap the very first deploy would crash-loop, which looks like a broken
# build rather than an empty disk.
set -e

DB="${DATABASE_PATH:-/data/lhf.sqlite}"

bootstrap() {
  if [ ! -f "$DB" ]; then
    echo "No database at $DB — building it. First run takes a few minutes."
    # refresh.py runs ingest, transcripts and enrich in the required order.
    python3 /app/refresh.py
  fi
}

case "${1:-serve}" in
  serve)
    bootstrap
    exec python3 /app/serve.py
    ;;
  refresh)
    # The web container owns first-run creation. If this one bootstrapped too,
    # a first deploy would have two processes ingesting the same feeds into the
    # same SQLite file at once. Wait for it to appear instead.
    #
    # Running this service on its own? Use `once` first to build the database.
    waited=0
    while [ ! -f "$DB" ]; do
      if [ "$waited" -eq 0 ]; then
        echo "Waiting for $DB — the web container builds it on first run."
      fi
      waited=$((waited + 10))
      sleep 10
    done
    # Both shows are weekly, so daily is already generous. --quiet-if-nothing-new
    # keeps the logs readable so a real failure stands out.
    exec python3 /app/refresh.py --loop 24h --quiet-if-nothing-new
    ;;
  once)
    exec python3 /app/refresh.py
    ;;
  *)
    exec "$@"
    ;;
esac
