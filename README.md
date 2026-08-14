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

There is a fourth step, `ingest/extract.py`, which is **not** part of
`refresh.py` — see [Topics, guests and interviewers](#topics-guests-and-interviewers).

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
python3 refresh.py --loop 15m --quiet-if-nothing-new
```

Runs immediately, then every 15 minutes — the deployed setting. Only logs when
something changed. On repeated failure it backs off (5m, 10m, 20m…) rather than
hammering the feed, and keeps retrying — transient network errors are normal and
shouldn't need a human.

**Fifteen minutes is affordable because a tick with nothing new costs 1 second
and downloads 0 bytes.** Podbean serves an `ETag` and honours `If-None-Match`
with a 304, so an unchanged feed transfers no body; and the expensive
enrichment pass (a full rebuild of mentions and re-airs) is skipped unless the
feeds actually brought something. Both shows publish weekly, so that is all but
two ticks a week.

**2. Cron** — if you'd rather the host own the schedule:

```cron
# Sundays 04:00, after both shows are out
0 4 * * 0  cd /path/to/digital-asset-manager && /usr/bin/python3 refresh.py >> /var/log/lhf-refresh.log 2>&1
```

**3. Coolify scheduled task** — same command as the cron line, configured
against the container.

Whichever you choose, **back the database up off-box**. `backup.py` does it
safely against a live database:

```bash
ssh HOST 'docker exec CONTAINER python3 /app/backup.py --stdout' > lhf-$(date +%F).sqlite
```

This matters more than it used to. Podbean serves only the most recent 100
episodes per show and **both shows are now at exactly that number**, so from
here on an episode rotates out of the feed every week while the database keeps
it. Re-scraping no longer recovers everything. See `HANDOFF.md`, "Backups".

## Deploying

```bash
docker compose up --build        # web on :8000, plus a refresh worker
```

Or in Coolify: point it at **https://github.com/Catskill909/lhf-tools**, add a
**volume mounted at `/data`**, and deploy. Everything that must survive a redeploy lives there and nowhere else.

| | |
|---|---|
| `DATABASE_PATH` | `/data/lhf.sqlite` — put it on the volume, not in the image |
| `LHF_HOST` | `0.0.0.0` in a container, or the proxy can't reach the process |
| `PORT` | `8000` |

**The first deploy serves immediately and fills in behind itself.** The volume
starts empty, so the container creates an empty database (well under a second),
starts the server, and fetches the archive in the background — about 143
seconds for 200 episodes, 14,937 passages, 701 tags and 28 re-air links. The
site is up throughout; it just has nothing in it for the first minute or two.

**This is the shape it has to be.** The first version built the archive *before*
starting the server, and it would not deploy: nothing is listening during the
build, so every health check fails, the orchestrator declares the container
unhealthy and restarts it, and the build starts over. Coolify allows about 55
seconds. Time to first response is now **1 second**.

### Coolify settings that matter

Coolify runs its **own** health check and ignores the one in the Dockerfile:

- **Set "Ports Exposes" to `8000`.** It defaults to 3000, and the check fails
  against a port nothing is listening on.
- `curl` is installed in the image for this reason. Coolify's check shells out
  to `curl` or `wget`, and `python:3.12-slim` ships with neither — the first
  deploy failed with `curl: not found` on every attempt.

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
docker-compose.yml     web + refresh worker, sharing one volume
docker-entrypoint.sh   serve | refresh | once — and the first-run bootstrap
refresh.py             run the whole pipeline in order
ingest/ingest.py       feed → SQLite
ingest/transcripts.py  Podcast 2.0 .srt → segments
ingest/enrich.py       deterministic enrichment (tags, re-airs) — no AI
ingest/extract.py      the one AI step: topics, guests, interviewers
ingest/schema.sql      tables, FTS5 index, triggers
serve.py               JSON API + serves the UI and its JS
static/index.html      the interface (markup, styles, app code — no build step)
static/mp3cut.js       lossless MP3 clip extraction (probe + frame copy)
static/waveform.js     peaks, IndexedDB cache, canvas waveform, snap-to-silence
static/zip.js          ZIP + CSV writers for the archive package (no dependency)
backup.py              consistent snapshot of the database; --stdout to pull it
tests/                 node tests (dev only, not shipped)
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

## Topics, guests and interviewers

⚠️ **Written and tested, but never run. There is no AI anywhere in production
and no extracted data in the database.** See [docs/ai-layer.md](docs/ai-layer.md)
for what this would add, what it costs, and what has to exist before it should
be run for real.

The last gap in the original brief, and the only place AI earns its keep here.
Show notes describe an episode but never classify it, most guests are
hyperlinked but not all, and nothing anywhere records who was asking the
questions. `ingest/extract.py` reads the notes and the transcript and works out
all three.

```bash
pip install anthropic                        # the project's only dependency
export ANTHROPIC_API_KEY=sk-ant-...          # in production: a Coolify env var

python3 ingest/extract.py --dry-run          # build and cost the batch, send nothing
python3 ingest/extract.py                    # submit, wait, collect, build
python3 ingest/extract.py --rebuild          # re-derive tables from stored output, free
```

`--dry-run` needs no key and no network — it builds every request against the
real database and prices the job.

**It is not part of `refresh.py`.** That loop runs unattended in the container
and must stay stdlib-only, keyless and free; this step is none of those. Run it
after a batch of new episodes — it only processes episodes it hasn't seen, so a
re-run costs only what's new. Everything else works without it; the UI simply
shows no topics.

**It should not stay a shell command.** Anything that spends money and rewrites
catalogue data wants an admin screen in front of it — trigger, cost preview,
progress, diff — which the site does not yet have and needs for other reasons
too (staff notes, tag corrections, `replayed_at` all have schema and no UI).

Measured cost, batched, against the real archive:

| | Tokens | Cost |
|---|---|---|
| Per episode | ~7,000 in, ~350 out | **$0.022** |
| Initial run, 200 episodes | 1.55M | **$4.35** |
| Ongoing, ~104 episodes/year | — | **~$2.26/year** |

Two things make the output a catalogue rather than a pile of strings:

- **A seeded vocabulary.** Asked for free-form topics across 200 episodes, any
  model returns "unions", "labor unions" and "unionization" as three separate
  topics. `extract.py` carries a ~50-term labor-history taxonomy the model must
  prefer, and may only coin two new terms per episode when nothing fits. It
  rides in the cached prompt prefix, so consistency is free.
- **Raw output is kept.** Every response is stored verbatim in `extractions`.
  A better *prompt* means paying again; a better *parser* means `--rebuild`,
  which costs nothing and takes a second.

Producer hyperlinks stay ground truth: they're fed to the model as spelling
hints, and where the two disagree about how a name is written, the producers
win. Names are normalised on the way in, so "Dr. Jeffrey Johnson" and "Jeffrey
Johnson" are one person with one episode count.

## API

The UI is just a client — swap it for anything without touching the backend.

| Endpoint | Returns |
|---|---|
| `GET /api/search?q=&show=&year=&encore=&limit=` | ranked results with highlighted snippets |
| `GET /api/facets` | shows, years, and totals for the filter chips |
| `GET /api/topics` | the subject vocabulary, commonest first |
| `GET /api/people?role=guest\|interviewer\|host` | guests and interviewers with episode counts |
| `GET /api/export?format=csv\|tsv\|json&…` | the current result set as a file; same filter params as search |
| `GET /api/episode/<id>` | one episode, for shared moment links |
| `GET /api/episode/<id>/segments?q=` | every transcript line with its timings, server-highlighted for `q` — what the transcript modal reads |
| `GET /episode/<id>/transcript?format=txt\|srt\|vtt` | one transcript to read, print or caption with |
| `GET /api/bundle?transcripts=1&passages=1&…` | Everything the archive package needs in one request — rows, transcripts and timed passages for the given scope, keyed on `guid`. The browser builds the `.zip` itself. |
| `GET /api/version` | content hash of `index.html` and the two ES modules. The page re-checks this when its tab regains focus, so a browser left open across a deploy can offer a reload instead of silently running old code. Database-free and cheap on purpose. |

Every response carries an `ETag` and honours `If-None-Match`, so a reload that
changes nothing costs a 304 with an empty body rather than the whole payload.

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
- **Transcript view** — the words with the tools around them: find inside an
  episode with the same query syntax as the archive, a matches-only view,
  click-to-play with follow-along, print, and Text / SRT / VTT download.
  Opens pre-highlighted with whatever search produced the result.
  **Every line has an Edit** that opens the clip editor on that passage —
  permanently visible on lines that matched the search, so a hit is one click
  from a waveform. Selecting a longer stretch reports its exact duration,
  in/out times and out-cue before anything is cut.
- **Re-air detection** — flags encores and programmes that ran on both shows
- **Tags** — 232 people/orgs/books from the producers' own hyperlinks
- **Topics** *(built, no data until the extraction pass is run)* — what each
  episode is *about*, from a seeded labor-history vocabulary; click one to see
  everything on that subject
- **Guests and interviewers** *(same)* — including the guests nobody
  hyperlinked, and who was asking the questions that week
- **Filters** — show, year, encores-only, by tag, by topic, by person, with
  All / Reset
- **Export** — CSV / TSV / JSON of the current result set, built for clean
  spreadsheet import (UTF-8 BOM, ISO dates, numeric durations, TRUE/FALSE)
- **Clip extraction** — the scissors at the right of the player opens a
  waveform editor on what you're listening to. Transport with play/pause,
  back-to-start and Repeat (which follows the handles as you trim); a time ruler
  on each waveform; click the overview to listen from any point. The zoomed view
  is drawn from **10 ms peaks** with an RMS body on a dB scale and the episode's
  own silence floor marked, so the gaps between words are visible; zoom follows
  the edge you're working, down to a half-second window. Drag across the zoomed
  view to set both marks at once, click it to place the playhead, drag the
  handles or arrow-key nudge to adjust, `I`/`O` to mark at the playhead, `[`/`]`
  to jump between pauses, `⌘Z` for one step of selection undo, snap to silence,
  hear the clip's own first or last seconds — then download an MP3
  **cut losslessly from the source** (no re-encode; within one 26 ms frame of
  the mark). Entirely in the browser — audio streams from the CDN and never
  touches this server.
- **Shareable links** — the address bar carries the full search state;
  `?ep=123&from=522&to=549` opens a single moment and `?help` opens the guide.
  `?q=` is the integration point for a search box on laborheritage.org.
- Light/dark, keyboard shortcuts, help modal with runnable examples

## Weight on the wire

Responses are gzipped (level 6) when the client asks, and everything sends
`Cache-Control: no-cache`.

| | raw | sent |
|---|---|---|
| `/` (whole UI, no build step) | 100 KB | **28 KB** |
| `/api/search` — all 200 episodes | 386 KB | **90 KB** |
| `/api/search?q=labor` — worst case | 510 KB | **121 KB** |

A first visit is roughly **118 KB**, and a full 200-row render is about 3,500
DOM elements — comfortable on a phone.

**The search response grew by ~40 KB gzipped when full show notes replaced a
240-character substring.** That substring truncated 100% of episodes — the
median note is 1,064 characters — mid-word and without an ellipsis, so cards
read as corrupted rather than shortened. The notes are now sent whole and
clamped in the browser, which is the same trade this project already makes
against pagination: shipping the data is cheaper than the machinery to avoid
shipping it, and it keeps find-in-page working across every note on screen.

**There is no pagination or infinite scroll, deliberately.** At this size the
whole result set is cheaper to send than the machinery to avoid sending it, and
having every result present means find-in-page and Export match what's on
screen. Revisit if the Podbean backlog triples the archive: at the current
per-episode weight ~600 episodes would be ~270 KB gzipped and ~10,000 elements,
which is the point where it starts to be worth measuring again — and where
sending notes on demand rather than up front becomes the obvious first saving.

## Tests

```bash
node tests/test-waveform.mjs      # pure — peak reduction, snap-to-silence
node tests/test-update-prompt.mjs # pure — the new-version reload prompt
node tests/test-zip.mjs           # pure — the archive packager (needs python3)
node tests/verify-clips.mjs       # live — needs the server running + network
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
- **`people` / `topics`** — filled by `extract.py`. The `normalized_name`
  unique key is the dedup hook so "Dr. Jeffrey Johnson" and "Jeffrey Johnson"
  collapse into one person instead of two. `episode_people.role` carries
  host / interviewer / guest / mentioned.
- **`extractions`** — raw model output, one row per episode, kept so the
  parsing can be changed and re-run for free.
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
- **An admin interface.** The blocker for the AI layer and for three features
  the schema already supports with no way to reach them: staff notes, tag
  corrections, and marking an episode re-aired. Needs auth in front of it.
- **Run the extraction pass**, once there's a screen to run it from.
  `ingest/extract.py` is written and its output path is tested end to end, but
  it has never touched the live API — there is no key on the dev machine.
  `--dry-run` prices it at $4.35. See [docs/ai-layer.md](docs/ai-layer.md).
- The 55 episodes with no feed transcript (~$9.52)
