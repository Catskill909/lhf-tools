# Labor Heritage Media Archive — Handoff

**Status:** **deployed and live on Coolify**, real data, checking the feeds every
15 minutes.
Feature-complete for everything achievable without AI.
**Local, not deployed:** tablet touch support for the audio editor and the
tap-safe hover-disclosure pass are built. The compact phone transcript is also
built after real-phone review. Paul confirmed the core editor touch interaction
and first-tap transcript playback on a real iPad; the broader device/rotation
matrix remains open (`docs/touch-dev.md`).
**Last worked:** 26 August 2026. Built from nothing on 3 August.
**Client:** Labor Heritage Foundation — Harold Phillips (producer), Chris Garlock
and Elise Bryant (hosts), Patrick Dixon.

---

## What actually needs doing

**If it is not in this box, it is not a task.** Everything else in these
documents is reasoning — parked ideas, rejected options, trade-offs — recorded
on purpose and easily mistaken for a backlog. See *How to report work here* in
`CLAUDE.md` for the four buckets and why they are kept apart.

**Last reviewed: 14 August 2026.**

### 🔥 DO — something bad happens if ignored

1. **Deploy and run the complete-archive backfill in production.** The importer
   and renamed *Labor Heritage Media Archive* are built and verified locally:
   785 unique episodes across *Labor Heritage Power Hour* (181), *Your Rights at
   Work* (185), and *Labor History Today* (419); 17,316 transcript passages; no
   duplicate GUIDs or permalinks; a second pass makes zero updates. Production
   still has the old 200-episode state, so the client request remains incomplete
   until deployment and the one-time command run. Take a verified snapshot
   first, then run backfill, the normal refresh, and one explicit enrichment
   rebuild. See
   `docs/feed-backfill-investigation.md`.

**Backups are handled** — confirmed by Paul, 9 August 2026: the VPS takes
snapshots *and* full backups on a two-week retention, and the archive package
export is a third, app-independent copy. Earlier drafts of this file listed
"somewhere to keep the backups" as an open task; **that was stale and is
resolved.** The `backup.py` tooling below is still the right way to pull a
verified snapshot by hand.

### 🐞 FIX — broken, reproducible, not urgent

*Nothing outstanding.*

### ❓ ASK — blocked on someone else

1. **Send `docs/ask-vocabulary.md`** — drafted, not sent. Asks whether this
   archive should share the Labor Arts & Culture Database's 34-term topic
   vocabulary. Their answer unlocks **topics, guests, interviewers and the admin
   screen** — all built or designed, all waiting on this one reply.
2. **The four open threads below** (Descript formats, speaker names, how far the
   projects go back, and what happens to episodes that fall off the feed).
   Slow-moving; nothing is blocked on them.
3. **Finish the touch release matrix before making a broad device-support
   claim.** Real-iPad use confirmed the core editor interaction and the
   transcript first-tap fix. Rotation/loading/download edge cases plus Android
   tablet and Windows hybrid checks remain in `docs/touch-dev.md` → Phase 4.

### 💭 NOTE — nobody has to do anything

Here so they are not mistaken for the lists above.

- **Clip search/sort/mobile wiring has structural coverage; row audio event
  ordering remains browser-only.** A known property, not a defect — the query
  and storage logic have 53 pure checks, the new interface has 13 structural
  checks, and the export path is proven.
- **Clip titles don't come from the transcript.** Designed, not built; see
  `docs/clip-library.md` divergence 5. Nobody has asked for it.
- **Everything under a *Brainstorm*, *Parked* or *Where it could go* heading**
  anywhere in these documents. Ideas, not commitments.

---

**Two things a new reader should know before anything else:**
1. **The archive is not disposable.** RSS is capped at 100 episodes per channel,
   while the public-page recovery source is an undocumented website surface and
   does not reproduce corrections or derived catalogue data. `backup.py` exists;
   see **Backups**.
   `episodes.last_seen_in_feed` records what the feed still carries, and
   `python3 ingest/ingest.py --stats` names anything it no longer does.
2. **The audio editor was rebuilt** — playhead, transport, 10 ms waveform,
   keyboard marking. `docs/audio-editor-dev.md` opens with a status summary.

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
~2½ minutes (most of it fetching ~147 transcripts), so don't be precious about
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

**Scraping has gone as far as it goes.** The AI tier is now written and wired
end to end (`ingest/extract.py`, plus topics/guests/interviewers through the
API, filters, export and UI) but **has never been run — there is no AI in
production and no extracted data in the database.** It needs a key, a client
decision, and an admin screen to run it from. See `docs/ai-layer.md`.

### Working now

**Search**
- Production: 200 episodes, 143.1 hours, both shows, updating automatically
  from the feeds. Local retained archive: 203 episodes, 145.4 hours; the three
  extra rows are the restoration task at the top of this file.
- Full-text with ranked results and highlighted excerpts
- As-you-type prefix matching (`carsie bla` finds Carsie Blanton)
- Query syntax: `"exact phrase"`, `AND`/`OR`/`NOT`, `(grouping)`, `organiz*`
  truncation, `title:strike` field search, `NEAR(coal mine, 5)` proximity
- Six sort orders: best match, newest, oldest, title A–Z, longest, shortest
- Filters: show, year, encores-only, and by tag — with All / Reset to clear
- Browser-safe results: 50 cards at a time, automatic progressive loading plus
  an accessible Load more button, accurate “shown of total” status, stable page
  boundaries, and cancellation of obsolete as-you-type requests. Export still
  uses the complete matching set rather than only the loaded cards.

