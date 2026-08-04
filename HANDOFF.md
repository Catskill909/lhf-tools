# LHF Digital Asset Manager — Handoff

**Status:** working prototype, real data, running locally. Feature-complete for
everything achievable without AI.
**Last worked:** 3 August 2026 (one evening, built from nothing).
**Client:** Labor Heritage Foundation — Harold Phillips (producer), Chris Garlock
and Elise Bryant (hosts), Patrick Dixon.

---

## Start here

```bash
cd ~/Desktop/digital-asset-manager
python3 refresh.py           # feeds + transcripts + enrichment  (~2 min)
python3 serve.py             # → http://localhost:8000
```

`refresh.py` runs the three pipeline steps in the right order. Don't run them
individually unless you know why — skipping enrichment leaves the API erroring
on a missing `mentions` table.

Stdlib only — no pip, no venv, no build step. A full rebuild from nothing takes
~2½ minutes (most of it fetching 144 transcripts), so don't be precious about
the database — delete `data/` and re-run whenever it's easier than debugging.

> A test server may still be running on port **8765** from the last session.
> `pkill -f serve.py` if it's in the way.

---

## What this is

A searchable catalogue of both LHF podcasts. Their ask, from Harold's original
email: catalogue the guests, topics and interviewers; find older shows to
replay; check whether a segment has already run; and put a search box on
laborheritage.org so listeners can jump straight to an episode.

Everything achievable without AI is built: metadata, transcripts, spoken-word
search, jump-to-moment, re-air detection and tags. See the tier ladder in
`docs/lhf-podcast-spec.html`; only the AI tier remains.

### Working now

**Search**
- 200 episodes, 143.1 hours, both shows, updating automatically from the feeds
- Full-text with ranked results and highlighted excerpts
- As-you-type prefix matching (`carsie bla` finds Carsie Blanton)
- Query syntax: `"exact phrase"`, `AND`/`OR`/`NOT`, `(grouping)`, `organiz*`
  truncation, `title:strike` field search, `NEAR(coal mine, 5)` proximity
- Six sort orders: best match, newest, oldest, title A–Z, longest, shortest
- Filters: show, year, encores-only, and by tag — with All / Reset to clear

**Transcripts** *(free — pulled from the feed, no AI, no vendor)*
- 144 of 200 episodes carry full transcripts: **14,937 passages, 882,346 words**
- Search reaches spoken audio; hits are marked "Heard in this episode" and the
  excerpt is the spoken line
- **Jump to the moment** — up to 3 timestamps per result; click one and an
  inline player starts at that second. Audio is CORS-open and range-seekable,
  so this needs nothing from Podbean.

**Cataloguing** *(deterministic — no AI)*
- **Re-air detection** — 14 relationships: 5 programmes that ran on *both*
  shows, 8 encores of an earlier episode. Shown inline as "Also ran".
  This is Chris's "have we already run this" problem, solved.
- **232 tags** — people, bands, museums and books the producers hyperlinked in
  their own show notes. Click one to see every episode featuring it.
- 22 encores flagged automatically from title convention

**Export**
- CSV / TSV / JSON of **exactly what's on screen** — same filters, same order,
  same count. Calls `search()` rather than reimplementing the query, so the
  file and the screen can't drift apart.
- CSV written for spreadsheet import: UTF-8 BOM (Excel mangles "No Pasarán"
  without it), ISO dates that parse as dates, numeric durations that sum,
  `TRUE`/`FALSE` that Sheets treats as booleans
- Three URL columns at different fidelities — Podbean page, original `.srt`,
  and our cleaned transcript at `/episode/<id>/transcript`
- Transcript text deliberately excluded: ~49k chars per episode against a
  50k-character spreadsheet cell cap would truncate silently
- Clipboard option for pasting straight into an open sheet

