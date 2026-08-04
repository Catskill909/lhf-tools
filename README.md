# LHF Digital Asset Manager

Search interface over both Labor Heritage Foundation podcast feeds. Tier 1 of
the build plan: no AI, no API keys, no dependencies.

## Running it locally

Two steps, from the project root. **Stdlib only — no `pip install`, no venv.**

```bash
python3 refresh.py           # 1. build everything  (~2 min first run)
python3 serve.py             # 2. start the UI  →  http://localhost:8000
```

`refresh.py` runs the three pipeline steps in order — feeds, then transcripts,
then enrichment. Run them individually only if you know why:

```bash
python3 ingest/ingest.py        # feeds      -> episodes (+ transcript URLs)
python3 ingest/transcripts.py   # .srt       -> segments, transcript_text
python3 ingest/enrich.py        # links      -> tags, re-air detection
```

Skipping a step leaves the app half-built (a fresh database without the
enrichment step has no tags and the API errors on a missing table).

Then open <http://localhost:8000>. Ctrl-C to stop the server.

```bash
python3 serve.py --port 9000      # different port
python3 serve.py --host 0.0.0.0   # reachable from other machines (see below)
python3 ingest/ingest.py --stats  # stats + search sanity check, no fetch
DATABASE_PATH=/tmp/x.sqlite python3 serve.py   # point at another database
```

Re-running is safe any time — everything keys on the RSS `<guid>`, so a second
run updates rows in place rather than duplicating them. With no new episodes
it's a ~2 second no-op.

**The server binds to `127.0.0.1` by default** — running it on a laptop should
not quietly put the archive on the café wifi. `--host 0.0.0.0` opens it up, and
that is what the container sets.

## Keeping it up to date

Both shows publish weekly. Three ways to run it automatically, pick one:

**1. Built-in loop** — works identically on a laptop, in Docker, and on Coolify
with no host scheduler involved:

```bash
python3 refresh.py --loop 24h --quiet-if-nothing-new
```

Runs immediately, then every 24h. Only logs when something changed. On repeated
failure it backs off (5m, 10m, 20m…) rather than hammering the feed, and keeps
retrying — transient network errors are normal and shouldn't need a human.

**2. Cron** — if you'd rather the host own the schedule:

```cron
# Sundays 04:00, after both shows are out
0 4 * * 0  cd /path/to/digital-asset-manager && /usr/bin/python3 refresh.py >> /var/log/lhf-refresh.log 2>&1
```

**3. Coolify scheduled task** — same command as the cron line, configured
against the container.

Whichever you choose, **back the SQLite file up off-box first**. The feeds
re-scrape for free; 882k words of transcript don't.

## Deploying

```bash
docker compose up --build        # web on :8000, plus a daily refresh worker
```

Or in Coolify: point it at **https://github.com/Catskill909/lhf-tools**, add a
**volume mounted at `/data`**, and deploy. Everything that must survive a redeploy lives there and nowhere else.

| | |
|---|---|
| `DATABASE_PATH` | `/data/lhf.sqlite` — put it on the volume, not in the image |
| `LHF_HOST` | `0.0.0.0` in a container, or the proxy can't reach the process |
| `PORT` | `8000` |

**The first deploy builds the archive before it serves anything.** The volume
starts empty, so the `web` container runs the whole pipeline first — feeds,
144 transcript files, then enrichment. Measured end to end from nothing:
**143 seconds**, producing 200 episodes, 14,937 passages, 701 tags and 28
re-air links.

That is network bound, so a busy VPS will be slower. The health check has a
15-minute start period to cover it: failures inside the start period don't
count, but too short a grace would mark the container unhealthy mid-build, get
it restarted, and begin the build again, forever.

Without the bootstrap at all, the first deploy would crash-loop on a missing
database, which looks like a broken build rather than an empty disk.

The `refresh` container **waits** for that database rather than building its
own; two processes ingesting the same feeds into one SQLite file would race.
Running the worker on its own? `docker compose run --rm refresh once` first.

Nothing is installed at build time. The app is stdlib-only and the front end
has no build step, so the image is the Python interpreter plus this repo —
no lockfile, nothing to drift.

**No authentication.** Everything served is already-published podcast material,
and `episode_notes` is not exposed by the API. If internal-only fields are
added later, put auth in front of it before deploying again.

## Layout