**Transcripts** *(free — pulled from the feed, no AI, no vendor)*
- Production is 147 of 200; the retained local archive is 147 of 203 because
  the three restored rows have no transcript: **15,294 passages, 904,266 words**
  (verified 14 Aug 2026)
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
- **Choose the scope** — this search, or the whole archive. Both counts are
  always visible, so a file quietly holding 78 of 203 episodes can't happen by
  accident. Calls `search()` rather than reimplementing the query, so the file
  and the screen can't drift apart.
- CSV / TSV / JSON, written for spreadsheet import: UTF-8 BOM (Excel mangles
  "No Pasarán" without it), ISO dates that parse as dates, numeric durations
  that sum, `TRUE`/`FALSE` that Sheets treats as booleans
- Three URL columns at different fidelities — Podbean page, original `.srt`,
  and our cleaned transcript at `/episode/<id>/transcript` — plus `guid` last,
  the only key that survives a rebuild
- **"What's in the file, exactly"** lists every column and shows the first two
  rows of the real file, fetched through the same endpoint as the download via
  `?limit=` — a preview assembled separately could disagree with the file
- **Archive package (.zip)** — the catalogue, every transcript, all 15,294
  timed passages and a README that explains the lot. **12 MB of content, 3.8 MB
  zipped**, built in the browser by `static/zip.js` with no dependency. Named
  `-complete` or `-filtered` so a partial export can never be mistaken for a
  backup. This is the app-independent copy: plain CSV, JSON and text that
  another developer could rebuild the catalogue from.
- Transcript text deliberately excluded from the *spreadsheet*: ~49k chars per
  episode against a 50k-character cell cap would truncate silently. The package
  carries them as real files instead.
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
- Two waveforms, each with its own **time ruler** — whole episode for context,
  zoomed selection for precision — with draggable in/out handles, arrow-key
  nudge (±0.1s, ±1s with Shift), and a live in / out / length readout
- **A real transport** between the two waveforms: play/pause, back-to-start,
  playhead timecode, and **Repeat**, which keeps the selection going round *and
  follows the handles as you move them*. `Space` plays/pauses, `0` returns to
  the start of the selection (`Home` too, where the keyboard has one — Mac
  laptops do not, which is why the reachable binding is a digit).
- **Click or tap the overview to listen** from that point; drag it to move the
  selection, as before. The two are told apart by whether the pointer travels,
  because a short selection is only a pixel or two wide on that waveform.
- **Zoom** (− / + or scroll wheel) reports the **window**, not the padding.
  While the selection fits it stays centred; past that the view follows the
  edge you last touched, so a 30-second selection can be inspected at half a
  second. **⤢** reframes the selection.
- **The zoomed waveform is drawn from 10ms peaks** with an RMS body inside a
  peak outline, on a dB scale, and the episode's own measured silence floor
  drawn as a line — so pauses between words are visible and quiet audio is
  distinguishable from nothing.
- **Hear the start / hear the end** — the clip's own first and last three
  seconds, clamped to the selection at both ends, so neither ever plays material
  the export does not contain. They replaced *Audition in / out*, which
  straddled each mark by a fixed two seconds and therefore played past the
  out-point and collapsed into each other on short clips
- **Drag across the zoomed waveform to select** — both marks in one movement,
  told apart from a click by distance travelled. Clicking it instead places the
  playhead without starting playback, which is what `I` and `O` mark against
- **Mark by ear**: `I` and `O` set in/out at the playhead; `[` and `]` jump the
  playhead between the pauses in speech; the arrow keys walk it along by 0.1s
  (1s with shift) when no handle holds focus
- **One step of selection undo** on `⌘Z`, and pressing it again puts the
  selection back. In memory only — it dies with the open editor, so it adds
  nothing to the two things the browser persists
- **Back to the start** (the skip-back button, or `0` / `Home`) returns the
  playhead *and the view* to the beginning of the selection
- **Snap to silence** puts a cut in the gap between words instead of through
  the middle of one. It reads the same 10ms tier, so it lands *in* the gap
  rather than on the half-second grid it used to be quantised to.
- Downloads as MP3 **cut straight from the source with no re-encoding** — the
  clip is bit-identical to the broadcast audio, and lands within one frame
  (26 ms) of the requested point. Verified by exact byte match against the
  source at 128 and 192 kbps.
- File name and ID3 tags carry show, date and timecode, so a clip found in a
  folder months later still says where it came from
- Audio streams from Podbean's CDN direct to the browser; peaks are cached in
  IndexedDB so an episode is only ever downloaded once
- **Tablet touch is built locally; core real-iPad use passed.** The
  editor's handles, rulers and waveforms use one Pointer Events lifecycle with
  capture and cancellation cleanup; touch targets expand to 44px without
  thickening the edit marks. Below 768px, phones get a tablet/computer notice
  instead of a clipped editor. Hover-revealed transcript, player and library
  actions are exposed directly on tap devices, so the first tap performs the
  action. The phone transcript is a separate find/listen/read surface with its
  editing routes and large selection lesson removed; a 390×844 emulated-touch
  render gives its prose 76% of the viewport. The broader Phase 4 matrix is
  still open. This is not deployed yet.

**Clip library** *(built 9 August 2026 — `docs/clip-library.md`)*
- **`＋ Add to library`** in the editor opens a **save dialogue**: the span, an
  editable title, and **labels**. It saves **without closing the editor**, which
  is the whole point — pulling three quotes from one episode was three round
  trips. Nudge a handle and save again for a second version of the same quote.