**Clip extraction** *(all in the browser — our server does nothing)*
- A **scissors icon at the right-hand end of the player transport** opens the
  audio editor. It sits where a producer already is once they've found the
  spot, rather than on every line of text above it. It seeds from the passage
  that opened the player, or from wherever you've scrubbed to if you've moved
  away — "edit what you're listening to".
- A progress ring over the waveform reports the download in megabytes and
  then switches to a spin for the decode, which has no measurable progress.
  The wait is real — 30 to 105 MB — so it says how long rather than just
  spinning.
- Opening the editor **pauses the player**; the modal covers the transport, so
  audio left running is audible but unreachable.
- Two waveforms — whole episode for context, zoomed selection for precision —
  with draggable in/out handles, arrow-key nudge (±0.1s, ±1s with Shift), and
  a live in / out / length readout
- **Zoom** (− / + or scroll wheel) with the **selection always centred**, so
  what you're adjusting never wanders off screen. The window always contains
  the whole selection plus context, so both handles stay grabbable at every
  zoom level — tested as an invariant.
- **Play selection**, **play with a 2-second lead-in**, and **audition in /
  audition out** (two seconds either side of a single cut) — an edit is judged
  by ear, and usually one edge at a time
- **Snap to silence** puts a cut in the gap between words instead of through
  the middle of one
- Downloads as MP3 **cut straight from the source with no re-encoding** — the
  clip is bit-identical to the broadcast audio, and lands within one frame
  (26 ms) of the requested point. Verified by exact byte match against the
  source at 128 and 192 kbps.
- File name and ID3 tags carry show, date and timecode, so a clip found in a
  folder months later still says where it came from
- Audio streams from Podbean's CDN direct to the browser; peaks are cached in
  IndexedDB so an episode is only ever downloaded once

**Sharing**
- Every search is reflected in the address bar — filters, tag, sort and all —
  so a result set can be sent to a colleague as a link
- `?ep=123&from=522&to=549` opens the clip editor on a single moment
- `?help` opens the guide directly, for linking someone to the instructions
- `?q=` is the **public integration point**: laborheritage.org can put a search
  box on its own page and link straight in, with no API work

**Interface**
- Custom audio transport — play/pause, seekable track, elapsed/total, keyboard
  seek (arrows ±5s, shift ±30s, space). Replaces the native control bar, which
  can't be styled consistently across browsers.
- Light/dark, follows the OS, with a manual toggle
- Help modal documenting every search *and* editing feature, with runnable
  examples. Set in columns across a wide dialogue so it reads as a guide
  rather than a long scroll.
- The clip editor is a full-width editing surface (up to 1600px), with
  waveform heights scaled to the viewport and a scrolling body so Download
  never slides out of reach on a short display.
- Keyboard: `/` search, `?` help, `Esc` clear → reset → close
- Back-to-top in the gutter; floats centred on tablet and phone
- Responsive; no build step, single HTML file

### Not built yet

- **Topics, un-hyperlinked guests, interviewer roles** → needs the AI pass
  (~$7 batched). This is the one remaining gap in Harold's original ask.
- The 55 episodes with no feed transcript (~$9.52 via Google STT)
- One broken transcript link on Podbean's side ("MLK in Memphis" 404s);
  `python3 ingest/transcripts.py --retry` will pick it up if they fix it