```
Dockerfile             python:3.12-slim, stdlib only, nothing to install
docker-compose.yml     web + daily refresh worker, sharing one volume
docker-entrypoint.sh   serve | refresh | once — and the first-run bootstrap
refresh.py             run the whole pipeline in order
ingest/ingest.py       feed → SQLite
ingest/transcripts.py  Podcast 2.0 .srt → segments
ingest/enrich.py       deterministic enrichment (tags, re-airs) — no AI
ingest/schema.sql      tables, FTS5 index, triggers
serve.py               JSON API + serves the UI and its JS
static/index.html      the interface (markup, styles, app code — no build step)
static/mp3cut.js       lossless MP3 clip extraction (probe + frame copy)
static/waveform.js     peaks, IndexedDB cache, canvas waveform, snap-to-silence
tests/                 clip editor tests (node; dev only, not shipped)
data/lhf.sqlite        the database (gitignored)
```

## Using the interface

- Type to search — results update as you go
- `/` focuses the search box, `Esc` clears it
- Filter chips for show, year, and encores-only; click again to unset
- Light/dark toggle top right (follows your OS by default)
- Titles link out to the episode on Podbean

### Search syntax

Two modes, chosen automatically by what you type.

**Plain words** — implicit AND, and the word in progress is prefix-matched, so
results stay useful mid-typing (`carsie bla` finds Carsie Blanton).

**Query syntax** — the moment you use an operator, quote, parenthesis, `*`, or
a field prefix, the query is passed through as written:

| Example | Does |
|---|---|
| `"general strike"` | exact phrase |
| `strike NOT encore` | exclude |
| `strike OR walkout` | union |
| `(strike OR walkout) NOT encore` | grouping |
| `organiz*` | truncation — organize / organized / organizing / organizers |
| `title:strike` | search one field only |
| `NEAR(coal mine, 5)` | proximity |

Fields are `title`, `description_text`, `transcript_text`. A malformed query
returns a syntax error rather than silently running something else.

**Tokenizer note:** the index deliberately uses `unicode61`, not the porter
stemmer. Stemming stores stems, which breaks prefix matching mid-word and makes
`organiz*` behave unpredictably. Whole-word indexing plus explicit truncation
gives the same recall and is predictable — which matters for cataloguers.

## API

The UI is just a client — swap it for anything without touching the backend.

| Endpoint | Returns |
|---|---|
| `GET /api/search?q=&show=&year=&encore=&limit=` | ranked results with highlighted snippets |
| `GET /api/facets` | shows, years, and totals for the filter chips |
| `GET /api/export?format=csv\|tsv\|json&…` | the current result set as a file; same filter params as search |
| `GET /api/episode/<id>` | one episode, for shared moment links |
| `GET /episode/<id>/transcript` | plain-text transcript for one episode |

Clip extraction calls no endpoint here at all — the browser range-requests the
audio from Podbean's CDN directly.

`serve.py` is stdlib `http.server` — fine for local work. For deployment,
swap in FastAPI behind the same two routes; the front end won't know.

## What's in there now

| | Power Hour | Labor History Today |
|---|---|---|
| Episodes | 100 | 100 |
| Date range | 2024-09-12 → 2026-07-30 | 2024-09-22 → 2026-08-02 |
| Avg length | 54 min | 32 min |
| Total audio | 90.3 hrs | 52.8 hrs |
| Encores | 7 | 15 |
| Transcripts | 77 | 67 |

200 episodes, 143.1 hours. **144 carry full transcripts** pulled free from the
feed — 14,937 searchable passages, 882,346 words. Plus 232 producer-linked
tags and 14 detected re-airs.

## Features

- **Search** — full-text with ranked results, as-you-type prefix matching,
  `"phrases"`, `AND`/`OR`/`NOT`, `(grouping)`, `organiz*`, `title:strike`,
  `NEAR(a b, 5)`; six sort orders
- **Transcript search** — reaches spoken audio, not just show notes; matches
  are labelled and show the spoken line
- **Jump to the moment** — timestamps under each result; click to play from
  that second in an inline player
- **Re-air detection** — flags encores and programmes that ran on both shows
- **Tags** — 232 people/orgs/books from the producers' own hyperlinks
- **Filters** — show, year, encores-only, by tag, with All / Reset
- **Export** — CSV / TSV / JSON of the current result set, built for clean
  spreadsheet import (UTF-8 BOM, ISO dates, numeric durations, TRUE/FALSE)