- **Labels** are free text, many-to-many, derived (no registry). `promo` folds
  into an existing `Promo`. They persist across saves in a session.
  **"Labels", not "tags"** — `Tags` already means the 232 hyperlinked entities.
- The **Clips** counter in the masthead opens the list: play in place with a
  **scrubber on the live row**, rename inline, download a single clip from a row
  icon, `⋯` for Edit/Remove, ten-second undo and date grouping. Every non-empty
  library has **full clip search** across title/show/date/labels and a matching
  **sort menu** (best match, saved date, title, length), plus a **top-labels
  bar** (six most used, `+n more`, two labels AND). Phone controls and row
  actions are 44px and the modal stays inside the dynamic viewport.
- **Download all** packs them into one zip — stored, not deflated, so the bytes
  stay bit-identical — with a dialogue to name the file and add a note. The note
  and a full listing go in as `clips.txt`. Filtered, the button says *"Download
  these 3"* and the file is named `-filtered`.
- **Stored in `localStorage` only.** Versioned; a wrong version reads as a miss.
  Every surface that writes says so, once, quietly. This is the first data in
  this application a user can actually lose — see **What lives in the browser**.

**Sharing**
- Every search is reflected in the address bar — filters, tag, sort and all —
  so a result set can be sent to a colleague as a link
- `?ep=123&g=2245e4af&from=522&to=549` opens the clip editor on a single
  moment. `g` is the first 8 hex of `sha1(guid)` — ids are reassignable, so
  the server compares and believes the fingerprint. **Copy link** on a clip
  row builds it; older links without `g` still resolve by id.
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

**Deployment is done.** It is live on Coolify and checking the feeds every 15
minutes. The
first attempt failed and taught three things, all fixed and all written up in
README.md under "Coolify settings that matter": Coolify runs its own health
check rather than the Dockerfile's, it shells out to `curl` which
`python:3.12-slim` does not ship, and building the archive *before* starting the
server means nothing is listening during the build, so the container is killed
as unhealthy and the build restarts for ever. The container now opens the port
in **1 second** and fetches the archive behind itself. **Coolify's "Ports
Exposes" must be 8000**; it defaults to 3000.

### Not built yet

- **Topics, un-hyperlinked guests, interviewer roles** → the code is written
  and tested (`ingest/extract.py` + full API/UI path) but **has never been
  run**: no key, no data, nothing live. $4.35 for the archive, ~2¢ per new
  episode. The one remaining gap in Harold's original ask, now a decision
  rather than a build. See `docs/ai-layer.md`.
- **An admin interface** → the blocker for the above, and for staff notes, tag
  corrections and `replayed_at`, all of which have schema and no UI. Needs auth.
- Production has 53 episodes with no feed transcript; the retained local
  archive has 56 (~$9 via Google STT) because its three restored rows have no
  transcript. Production is 147/200 covered and local is 147/203 as verified
  14 August 2026. The gap is nearly all old episodes. It is also
  the only outstanding job that needs the *audio*, so it is the only one that
  can expire if Podbean ever deletes rather than unlists.
- One broken transcript link on Podbean's side ("MLK in Memphis" 404s);
  `python3 ingest/transcripts.py --retry` will pick it up if they fix it
- ~~**Somewhere to keep the backups.**~~ ✅ **Resolved** — confirmed 9 August
  2026: the VPS runs snapshots plus full backups on a two-week retention, and
  the archive package is an app-independent third copy. `backup.py` remains the
  way to pull a verified snapshot by hand; see **Backups**.
- Failure notification on the refresh loop (it logs to stderr; nobody watches
  stderr). A silently broken updater is how this rots, and the symptom — an
  archive that quietly stops growing — is one nobody notices for months.
- A styled embed widget for laborheritage.org. The `?q=` deep link means a
  plain search box already works — the widget is polish, not plumbing.

## Scorecard against Harold's original email

| Ask | Status | Notes |
|---|---|---|
| Scrape existing + future episodes | ✅ **Done** | 203 retained episodes, re-runnable weekly. Last ~2 years — see the feed cap. |
| Searchable database | ✅ **Done** | Full-text, boolean, fielded, six sorts, filters. |
| Find older shows to replay | ✅ **Done** | Search, filter, sort by duration for a slot of a given length. |
| Check if a segment is "in the can" | ✅ **Done** | Re-air detection incl. cross-show. Better than asked. |
| Catalogue **guests** | 🟡 **Partial** | 232 names — but only those the producers hyperlinked. |
| Catalogue **topics** | 🟡 **Built, not run** | Needs AI + a client decision. Hashtags were tested and are too repetitive to classify subjects. $4.35 for the archive. |
| Catalogue **interviewers** | 🟡 **Built, not run** | Same pass. It's a two-host show — a small job once it runs. |
| Public search box on laborheritage.org | 🟡 **Works, not deployed** | `?q=` deep links make a plain search box work already; needs hosting. |

**Delivered beyond the ask** — neither was requested, both came free:

| | |
|---|---|
| Search what was *said* on air | 147 transcripts, 904k words, pulled from the feed |
| Jump to the exact moment | Click a timestamp, hear it — no Podbean cooperation needed |
| Spreadsheet export | Whatever's on screen, ready for Sheets or Excel |
| **Cut a broadcast-ready clip** | Waveform, drag handles, snap to silence, lossless MP3 out |
| **Share a search or a moment** | Copy the address bar; it carries the whole state |