- **Deployment.** First attempt on Coolify failed and taught us three things,
  all now fixed: Coolify runs its own health check (not the Dockerfile's), it
  shells out to `curl` which `python:3.12-slim` doesn't have, and — the real
  bug — building the archive *before* starting the server means nothing is
  listening during the build, so the container is killed as unhealthy and the
  build restarts forever. The container now opens the port in **1 second** and
  fetches the archive in the background.
  **Coolify's "Ports Exposes" must be set to 8000**; it defaults to 3000.
- Off-box backups of the volume. It is the only copy of the scraped archive.
- Failure notification on the refresh loop (it logs to stderr; nobody watches stderr)
- A styled embed widget for laborheritage.org. The `?q=` deep link means a
  plain search box already works — the widget is polish, not plumbing.

## Scorecard against Harold's original email

| Ask | Status | Notes |
|---|---|---|
| Scrape existing + future episodes | ✅ **Done** | 200 episodes, re-runnable weekly. Last ~2 years — see the feed cap. |
| Searchable database | ✅ **Done** | Full-text, boolean, fielded, six sorts, filters. |
| Find older shows to replay | ✅ **Done** | Search, filter, sort by duration for a slot of a given length. |
| Check if a segment is "in the can" | ✅ **Done** | Re-air detection incl. cross-show. Better than asked. |
| Catalogue **guests** | 🟡 **Partial** | 232 names — but only those the producers hyperlinked. |
| Catalogue **topics** | ❌ **Not built** | Needs AI. Hashtags tested and useless (`#LaborHistory` on 176/200). |
| Catalogue **interviewers** | ❌ **Not built** | Needs AI, but it's a two-host show — a small job. |
| Public search box on laborheritage.org | 🟡 **Works, not deployed** | `?q=` deep links make a plain search box work already; needs hosting. |

**Delivered beyond the ask** — neither was requested, both came free:

| | |
|---|---|
| Search what was *said* on air | 144 transcripts, 882k words, pulled from the feed |
| Jump to the exact moment | Click a timestamp, hear it — no Podbean cooperation needed |
| Spreadsheet export | Whatever's on screen, ready for Sheets or Excel |
| **Cut a broadcast-ready clip** | Waveform, drag handles, snap to silence, lossless MP3 out |
| **Share a search or a moment** | Copy the address bar; it carries the whole state |

**The fair summary:** the internal tool Chris described is finished and then
some. The one genuine gap is **topics** (and the guests who weren't
hyperlinked) — everything deterministic has been mined, and that last piece
needs a model reading prose. It's the cheap pass: ~$7 batched.

Don't tell the client it's finished. Tell them the archive works, the re-air
problem is solved, search now reaches the audio — and topics are the next step.

## For the client (plain language — liftable into an email)

> **What's working now**
>
> - **Both shows in one searchable place** — 200 episodes, 143 hours, updating
>   automatically as new ones publish.
> - **Search that reaches inside the audio.** 144 episodes have full
>   transcripts, so searching finds what was *said*, not just what was written
>   in the show notes. Searching "picket line" turns up 59 episodes — only two
>   of which mention it in the notes.
> - **Jump straight to the moment.** When your words were spoken aloud, the
>   result shows the exact times. Click one and the episode plays from that
>   second — no scrubbing.
> - **"Have we run this already?"** — the archive spots when the same programme
>   has aired more than once, as an encore or on both shows, and says so under
>   the episode. It found 22 encores and 5 programmes that ran on both.
> - **Browse by name.** The people, bands, museums and books you link in your
>   show notes have become a clickable index — 232 of them. Nothing had to be
>   tagged by hand.
> - **Proper search tools** — exact phrases, AND/OR/NOT, wildcards, searching a
>   single field, and six ways to sort. There's a Help button explaining all of
>   it, with examples you can click to run.
> - **Export to a spreadsheet.** Whatever you're looking at — filtered however
>   you've filtered it — downloads as a file that opens straight in Google
>   Sheets or Excel, with dates, lengths and yes/no columns ready to sort and
>   filter. Each row carries links to the episode, its transcript and the audio.
>
> **What's next**
>
> - **Topics and full guest lists.** Right now we catch the guests you happened
>   to hyperlink. Reading everything properly — every guest, the interviewer,
>   and what each episode was actually about — is the remaining step, and it's
>   what turns this into a true catalogue.
> - **The last 55 episodes** don't have transcripts in the feed; we can fill
>   those in cheaply.
> - **The public search box** for laborheritage.org.
>
> **Two things worth knowing**
>
> The transcripts come from your own feed — the ones your editing produces get
> published automatically, and we simply read them. Nothing new for you to do,
> and no dependency on any one tool.
>
> They're machine transcripts though, so names take some damage (one renders
> Elise as "Lisa"). Good enough to find things; not proofread documents.
>
> Also: the podcast feed only hands out the most recent 100 episodes per show,
> so this covers roughly the last two years. Going further back means pulling
> from Podbean's back-end.