- **Clip extraction** — the scissors at the right of the player opens a
  waveform editor on what you're listening to: drag handles, arrow-key nudge,
  zoom with the selection always centred, snap to silence, audition either cut
  point, then download an MP3 **cut losslessly from the source** (no re-encode;
  within one 26 ms frame of the mark). Entirely in the browser — audio streams
  from the CDN and never touches this server.
- **Shareable links** — the address bar carries the full search state;
  `?ep=123&from=522&to=549` opens a single moment and `?help` opens the guide.
  `?q=` is the integration point for a search box on laborheritage.org.
- Light/dark, keyboard shortcuts, help modal with runnable examples

## Tests

```bash
node tests/test-waveform.mjs     # pure — peak reduction, snap-to-silence
node tests/verify-clips.mjs      # live — needs the server running + network
```

Node is a **dev-only** dependency; nothing at runtime uses it.

`verify-clips.mjs` cuts real clips from randomly chosen episodes and then
searches the source file for the clip's bytes. An exact match at the expected
offset proves the cut is both correctly positioned and genuinely lossless —
duration alone would not, since a clip can be the right length and come from
the wrong place.

## ⚠️ The feed only returns 100 episodes per show

Podbean caps the RSS feed at the 100 most recent and **ignores every
pagination parameter** (`?paged=`, `?page=`, etc. — all tested, all return the
same 100). The website's "Load More" is JavaScript-driven, so there's nothing
to scrape from the raw HTML either.

So this covers roughly the last two years. Anything older needs a different
route:

- **Podbean API** (OAuth, has an episode-list endpoint) — the automatable option
- **Podbean dashboard export** — the manual one-off option

Worth settling before the transcription backfill, since it determines what
"the whole archive" actually means. Not urgent for interface work — 200 real
episodes is plenty to design against.

## Schema notes

`schema.sql` is the full picture. The parts that matter:

- **`episodes`** — one row per episode, keyed on `guid`. Keeps both
  `description_html` (hyperlinks in show notes are a guest signal worth
  preserving) and `description_text` (stripped, for search and extraction).
- **`transcript_source`** — `descript` | `google` | null. This is the column
  that makes the hybrid work: LHF's own Descript transcripts where they exist,
  machine transcription for the gaps. Nothing downstream cares which.
- **`segments`** — transcript chunks with optional timestamps and speaker tags.
  Deliberately source-agnostic: Descript SRT and Google `BatchRecognize` output
  both land here identically.
- **`people` / `topics`** — empty until the Tier 2 extraction pass. The
  `normalized_name` unique key is the dedup hook so "Dr. Jeffrey Johnson" and
  "Jeffrey Johnson" collapse into one person instead of two.
- **`episode_notes`** — internal staff notes and `replayed_at`, for the
  "have we already run this" workflow.
- **`episodes_fts`** — FTS5 over title + description + transcript, kept in sync
  by triggers. Contentless-linked to `episodes` so text isn't duplicated.

## Useful queries

```sql
-- Full-text search, best matches first
SELECT e.title, substr(e.published_at,1,10) AS d
FROM episodes_fts f JOIN episodes e ON e.id = f.rowid
WHERE episodes_fts MATCH '"Chris Garlock"'
ORDER BY rank LIMIT 20;

-- With a highlighted snippet, for result cards
SELECT e.title, snippet(episodes_fts, 1, '<mark>', '</mark>', '…', 20) AS excerpt
FROM episodes_fts f JOIN episodes e ON e.id = f.rowid
WHERE episodes_fts MATCH 'strike' ORDER BY rank LIMIT 20;

-- Encores, newest first
SELECT title, substr(published_at,1,10) FROM episodes
WHERE is_encore = 1 ORDER BY published_at DESC;

-- Episodes still needing a transcript
SELECT COUNT(*) FROM episodes WHERE transcript_status = 'pending';
```

FTS5 syntax worth knowing: `"exact phrase"`, `labor NOT history`,
`strike OR walkout`, `organiz*` for prefix matching.

## Next

- **Deploy it.** The container files are written and the pipeline is proven,
  but this has never been built or run as an image — there is no Docker on the
  dev machine. Coolify will be the first thing to build it.
- AI extraction pass over `description_text` + transcripts → `topics`,
  un-hyperlinked guests, interviewer roles (~$7 batched). The last gap in the
  original brief.
- The 55 episodes with no feed transcript (~$9.52)