**The fair summary:** the internal tool Chris described is finished and then
some. The one genuine gap is **topics** (and the guests who weren't
hyperlinked) — everything deterministic has been mined, and that last piece
needs a model reading prose. That pass is now written and wired end to end but
**never run**: $4.35 for the whole archive, ~2¢ per new episode.

Don't tell the client it's finished. Tell them the archive works, the re-air
problem is solved, search now reaches the audio — and topics are the next
decision, not the next build. It needs their yes, a key, and an admin screen to
run it from.

## For the client (plain language — liftable into an email)

> **What's working now**
>
> - **Both shows in one searchable place** — 200 episodes, 143 hours, updating
>   automatically as new ones publish.
> - **Search that reaches inside the audio.** 147 episodes have full
>   transcripts, so searching finds what was *said*, not just what was written
>   in the show notes. Searching "picket line" turns up 59 episodes — only two
>   of which mention it in the notes.
> - **Jump straight to the moment.** When your words were spoken aloud, the
>   result shows the exact times. Click or tap one and the episode plays from that
>   second — no scrubbing.
> - **"Have we run this already?"** — the archive spots when the same programme
>   has aired more than once, as an encore or on both shows, and says so under
>   the episode. The live archive currently carries 21 encores.
> - **Browse by name.** The people, bands, museums and books you link in your
>   show notes have become a clickable index — 232 of them. Nothing had to be
>   tagged by hand.
> - **Proper search tools** — exact phrases, AND/OR/NOT, wildcards, searching a
>   single field, and six ways to sort. There's a Help button explaining all of
>   it, with examples you can click or tap to run.
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
> - **The remaining 53 live episodes** don't have transcripts in the feed; we can fill
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

**The quote above is the message as sent — left exactly as it went out, so the
figures in it are the figures Harold was given.** The retained archive is now
203 episodes with a **56-episode transcript gap**: the three restored rows add
to the retained total but do not carry transcripts. The 100-episode limit also
stopped being theoretical when those episodes dropped off; their recordings
still play. `docs/client-guide.md` carries the current numbers and is the
document to send.

## Files

| Path | What it is |
|---|---|
| `ingest/ingest.py` | RSS → SQLite. Idempotent, keys on `<guid>`. Also the weekly-cron path. |
| `ingest/transcripts.py` | Podcast 2.0 `.srt` → `segments`. Idempotent; `--retry` re-attempts failures. |
| `refresh.py` | Runs all three pipeline steps in order; `--loop 15m` schedules itself. Skips enrichment when the feeds brought nothing. |
| `CLAUDE.md` | The constraints and traps that are easy to break without knowing them, for whoever (or whatever) picks this up. Read `HANDOFF.md` first. |
| `docs/export-spec.md` | Export design + the CSV details that decide whether it imports cleanly. **Built.** |
| `docs/export-dev.md` | The export as the client's full backup of their Podbean archive — catalogue, transcripts, artwork, audio. **Not built.** Explains why it is two exports: 5 MB of text against 8–12 GB of media. |
| `docs/client-guide.md` | **Send this one.** Feature + usage guide for LHF, with screenshot slots. Every figure verified against the database. |
| `docs/audio-editor-spec.md` | Browser-side clip editor: the **export** design (frame copy, bitrate probing) and its verification. **Built.** The editing *surface* it describes has since been rebuilt — see the dev doc below. |
| `docs/audio-editor-dev.md` | Audit of the editing *surface* + phased plan. **Phases 1–7 built; Phase 8 tablet touch built locally, core iPad use confirmed.** Opens with a status summary. Read before touching the editor UI. |
| `docs/touch-dev.md` | Touch audit, implementation record and real-device acceptance checklist: tablet editor, phone guard, tap-safe hover and compact phone transcript. |
| `docs/clip-library.md` | Saving clips. **✅ Built 9 Aug 2026** — design, then an **As built** section recording the four places the code diverged and why. Its **What lives where** section is the canonical local-vs-server boundary and the source for the client guide's plain-language version. |
| `static/clips.js` | The saved-clip store: `list / add / update / remove / restore` plus label derivation and date grouping. **The only file that knows clips live in `localStorage`** — that seam is what makes a server move one file rather than a hunt. Keys on the audio URL, never the episode row id. |
| `tools/cropshot.py` | Crops a full-page screenshot down to the dialogue in it, for `docs/client-guide.md`. Pure stdlib — PNG is zlib plus a header, so no Pillow. Finds the modal by its 4px spot-red top border, then its bottom by where the left edge stops being an edge. `python3 tools/cropshot.py in.png out.png --pad 10`, or `--check` to print the box and write nothing. **Screenshots are retina, so set an explicit `width` in the guide at about half the pixel width** — markdown alone stretches them to the column. |
| `backup.py` | Consistent snapshot of the archive, stdlib only. Verifies what it wrote and exits non-zero if it cannot. See **Backups** below — this matters more every week now. |
| `ingest/enrich.py` | Deterministic enrichment, **no AI**. Re-airs + linked entities. Safe to re-run. |
| `ingest/extract.py` | The one AI step: topics, guests, interviewers. Written, tested, **never run**. Not in `refresh.py` — needs a key and costs money. `--dry-run` and `--rebuild` need neither. |
| `ingest/schema.sql` | Tables, FTS5 index, triggers. Already has `transcript_source` and a source-agnostic `segments` table. |
| `serve.py` | JSON API + serves the UI and its JS. Stdlib `http.server`; swap for FastAPI at deploy. |
| `static/index.html` | The whole UI — markup, styles and app code. No build step. |
| `static/mp3cut.js` | Lossless MP3 clip extraction. `probeMp3()` measures each file; `cutClip()` copies frames. |
| `static/zip.js` | ZIP writer, CSV writer and filename slug for the archive package. No dependency — `CompressionStream` does the deflating. Deterministic output so two exports can be diffed. |
| `static/waveform.js` | Peaks at 8 kHz, IndexedDB cache, canvas rendering, snap-to-silence. |
| `static/index.html` | The whole interface — single file, no build step. |
| `README.md` | Run instructions, API reference, useful SQL. |
| `docs/lhf-podcast-spec.html` | **Client-facing** planning memo (shared with them). Tier ladder, no cost-of-work talk. |
| `docs/build-plan.html` | **Internal** build plan. Google setup walkthrough, VPS sizing, phases, risks. |
| `docs/reply-descript.md` | The short email reply about Descript transcripts (sent). |
| `docs/ask-vocabulary.md` | **Draft, not sent.** Asks LHF whether the podcast archive should share the Labor Arts & Culture Database's 34-term topic vocabulary. Reasoning lives in `docs/ai-layer.md`. |
| `docs/transcripts-plan.md` | **Phased plan for transcripts.** Read before touching this area. |