## Files

| Path | What it is |
|---|---|
| `ingest/ingest.py` | RSS → SQLite. Idempotent, keys on `<guid>`. Also the weekly-cron path. |
| `ingest/transcripts.py` | Podcast 2.0 `.srt` → `segments`. Idempotent; `--retry` re-attempts failures. |
| `refresh.py` | Runs all three pipeline steps in order; `--loop 24h` schedules itself. |
| `docs/export-spec.md` | Export design + the CSV details that decide whether it imports cleanly. **Built.** |
| `docs/audio-editor-spec.md` | Browser-side clip editor: design, decisions and verification. **Built.** |
| `ingest/enrich.py` | Deterministic enrichment, **no AI**. Re-airs + linked entities. Safe to re-run. |
| `ingest/schema.sql` | Tables, FTS5 index, triggers. Already has `transcript_source` and a source-agnostic `segments` table. |
| `serve.py` | JSON API + serves the UI and its JS. Stdlib `http.server`; swap for FastAPI at deploy. |
| `static/index.html` | The whole UI — markup, styles and app code. No build step. |
| `static/mp3cut.js` | Lossless MP3 clip extraction. `probeMp3()` measures each file; `cutClip()` copies frames. |
| `static/waveform.js` | Peaks at 8 kHz, IndexedDB cache, canvas rendering, snap-to-silence. |
| `static/index.html` | The whole interface — single file, no build step. |
| `README.md` | Run instructions, API reference, useful SQL. |
| `docs/lhf-podcast-spec.html` | **Client-facing** planning memo (shared with them). Tier ladder, no cost-of-work talk. |
| `docs/build-plan.html` | **Internal** build plan. Google setup walkthrough, VPS sizing, phases, risks. |
| `docs/reply-descript.md` | The short email reply about Descript transcripts (sent). |
| `docs/transcripts-plan.md` | **Phased plan for transcripts.** Read before touching this area. |

Both `docs/*.html` are also published as artifacts — same URLs update in place
if edited and republished.

---

## What we learned today (the useful part)

**1. The RSS feed caps at 100 episodes per show.** Every pagination parameter
is ignored; the website's "Load More" is JavaScript. So we have roughly the
last two years (Sept 2024 → Aug 2026). Anything older needs the **Podbean API**
(OAuth, has an episode-list endpoint) or a dashboard export. This is the real
answer to "how do we get the whole archive" — more useful than the episode
count itself.

**2. Their problem is real and measurable.** 22 of 200 episodes are encores
(11%), and 5 programmes ran on *both* shows. That's evidence to show them, not just
an assertion.

**3. Show notes are hand-curated data.** 196 of 200 episodes contain
hyperlinks, and the producers link guests, bands, museums and books. Frequency
filtering separates them cleanly from boilerplate — only 5 entities were
dropped as furniture, 232 kept. Nobody had to tag anything.

**4. Hashtags are a dead end.** Tested hoping for free topics:
`#LaborHistory` appears on 176 of 200 episodes, `#1u`/`#unions`/`#laborradiopod`
on ~95 each. They're boilerplate, not classification. **Topics genuinely
require reading the prose** — this is the hard wall, and it's why Tier 2 exists.

**5. Estimates held.** Actual episode lengths average 54 min (Power Hour) and
32 min (Labor History Today) against the 55/30 assumed in the client memo, so
the cost figures there are sound.

**8. Jump-to-moment needed nothing from Podbean.** Their audio URLs return
`Accept-Ranges` and `Access-Control-Allow-Origin: *`, so we host our own player
and seek precisely rather than depending on a `?t=` parameter their pages don't
support. Checked before designing around it.