Both `docs/*.html` are also published as artifacts — same URLs update in place
if edited and republished.

---

## What we learned today (the useful part)

**1. The RSS feed caps at 100 episodes per channel.** Feed pagination parameters
are ignored. A later full audit on 26 August found that the public website's
server-rendered `/page/N/` routes do expose the whole published catalogue and
all fields needed for a one-time backfill: **785 episodes** across three
programs. The authenticated Podbean API or a dashboard export is now a fallback,
not a prerequisite. See `docs/feed-backfill-investigation.md`.

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

**7. 147 of 200 live episodes publish full transcripts in the RSS feed**
(Podcast 2.0 `<podcast:transcript>` tags → `.srt` files, timestamped to the
millisecond, free). Only 53 episodes need machine transcription — about $9,
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
4. **What happens to episodes that fall off the feed — on their side?** Raised
   9 August 2026, when both shows were measured at exactly the 100-episode cap
   (see Backups). We know what *our* archive does: it keeps them, permanently,
   and retains it independently of RSS. The 26 August audit found that Podbean's
   public archive pages still list the full backlog, but what they retain behind
   those pages still changes what this product is:

   - **Do they hold their own masters** for everything back to the start of
     each show, or is Podbean their archive too? If the latter, this database
     is closer to a system of record than anyone has treated it as.
   - **Has anything already been lost** — episodes deleted from Podbean, or
     predating it entirely?
   - **They do want the pre-feed backlog ingested.** Confirmed by the client on
     26 August 2026; it is now the first DO in the task box.
   - **Do they expect the app to hold shows the feed no longer carries** as a
     feature — i.e. "this is where the whole archive lives" — or as a side
     effect nobody has thought about?

   The last one is the fork. If the app is meant to be the archive of record,
   then backup, an admin surface and eventually authentication stop being
   nice-to-haves, and that is the same shell `docs/ai-layer.md` is blocked on.
   **Their answer is expected soon; capture it here when it arrives.**