**7. 145 of 200 episodes already publish full transcripts in the RSS feed**
(Podcast 2.0 `<podcast:transcript>` tags → `.srt` files, timestamped to the
millisecond, free). Only 55 episodes need machine transcription — about $9.52,
not $102. Descript turns out to be largely irrelevant: Chris already publishes
those exports to Podbean as part of his normal workflow, so we read the feed,
not their API. See `docs/transcripts-plan.md`.

**6. Descript changes the plan for the better.** LHF edits in Descript, which
means human-corrected transcripts likely already exist for many episodes.
That's *better* than machine transcription, because proper nouns — guest names,
union locals — are the thing automated STT gets wrong and the thing this
project most depends on. Schema already handles the hybrid via
`transcript_source`.

---

## Open threads (waiting on the client)

1. **Descript export format** — SRT preferred (timestamps enable jump-to-moment);
   Word or plain text also fine for search only.
2. **Have speakers been named** in the Descript projects, or left as
   "Speaker 1"? Named speakers would give attribution for free.
3. **How far back do the Descript projects go** — they've deleted some over time.
4. **Podbean API credentials**, if we want the pre-2024 archive.

Nothing is blocked on these. They're slow-moving; the interface work continues
regardless.

---

## Where we stopped

Everything listed under "Working now" is built, verified and documented. The
database rebuilds from nothing in ~2½ minutes via `refresh.py`.

The natural next moves, in order of value:

1. **Deploy it.** The client can't see any of this until it has a URL.
   Coolify + a Dockerfile; ~an hour. Nothing else matters until this happens.
2. **The AI pass** (~$7) — topics, un-hyperlinked guests, interviewers. The one
   remaining gap in the original ask.
3. **The 55-episode transcript gap** (~$9.52).

---

## Data ownership, scheduling, export

Three related concerns. Status differs for each.

### 1. Storing the scraped text — ✅ already done

Everything is stored locally, nothing is re-fetched at query time:

| | |
|---|---|
| `episodes.transcript_text` | 144 episodes, 4 MB |
| `segments` (timestamped passages) | 14,937 rows, 4 MB |
| `description_html` + `description_text` | all 200 episodes |
| Audio | **not stored** — only the URL |

Database is 33 MB. Podbean's transcript URLs and audio URLs are recorded but
never depended on after ingest, so CDN link rot can't take the archive down. If
both feeds vanished tomorrow, everything searchable still works.

Audio deliberately isn't stored — ~12–24 GB, and streaming from their CDN is
free and fast. Worth revisiting only if clip export gets built.

### 2. Timed updates — ✅ mechanism built, ⚠️ not yet scheduled anywhere

`refresh.py --loop 24h` now runs the pipeline on a schedule and keeps itself
alive — verified cycling correctly. It works the same on a laptop, in Docker,
and on Coolify without depending on a host scheduler, and backs off on repeated
failure instead of hammering the feed.

**What's still missing is choosing where it runs.** Nothing is scheduled on any
machine yet. Once deployed, either run the container with
`--loop 24h --quiet-if-nothing-new` as its command, or use a host cron:

```cron
# Sundays 04:00 — after both shows are out
0 4 * * 0  cd /path/to/digital-asset-manager && /usr/bin/python3 refresh.py >> /var/log/lhf-refresh.log 2>&1
```

Still worth adding when wiring it up:

- **Failure notification.** The loop logs failures to stderr and backs off, but
  nobody is watching stderr. An email or webhook on repeated failure is the
  missing piece — a silently broken updater is how this rots.
- **Back up the SQLite file off-box first.** The feeds are re-scrapeable for
  free; 882k words of transcript are not worth re-fetching casually.

### 3. Export — ❌ not built, and worth doing

Currently JSON via the API only. Their organisation includes Library of
Congress people, so export formats will be asked about early.

**Build it from scratch — no package needed.** Python's stdlib (`csv`, `json`,
`xml.etree`) covers every format below, and staying zero-dependency has been
genuinely valuable: no venv, no install, `python3 refresh.py` just works. A
library would buy nothing here.

Formats worth supporting, roughly by demand:

| Format | For | Effort |
|---|---|---|
| CSV | Everyone. Opens in Excel, which is how most of this org works. | trivial |
| JSON | Machine use, already the API shape | done |
| SRT / VTT | A single episode's transcript, back out in a standard format | trivial |
| Plain text / Markdown | Readable transcript for reference or quoting | trivial |
| Dublin Core XML | The library-standard metadata answer. ~20 lines. | small |
| BibTeX / citation | Researchers quoting an episode + timestamp | small |

Scope it as "export whatever the current search returns" rather than a separate
reporting screen — a button next to Sort that exports the visible result set,
filters and all. That's one endpoint and one control, and it covers most of what
anyone actually wants.

## Who these users actually are

Worth holding onto, because it changes which features matter. They wear three
hats at once:

**Podcast producers** — editing, clips, promos, show notes. Descript workflow.

**FM radio broadcasters** — the Power Hour airs on WPFW 89.3FM. This is the one
easiest to forget and it has the hardest constraints: broadcast needs *exact*
durations, clean in/out points, and run sheets. "I have a 4-minute hole to
fill" is a real question with a real answer, and no search tool built for
podcasts ever answers it.

**Labor history researchers** — provenance, citation, "when did she say that,
and can I quote it." Their organisation includes Library of Congress people,
so cataloguing conventions land with them.

Two things we built read differently in that light:

- **Sort by longest / shortest** isn't a nicety — it's the beginnings of a
  broadcast tool. "Show me segments between 3 and 5 minutes" would finish it.
- **Re-air detection** matters more for broadcast than podcast. Repeating a
  segment on air three months later is a scheduling decision with an audience
  that noticed the first time.

## Brainstorm seeds — producer and broadcast tools

Not planned, just captured. Roughly cheapest first:

- **Duration-range filter** ("between 3 and 5 minutes") — trivial, and directly
  serves the fill-a-slot problem.
- ~~**Shareable moment links**~~ ✅ **built** — `?ep=123&from=522&to=549`.
- **Copy a citation** — episode, date, show, timestamp, and the spoken line.
  Free, and researchers will want it. LC people especially.
- ~~**Mark in/out on the player track**~~ ✅ **built** — and with no `ffmpeg`
  and no server load at all, which the note above assumed would be necessary.
- **Run-sheet view** — pick segments, see cumulative duration against a target.
  Pure broadcast, and nothing else on the market does it.
- **"Not aired since"** — episodes not run in N months, sorted by age. Turns the
  re-air data into a scheduling worklist rather than a lookup.

The thread: they don't just need to *find* things, they need to *use* them on
air. Search was the prerequisite; the tools above are the actual job.

## Clip extraction — built

Spec and verification in `docs/audio-editor-spec.md`. The headline decisions:

- **Export by copying MP3 frames, not re-encoding.** A clip is the frames
  between two timestamps, copied byte-for-byte. Bit-identical to the source,
  instant, no library. A 2-min clip is 2.9 MB at 192 kbps.
- **Cut accuracy is one frame (26 ms)** — inaudible in speech. Measured at
  0.008–0.022 s across four episodes, confirmed by exact byte match against
  the source.
- **Never assume the bitrate.** The archive runs 128, 192 *and* 256 kbps. A
  rate hardcoded from one episode returns HTTP 416 on a smaller file and cuts
  in the wrong place on a larger one. `probeMp3()` measures each file — ID3
  length for where audio starts, first frame header for the rate.
- **Zero server load.** Range requests go to Podbean's CDN; we serve a modal.
- **Waveform decoded at 8 kHz** for display only (101 MB transient, cached as
  peaks in IndexedDB). Full-rate decode would be 555 MB and is never needed.