5. **Should topics use the vocabulary LHF already owns?** Raised 9 August 2026.
   The Labor Arts & Culture Database
   (<https://labor-database.supersoul.top>) carries **34 canonical tags in three
   facets**, already classifying ~5,954 entries, plus 145 regex auto-tagging
   rules. Adopting it here would let one search eventually cover episodes,
   films, quotes, songs and landmarks — and it turns "topics" from a seven-hour
   tagging job into a one-meeting approval, which is the form their former
   Library of Congress historians can actually help with.

   **Nothing built, nothing decided.** The full consideration — including the
   measurable first step that needs no AI and no money, and the care needed
   around the "informed by LCSH" claim — is `docs/ai-layer.md` → *A shared
   vocabulary*. The plain-language version for the client is in
   `docs/client-guide.md`.

Nothing is blocked on these. They're slow-moving; the interface work continues
regardless — **except that backups should not wait for thread 5.** The archive
is already accumulating episodes the feed no longer serves, whatever the client
decides they want.

---

## Where we stopped

Production is deployed. The current touch work—tablet editor support, tap-safe
hover disclosure and the compact phone transcript—is complete locally, with
core iPad use confirmed and the remaining Phase 4 device matrix recorded in
`docs/touch-dev.md`. The task box at the top of this file is the authoritative
next-work list; older design and correspondence sections below are historical
context, not a second backlog.

---

## Data ownership, scheduling, export

Three related concerns. Status differs for each.

### 1. Storing the scraped text — ✅ already done

Everything is stored locally, nothing is re-fetched at query time:

| | |
|---|---|
| `episodes.transcript_text` | 147 episodes, 4 MB |
| `segments` (timestamped passages) | 15,294 rows, ~4 MB |
| `description_html` + `description_text` | all 203 episodes |
| Audio | **not stored** — only the URL |

Database is 56 MB. Podbean's transcript URLs and audio URLs are recorded but
never depended on after ingest, so CDN link rot can't take the archive down. If
both feeds vanished tomorrow, everything searchable still works.

Audio deliberately isn't stored — ~12–24 GB, and streaming from their CDN is
free and fast. Worth revisiting only if clip export gets built.

#### What lives in the browser instead — verified 9 August 2026

Worth knowing exactly, because the clip library adds to this list and
`docs/client-guide.md` now makes a promise to the client about it. **The app
persists three things client-side today:**

| What | Where | Lost if cleared? |
|---|---|---|
| Light / dark choice | `localStorage["lhf-theme"]` | One click to redo |
| Waveform peaks | IndexedDB `lhf-peaks`, keyed on audio URL, `v: 2` | One 30–105 MB re-download |
| **Saved clips + labels** | `localStorage["lhf-clips"]`, `v: 1` — `static/clips.js` | **Gone. Not derived from anything.** |

The first two are derived and rebuild themselves. The update-prompt dismissal is
*not* persisted at all — `hushedVersion` is an ordinary variable, forgotten on
reload, so "remembered per build" means for the life of the tab.

**Saved clips are the first client-side data in this application that is not
rebuildable.** Hence: every surface that writes them says so once, the empty
state says it before there is anything to lose, and Download stays the primary
action in the editor because a downloaded MP3 is the copy that outlives the
browser. `docs/clip-library.md` → *What lives where* carries the full boundary,
including which features would need a server and why they are all one decision.

### 2. Timed updates — ✅ built and running in production

`refresh.py --loop 15m` runs the pipeline on a schedule and keeps itself alive.
It works the same on a laptop, in Docker, and on Coolify without depending on a
host scheduler, and backs off on repeated failure instead of hammering the feed.

**It was 24h until 13 August 2026**, which meant a new episode could sit unseen
for most of a day — not good enough for a live podcast. Two things made a short
interval affordable, and both matter more than the number itself:

- **Conditional GET.** Podbean serves an `ETag` on both feeds and honours
  `If-None-Match` with a 304 and an empty body. `shows.feed_etag` stores it, so
  an unchanged feed costs no bytes rather than ~1 MB. Without this, a 15-minute
  poll would pull roughly 3 GB a month to learn nothing had happened.
- **Enrichment only when something arrived.** `enrich.py` does
  `DELETE FROM reairs` + `DELETE FROM mentions` and rebuilds across every
  episode; it cannot run every 15 minutes. It is gated on the feeds actually
  bringing something. Transcripts still run every tick — one indexed lookup when
  nothing is outstanding — because Podbean sometimes attaches a transcript days
  after publishing, and gating that would mean never collecting those.

A step that fails is **owed** and retried on the next tick. Without that, the
retry looks like an ordinary quiet tick, the step is skipped as "nothing new",
the run reports success, and the failure is swallowed for as long as the feeds
stay unchanged.

Measured: a tick with nothing new takes **1 second and downloads 0 bytes**.

**This is now wired up and running.** `docker-entrypoint.sh` starts the loop in
the background unless `LHF_AUTO_REFRESH=0`, which is what keeps a single-container
Coolify deploy current — Coolify deploys the Dockerfile, not the compose file, so
without that the archive would be frozen at whatever the feeds held on deploy
day. The compose `web` service sets `LHF_AUTO_REFRESH=0` because the dedicated
`refresh` worker owns updates there; two loops on one SQLite file would race.

For a host scheduler instead of either, the cron form is:

```cron
# Sundays 04:00 — after both shows are out
0 4 * * 0  cd /path/to/digital-asset-manager && /usr/bin/python3 refresh.py >> /var/log/lhf-refresh.log 2>&1
```

**Failure notification is still missing, but the symptom is now visible.** The
loop logs failures to stderr and backs off, and nobody is watching stderr. An
email or webhook on repeated failure remains the piece that isn't there.

What changed on 13 August 2026 is that a stopped updater no longer hides. The
footer shows **"Feeds checked N minutes ago"** from `shows.feed_checked_at`,
stamped on every poll that reached Podbean *including one answered 304*, and
flagged stale past two hours. This exists because the prediction in the
paragraph above came true almost exactly: production drifted, nobody noticed,
and the only way to check was to open Podbean and compare episode by episode.

Deliberately **not** `episodes.last_seen_in_feed` — that only moves when a feed
actually changed, and on a weekly show it is days old almost always, so a footer
built on it would report a perfectly healthy updater as dead.

An earlier version of this section said the database was the only reachable
copy of anything that rotated out of RSS. The 26 August audit corrected that:
the public Podbean archive pages still expose the published backlog. Backups
remain necessary because that page format is undocumented and cannot reproduce
our corrections, retained feed state, or derived catalogue data.

### 3. Export — ✅ mostly built

Built from scratch on the stdlib, as planned — no package, no venv. See
`docs/export-spec.md` and the **Export** entry under "Working now".

| Format | For | State |
|---|---|---|
| CSV | Everyone. Opens in Excel, which is how most of this org works. | ✅ built, with a BOM so Excel doesn't mangle accents |
| TSV | Paste straight into a sheet | ✅ built (`?format=tsv`) |
| JSON | Machine use, already the API shape | ✅ built |
| Clipboard | Paste into an already-open sheet | ✅ built |
| SRT / VTT / plain text | A single episode's transcript in a standard format | ✅ built, at `/episode/<id>/transcript?format=` |
| Dublin Core XML | The library-standard metadata answer. ~20 lines. | ❌ not built |
| BibTeX / citation | Researchers quoting an episode + timestamp | ❌ not built, and **blocked on a question, not on effort** — Chicago, MLA, APA and the broadcast-archive conventions disagree about how to cite a radio segment, and choosing blind means building the wrong thing confidently. Ask them. See `docs/ai-layer.md` §6. |

It was scoped as "export whatever the current search returns" rather than a
separate reporting screen, and that held up: one endpoint, one control, and it
covers what anyone actually asks for. The endpoint calls `search()` rather than
reimplementing the query, so the file and the screen cannot drift apart.

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

**`docs/transcript-modal.md`** picks this thread up: a transcript view with the
tools around it — select text to get a broadcast-ready clip, live duration
readouts, out-cues, citations. Several of the seeds above (run sheet, citation
copy) are really features *of* that view.

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

**If you want to unblock the real feature set:** Tier 2 extraction — now
written as `ingest/extract.py`, tested end to end, and never run. It sends a
batched pass over `description_text` + transcript → guests, topics,
interviewers into the `people` / `topics` tables (in the schema, still empty).
$4.35 for the whole archive via the Batch API, ~2¢ per new episode; verify with
`--dry-run`, which needs no key. The deterministic entities from
`enrich.py` are ground truth — let them win on conflict, and use them to check
the model's output.

**If the client comes back with transcripts:** write a `ingest/descript.py`
that parses SRT/DOCX into the `segments` table with `transcript_source =
'descript'`. Nothing else changes — extraction, search, and UI all read from
the same place.

### Tests

```bash
node tests/test-waveform.mjs        # pure: peak reduction + snap-to-silence
node tests/test-update-prompt.mjs   # pure: the new-version reload prompt
node tests/test-zip.mjs             # pure: the archive packager
node tests/test-clips.mjs           # pure: saved clips, labels + query semantics
node tests/test-clips-ui.mjs        # structural: clip search/sort/mobile wiring
node tests/test-palette.mjs         # pure: both themes' colour laws
node tests/test-hidden.mjs          # pure: hidden elements actually hide
node tests/test-keyboard.mjs        # pure: keyboard/focus interaction laws
node tests/test-overflow.mjs        # pure: archive text cannot widen a phone
node tests/test-touch.mjs           # pure: phone transcript/guard + tablet pointer + hover safety
node tests/test-pagination.mjs      # structural: paged search + request cancellation
python3 tests/test-ingest.py        # pure: feed stamping + rotated-out detection
python3 tests/test-backfill.py      # pure: page parsing + identity + reruns
python3 tests/test-server.py        # pure: search pages + complete export path
node tests/verify-clips.mjs         # live: needs the server running + network
```

`verify-clips.mjs` picks episodes at random each run, so it covers the bitrate
spread over time rather than pinning one fixture. It checks duration, filename,
and — the one that matters — that the clip's bytes appear **verbatim** in the
source at the expected offset. That single check proves the cut is both
correctly positioned and genuinely lossless.

### Keeping the archive current

`serve` starts its own 15-minute refresh loop. `LHF_AUTO_REFRESH` defaults to
`1` (`${LHF_AUTO_REFRESH:-1}`), so **no environment variable needs to be set for
updates to run** — and none is set in Coolify. Only an explicit `0` disables it,
which is what `docker-compose.yml` does because compose runs a *separate*
refresh worker and two loops on one SQLite file would race.

This matters because **Coolify deploys the Dockerfile, not the compose file**,
so it runs one container. The refresh worker in `docker-compose.yml` never
started, and the deployed archive was frozen at whatever the feeds held on
deploy day — the one thing an archive of a weekly show must not be. The
compose web service sets `LHF_AUTO_REFRESH=0` because the dedicated worker
owns updates there; two loops on one SQLite file would race.

The loop waits for the first build to finish before its first tick.

### Backups — this gets more important with time, not less

**The database is not disposable.** An earlier version of this section said
three episodes had become recoverable only from a laptop backup. A complete
audit on 26 August corrected that: Podbean's public paginated archive still
exposes those episodes and the entire published backlog. The backup remains
valuable, but is not their only reachable source.

Podbean serves only the most recent 100 episodes per channel, so every week the
oldest episode in each RSS feed falls out of that source. Anything already
ingested stays in the database, because `episodes` rows are never deleted —
there is no `DELETE FROM episodes` anywhere in `ingest/`. An RSS-only rebuild
comes back **without it**; the separate public-page recovery route is documented
in `docs/feed-backfill-investigation.md`.

**Measured 13 August 2026 — the first measurement ever taken against
production.** The 9 August figures previously printed here were the *local dev*
database's, from a 4 August ingest, and read as though they were production's.

Three episodes have now rotated off Podbean:

| Show | Date | Title |
|---|---|---|
| Labor Heritage Power Hour | 2024-09-12 | The power of our stories |
| Labor Heritage Power Hour | 2024-09-19 | Shift Happens |
| Labor History Today | 2024-09-22 | The Disney Revolt (Encore) |

**None of the three is on production**, because `/data` was not a persistent
volume: it lived in the container's writable layer and was destroyed on every
redeploy, so each deploy silently reset the archive to whatever the feeds held
that day. Confirmed by Paul on 13 August 2026 — there was no volume configured
in Coolify at all. One is mounted now, and from here the archive accumulates.

They are retained in `~/Desktop/lhf-BACKUP-2026-08-13.sqlite` on Paul's machine
and were also confirmed on Podbean's public archive pages on 26 August. The full
backfill will restore them to production along with the older catalogue.

**The standing check** — worth running after any deploy — is whether the live
site reports **more than 100** episodes for either show. Both shows are weekly,
so the count should now grow by one per show per week and never reset. A count
of exactly 100 after a deploy means the volume is not holding.

Nothing prior to September 2024 is reachable through RSS, but a 26 August 2026
audit confirmed the full published catalogue on Podbean's public paginated
archive pages. That makes the pre-feed backlog a one-time public-page recovery;
the authenticated API or back-end export is the supported fallback. See
`docs/feed-backfill-investigation.md`.

So: back up the Coolify volume, and start before it matters rather than after.

`backup.py` does this and nothing else.

**On the server, pull it down — do not store it there.** The VPS should not
accumulate 53 MB copies of a file it already has, and a snapshot beside the
database protects against nothing likely to happen to it:

```bash
# run from your own machine
ssh HOST 'docker exec CONTAINER python3 /app/backup.py --stdout' \
    > ~/lhf-$(date +%F).sqlite
python3 backup.py --verify-only ~/lhf-2026-08-09.sqlite
```

`--stdout` builds the snapshot in a temporary file, verifies it, streams it and
deletes it. Peak disk on the server is one copy of the database for the length
of the transfer; nothing persists. Every message goes to stderr, so logging can
never contaminate the database bytes on stdout, and **verification happens
before the first byte is sent** — a failed backup produces no output at all
rather than a truncated file that looks plausible.

Locally, or anywhere you do want files kept:

```bash
python3 backup.py                       # snapshot to data/backups/, keep 7
python3 backup.py --dest /mnt/nas/lhf   # somewhere else, rotated
python3 backup.py --verify-only FILE    # check an old snapshot
```

Three things it does that a file copy does not:

- **It takes a consistent snapshot of a live database.** `cp`, `rsync` and
  volume snapshots can catch a torn page or miss commits still in the `-wal`
  file, and the result usually *opens fine* while being quietly incomplete —
  the worst way for a backup to fail. This uses SQLite's online backup API.
- **It converts the snapshot out of WAL mode**, so a backup is one
  self-contained file rather than three, and can be opened read-only anywhere.
- **It verifies what it wrote** — integrity check plus a row count — and renames
  the file `.FAILED` and exits non-zero if it cannot. A scheduler will notice.

**A snapshot inside the same volume is not a backup.** It defends against
corruption and a bad migration, and against nothing at all if the volume is
lost, which is the failure that matters here. The script says so in its own
output when it detects that it has written one.

The other half of the same problem is the one-time public-page backfill, which
can recover the pre-September-2024 published backlog without credentials. See
`docs/feed-backfill-investigation.md`.

### Deploys and stale browsers

`serve.py` sends `Cache-Control: no-cache` on everything, which is widely
misread. It does not mean "do not cache". It means **"never reuse a stored copy
without asking the server first"** — so a reload can never produce a stale page.
There is no build step and no fingerprinted filenames, so a file's URL never
changes when its contents do, and revalidating every time is the only thing
that works.

**Two things were wrong here, and both are now fixed.**

**1. There were no 304s.** A comment in `_send` claimed they cost nothing, but
the server sent no `ETag` and no `Last-Modified`, so the browser had no
validator to revalidate *with* and had to re-download the whole body every
time. Every response now carries an `ETag`, and a conditional request gets a
304 with an empty body — measured on the page itself, 158,651 bytes became 0.
The hash is taken after compression, so a gzipped body and a plain one are
different ETags, which is what `Vary: Accept-Encoding` already implied.

**2. None of that reaches a tab that is already open**, which is the case that
actually cost time here. A bug fixed and deployed appeared **unfixed locally**
because one tab held a stale `index.html`; twenty minutes went into debugging
code that was already correct, and the giveaway was a status string in a
screenshot that had been deleted from the source two commits earlier. No cache
header can fix that, because a running page never asks the server anything. A
tab left open for a fortnight runs fortnight-old JavaScript, indefinitely.

So the page now asks. `/api/version` returns a content hash of `index.html` and
all four ES modules, and the UI re-checks it **when the tab is returned to** —
`visibilitychange` and `focus`, throttled to one request a minute. On a change
it shows a dismissible bar offering a reload. Three deliberate choices:

- **Nothing reloads on its own.** An editor holding an unsaved selection is the
  wrong thing to discard on the app's initiative.
- **Hashed by content, not mtime**, so a redeploy that changes no files stays
  silent. Nobody trusts a prompt that cries wolf.
- **Checked on return, not on a timer**, so an idle tab generates no traffic —
  and the check fires at exactly the moment a days-old tab comes back into use.

`node tests/test-update-prompt.mjs` covers the quiet cases: dismissal is
remembered per build, a further deploy may ask again, a failed request neither
throws nor prompts. **"Remembered" means for the life of the tab** — it is an
in-memory variable, not storage, so a reload asks again. That is the right
trade for a prompt that only fires on a real change, but don't read it as
persistence.

If a fix still seems not to have landed, check for a stale page before checking
the code — and `git log -S'some string from the screen'` will date it exactly.

### Small things that were wrong and are now fixed

- Waveform peaks were cached in IndexedDB under `ep-<id>`. Episode ids are
  `INTEGER PRIMARY KEY`, assigned in ingest order, so rebuilding from an empty
  volume can give a number to a different episode — a returning visitor would
  then get another show's waveform and cut a clip from the wrong audio while it
  all looked correct. Keyed on the audio URL now, which identifies the
  recording rather than its row.
- Dragging the overview needed the waveform to have loaded, so every drag
  during the first minute did nothing. Only duration is required to move a
  selection, and that arrives with the search result.

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
- Ingest's feed-stamping and rotated-out rules have a pure suite in
  `tests/test-ingest.py`; a complete rebuild and count check remains the
  integration test. The clip editor's pure/static tests are also in `tests/`.
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