- **No wavesurfer** — reversed from an earlier draft. With no decode needed for
  export, the requirement is just peaks + two handles + a playhead: ~150 lines
  of canvas, full control of the look, no 100 KB dependency.

Five phases, ~2 days. Risk is in the waveform decode, not the cutting.

## Picking it back up

**If you want the fastest visible win:** the public embed. The search UI already
works; packaging it as an iframe-able page for laborheritage.org is mostly
CSS and a read-only flag, and it's the deliverable Harold can show people.

**If you want to unblock the real feature set:** Tier 2 extraction. Run a
batched AI pass over `description_text` → guests, topics, interviewers into the
`people` / `topics` tables (already in the schema, currently empty). Roughly
$7 for the whole archive via the Batch API. The deterministic entities from
`enrich.py` are ground truth — let them win on conflict, and use them to check
the model's output.

**If the client comes back with transcripts:** write a `ingest/descript.py`
that parses SRT/DOCX into the `segments` table with `transcript_source =
'descript'`. Nothing else changes — extraction, search, and UI all read from
the same place.

### Tests

```bash
node tests/test-waveform.mjs        # pure: peak reduction + snap-to-silence
node tests/verify-clips.mjs         # live: needs the server running + network
```

`verify-clips.mjs` picks episodes at random each run, so it covers the bitrate
spread over time rather than pinning one fixture. It checks duration, filename,
and — the one that matters — that the clip's bytes appear **verbatim** in the
source at the expected offset. That single check proves the cut is both
correctly positioned and genuinely lossless.

### Deploys and stale browsers

`serve.py` sends `Cache-Control: no-cache` on everything. There is no build
step and no fingerprinted filenames, so a file's URL never changes when its
contents do — without revalidation a browser can keep running a months-old copy
of the app after a deploy, with nothing to indicate it.

This is not theoretical: a bug fixed and deployed appeared **unfixed locally**
because one tab held a stale `index.html`. Twenty minutes went into debugging
code that was already correct. The giveaway was a status string in a screenshot
that had been deleted from the source two commits earlier.

If a fix seems not to have landed, check for a stale page before checking the
code — and `git log -S'some string from the screen'` will date it exactly.

### Known rough edges

- `serve.py` is stdlib `http.server`. It now takes `--host`/`LHF_HOST` so a
  container can bind `0.0.0.0` (verified both ways: `0.0.0.0` answers on the
  LAN address, the default refuses it). Threaded and fine for this traffic, but
  it is not a hardened server — keep it behind Coolify's proxy.
- Repo: **https://github.com/Catskill909/lhf-tools** (`origin/main`). Check its
  visibility — it was pushed to an existing empty repo and nobody has confirmed
  whether it is public or private. Nothing sensitive is tracked (no database,
  no keys) but it is a client project.
- The Docker image has never been built. The entrypoint's branching was tested
  with a stubbed `python3` (all four paths, including the first-run bootstrap
  and the worker's wait-for-database), and Python 3.12 compatibility was checked
  by auditing every import — but that is not the same as a build.
- Ingest has no test suite; it's deterministic and rebuilds in ~2½ minutes, so
  `refresh.py` → check counts is the test. The clip editor does have tests
  (`tests/`) — see "Tests" below.
- The waveform needs the whole episode (30–105 MB) before it draws. The modal
  is usable without it and peaks are cached after the first open, but the first
  open on a slow connection is a wait.
- **Always use `refresh.py`.** The three steps must run in order; running
  `ingest.py` alone against a fresh database leaves no tags and no re-airs.
  Search degrades gracefully now rather than 500ing, but the data is missing.
- One transcript URL in Podbean's feed 404s ("MLK in Memphis") — their broken
  link, not ours. `transcripts.py --retry` re-attempts failures.
- The client memo's cost scenarios assume backlogs of 100/300/600 per show.
  Still valid as projections, but we now know the *feed* only reaches 100.
