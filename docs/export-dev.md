# Export — development plan

**Status:** **phase 0 and the catalogue package are built** (9 August 2026);
the media half is not. **Companion to** `docs/export-spec.md`, which records the
row-level export as built. This document covers what the export is *for* beyond
a spreadsheet.

| Phase | | |
|---|---|---|
| 0 | Record what the feed still carries | ✅ built |
| 1 | The catalogue package (.zip) | ✅ built |
| 2 | Picker and size estimate | partly — transcripts and timestamps are optional, sizes are static |
| 3 | At-risk episodes: the filter and rescue | not started |
| 4 | The full media download kit | not started |
| 5 | BagIt, Dublin Core, citations | not started |

---

## At a glance

**The idea, in the client's own framing:** the export should be *everything* —
a package that is simultaneously a spreadsheet, a documented dataset, and a
complete backup of what Podbean holds for them. Feed data, descriptions,
transcripts, audio and artwork in one place. All the work happens on their
machine, so the app stays light. And enough choice in it to serve three
different jobs: labor historian, podcast producer, host.

**What already exists:** CSV / TSV / JSON of the visible result set, transcripts
as txt / srt / vtt per episode, clipboard copy.

**What this adds:** everything else — and one architectural decision that the
numbers make for us.

**It is also the migration path.** With every table and the transcripts in it,
the package is a complete reconstruction of the database minus the audio —
readable by another developer, or a language model, without this codebase
existing. See [The package as a migration
path](#the-package-as-a-migration-path). That is a different and longer-lived
thing than `backup.py`, which restores this application and only this one.

### The number that decides the design

Refreshed against the local retained archive, 14 August 2026. Production still
contains 200 episodes / 143.1 hours until the three restored rows are deployed:

| Part | Size | Notes |
|---|---|---|
| Transcript text | **4.8 MB** | 904,266 words, 15,294 passages |
| Descriptions (HTML) | **0.2 MB** | |
| Cover images | **~39 MB** | 146 distinct; the earlier measured average was ~267 KB each |
| **Audio** | **~8–12 GB** | 145.4 retained hours; a 28-minute episode measured at 27.0 MB, and the archive carries both 128 and 192 kbps |

**The catalogue is five megabytes. The media is ten thousand.** A factor of two
thousand between them is not a difference of degree, and one mechanism cannot
serve both well. So there are **two exports**, and confusing them is the main
way this feature could go wrong.

**And the audio question is smaller than it looks.** Podbean is still hosting
all of it, so the default everywhere is a *link*. What deserves copying is the
tail that is about to leave the feed — roughly two episodes a week rather than
two hundred at once. See [What audio is actually
for](#what-audio-is-actually-for--the-expiring-archive), which is the section to
read if you only read one.

---

## Export A — the catalogue package

Small, fast, complete, and the one most people will ever need. A single `.zip`
built **in the browser**, from data the page already has or can fetch cheaply.
Nothing is generated on the server.

```
lhf-archive-2026-08-09/
  README.md                     ← what this is, how it was made, what's in it
  DATA-DICTIONARY.md            ← every column and field, defined
  datapackage.json              ← machine-readable manifest (Frictionless spec)
  episodes.csv                  ← one row per episode, the spreadsheet
  episodes.json                 ← the same, structured, for machines
  passages.csv                  ← one row per transcript line, with timecodes
  people.csv  topics.csv  reairs.csv
  transcripts/
    txt/  0142-made-by-labour.txt
    srt/  0142-made-by-labour.srt      ← the original timed file
    vtt/  0142-made-by-labour.vtt
  episodes/
    0142-made-by-labour/
      metadata.json
      dublin-core.xml           ← the library-standard answer
      description.html
      notes.md
  MANIFEST-sha256.txt
```

**`passages.csv` is the piece a researcher will actually live in.** One row per
spoken line — episode, show, date, start, end, text — is 15,294 rows, which is
nothing for a spreadsheet, and it makes "find every mention of the Pittston
strike, with timecodes" a filter rather than a project. It is also the single
most useful thing to hand a language model, because it is already chunked with
citations attached. `export-spec.md` lists this as outstanding; it should be
near the front.

**Transcripts ship as files, not cells.** Google Sheets truncates a cell at
50,000 characters and episodes average ~49,000. Putting them in a column would
silently lose text, which is the worst failure mode a backup can have.

### How big is the transcript folder, exactly

Counts and plain-text sizes refreshed 14 August 2026; the generated-format and
zip sizes remain estimates based on the 9 August package measurement:

| | |
|---|---|
| Episodes carrying text | **147** |
| Plain text, all of them | **4.8 MB** |
| Average per episode | **34 KB** |
| Largest single episode | **58 KB** |
| Same content as SRT | **~5.3 MB** (15,294 passages, timestamps included) |
| All three formats (txt + srt + vtt) | **~15–16 MB** |
| **Zipped** | **~1.9 MB** for the text |

**The whole catalogue package, transcripts and all, is under 10 MB zipped.**
More than nine hundred thousand words of spoken labor history fits
comfortably inside a single email attachment. There is no size argument against
including all of it, in every format, every time.

---

## The package as a migration path

This is the strongest reason to build it, and it is worth stating plainly
because it changes what the export *is*.

**There are two kinds of backup here, and they are not substitutes.**

| | `backup.py` | The export package |
|---|---|---|
| Format | SQLite | CSV, JSON, plain text, SRT |
| Restores | This application, exactly | Any application, any language |
| Needs | This codebase and SQLite | Nothing but a text editor |
| Good for | An accident on Tuesday | A different developer in 2031 |

`backup.py` is an **operational** backup: fast, exact, and worthless if the
thing you have lost is the application rather than the data. The export package
is a **preservation** copy — plain text with a data dictionary, readable by
anyone who has never seen this repository, and the format an archivist would
expect precisely because it outlives the software that produced it.

**And if it carries every table, it is a complete logical reconstruction of the
database minus the audio.** Another developer, or a language model, could
rebuild this entire application from the package alone. That is the client's
own instinct — *"a path to a possible full backup, for another dev or a new
app"* — and it is correct.

### What completeness actually requires

The package is only a migration path if it carries everything, which means more
than `episodes.csv`:

- **`segments`** with their millisecond timings — the transcripts *and* the
  index that makes them searchable
- **The original `.srt`**, not only our derived text. It is the artefact the
  producers' own workflow generated, and re-deriving from it is always possible;
  re-deriving *it* is not.
- **`description_html`** as published, not just the stripped text. The
  hyperlinks in it are where all 232 tags came from.
- **`mentions`, `reairs`, `topics`, `people`, `shows`** — every table, not only
  the ones a spreadsheet user would ask for
- **Keyed on `guid`** throughout, so the reconstruction does not depend on row
  ids this project has already been burned by

### The trap this creates

**A partial export that calls itself a backup is dangerous**, and the scope
control makes that easy to do by accident: export while filtered to 2025 and
you get a perfectly valid 107-episode package that looks exactly like a
complete one.

So the package export **states its scope in the README and in the filename**,
and a filtered package is named as such — `lhf-archive-2026-08-09-filtered.zip`
against `lhf-archive-2026-08-09-complete.zip`. The row-level exports may be
filtered freely; a thing claiming to be an archive has to say what it left out.

---

## The dialogue itself — scope, and showing rather than describing

Two changes to the export dialogue, both prompted by using it.

### 1. Scope: this search, or everything

**"Export exactly what's on screen" was the right principle and is now a
limitation.** It is still the correct *default* — if Chris has filtered to
"Power Hour, 2025, encores only", that is almost certainly what he wants. But
somebody who has just searched for something and now wants the whole archive has
to clear every filter first, and — worse — may not notice the export was scoped
at all. A file that silently contains 78 of 200 episodes is the kind of mistake
discovered much later.

So the count panel stops being a readout and becomes the choice:

```
  ( ) This search          78 episodes · Power Hour · 2025 · encores only
  (•) Everything          200 episodes · the whole archive
```

Both counts visible at once, always. The point is not merely to offer the
option; it is that **you cannot press Export without having seen which one you
are getting.** `describeScope()` already produces that summary line and
`CORPUS.episodes` already holds the archive total, so this is presentation.

Sort order carries over to both — an unfiltered export still has a useful order.

**A choice between two identical files is not a choice.** With nothing filtered,
"This search" and "Everything" are the same 200 rows, presented as two options
with the same number beside them — which makes the reader hunt for a difference
that is not there. Since August 2026 the radio group appears only when something
is actually filtering. Otherwise it is not shown at all, and the subhead carries
the whole answer: *All 200 episodes — the whole archive.*

Not a disabled control, and not one option shown pre-selected: both read as a
chooser that won't respond. The count still appears, because the size of the
file is never implied — it just moves to the only line left.

The scope is read from `currentQuery()` rather than from a second list of the
filter fields — anything but `sort` in that query means the view is narrower
than the archive. A separate list would have gone stale the first time a filter
was added, and the failure would have been a *filtered* export claiming to be
complete.

That last part fixed a real defect rather than only removing a redundant
control. `complete` was `exportScope === "all"`, and the scope reset to `"view"`
on every open — so an unfiltered archive package downloaded as
`lhf-archive-…-filtered.zip` with a README announcing it held "only part of the
archive: the whole archive". It is now `exportIsComplete()`, which is true when
the scope is "all" *or* nothing is filtering. The clip library's zip never had
this bug: it derives `filtered` by comparing row counts, which is the same
answer computed the safe way.

**And hiding the group did not hide it.** `.scope-list` sets `display: grid`,
which beats the browser's own `[hidden] { display: none }`, so the first attempt
shipped a dialogue that had correctly decided not to offer a choice and then
drew it anyway. The stylesheet now carries one global
`[hidden] { display: none !important; }` rather than the per-component companion
rule this codebase had been adding by hand sixteen times; `tests/test-hidden.mjs`
stops that rule being deleted as redundant. The same defect was live in the clip
library — `.lib-tools` is `display: flex`, and its "fewer than six clips is
furniture" rule had never once taken effect.

### 2. Explain by showing

The dialogue currently *describes* what you will get in a paragraph. The
stronger version shows it, and the data is already on the page:

- **A preview of the first rows**, in the chosen format. Two rows of real data
  answer "what does it pull" more completely and more permanently than a
  sentence, and they make the format choice concrete — the difference between
  CSV and JSON stops being abstract when you can see both.
- **The actual column list**, which doubles as the groundwork for the column
  picker already outstanding in `export-spec.md`.
- **Where the data comes from**, in one line: it is read from this archive —
  built from your feed and updated daily — not fetched from Podbean at the
  moment you press the button. That matters because it explains why the export
  is instant, why it works offline from Podbean's point of view, and why the
  audio columns are *links* rather than files.

**Not a second dialogue.** There are already four, and the clip editor work
established that stacking them is a maze. This is progressive disclosure inside
the export modal: a collapsed **"What's in the file"** section that expands.
The common case — open, pick CSV, press Export — stays two clicks and gets no
longer.

### The model belongs in the package, not the dialogue

"Could it be a model?" splits in two, and both halves are right in different
places. A **data model** — entities, fields, types, how they relate — is
genuinely needed, but a producer choosing between CSV and JSON is not the
audience for it. It belongs in the exported package as `DATA-DICTIONARY.md` and
`datapackage.json`, where it serves the "hand it to any AI" goal directly. The
dialogue gets a preview; the package gets the schema.

---

## What audio is actually for — the expiring archive

**A link is not a copy, and only some links are worth turning into copies.**

The default is a **URL**, in every format the catalogue package emits. Podbean
is still serving those files, they cost nothing to reference, and downloading
12 GB of audio that somebody else is already hosting is work for its own sake.

What changes that is **expiry**. Podbean serves the most recent 100 episodes per
show, and both shows are at exactly that number, so from the next publication
onward an episode rotates out every week per show. **An episode that has left
the feed is the one whose audio is worth holding**, because it is the only one
nobody else is reliably keeping.

That reframes the whole media question. It is not "back up 12 GB". It is:

> **Keep the audio that is about to become unreachable, and link to the rest.**

Roughly two episodes a week, about 41 MB each — **~80 MB a week, ~4 GB a year**,
and nothing at all for the 200 episodes still in the feed. A completely
different proposition from a one-off 12 GB pull, and one that arrives gradually
rather than as a project.

### Detecting expiry costs almost nothing — ✅ built

`ingest.py` stamps **`last_seen_in_feed`** on every episode it finds in the
feed, and the loop runs daily. **An episode whose stamp stops advancing has left
the feed.** No new request, no scraping, no comparison against anything.

It is a dedicated column rather than the existing `updated_at`, which
`transcripts.py` also writes to
([`ingest/transcripts.py:178`](../ingest/transcripts.py#L178)) and which
therefore means "something changed" rather than "the feed still has this".
`--stats` reports what has gone, with the date each was last seen.

One thing still unknown, and it is the important one:

- **Nobody knows yet whether Podbean deletes the file when an episode leaves the
  feed, or merely stops listing it.** The `audio_url` is a direct CDN link and
  may well keep resolving. This is empirically testable the first time an
  episode expires, and the answer decides whether rescuing audio is urgent or
  merely tidy. **Test it then; do not assume either way.**

### What this looks like in the app

An **"at risk"** filter alongside the existing chips — episodes no longer in the
feed — and a rescue action on them. The archive already knows which they are;
this is presentation, not new machinery. It also gives the client something
concrete to look at when deciding whether they care.

---

## Export B — the media archive

The full pull: audio and artwork, 8–12 GB. Wanted less often than the rescue
case above, but the mechanism is the same and it is the right shape for "give me
everything, once".

This one is **not a download button**, and the reasons are worth stating plainly
because the obvious approach fails badly.

A browser cannot responsibly do this:

- **Memory.** Building a 12 GB ZIP in a tab means holding it, or streaming to
  disk through an API only Chrome implements.
- **No resume.** One dropped connection three hours in and the whole thing
  restarts. On a domestic connection this is not an edge case.
- **No verification.** A truncated MP3 usually plays. A backup you cannot check
  is a backup you cannot trust.
- **A closed tab kills it.** Nobody should have to keep a laptop awake and a
  tab open overnight to have a backup.

**So the app generates a download kit instead**: a manifest and a short script
they run on their own machine.

```
lhf-media-2026-08-09/
  manifest.csv            ← url, destination path, expected size, sha256 when known
  fetch.py                ← stdlib only. No pip, no venv, matching the rest of this project.
  README.md               ← "run this, it will take a few hours, you can stop it"
```

`fetch.py` should be **resumable** (skip what is already present and complete),
**verifiable** (size and checksum after each file), **polite** (sequential, with
a small delay — this is a 12 GB pull from someone else's CDN and it should not
look like an attack), and **incremental** (a second run months later fetches
only what is new).

This is the literal form of *"all the processing is on their machine."* The
media never touches our server — the manifest is a few hundred kilobytes of
URLs, and the bytes go straight from Podbean's CDN to their disk, exactly as the
clip editor already works.

**A file that failed must be recorded as failed.** A package quietly missing
three episodes is worse than one that says so, because it will be discovered
years later by someone who needed those three.

---

## Where this runs — the infrastructure boundary

Worth stating explicitly, because it is a client conversation rather than a
technical one, and because everything above was designed to respect it.

**Today this application is deliberately weightless.** Stdlib only, no build
step, no dependencies, two containers and one 53 MB file. That is why it runs
happily alongside other work on a shared Coolify box, and why a redeploy cannot
break in six interesting ways. It is a property worth defending, not an
accident.

**Storing audio and processing media are a different class of thing.** Ten to
twelve gigabytes of MP3, growing weekly, plus transcoding or waveform
generation, is not a feature increment — it is a different server with different
disk, different bandwidth and a different backup obligation. It does not belong
on shared infrastructure hosting somebody else's projects.

So the line is:

| Stays here | Needs their own machine |
|---|---|
| Catalogue, search, transcripts, the editor | Stored audio at archive scale |
| Metadata export, manifests, the download kit | Media processing of any kind |
| Clip cutting (browser → CDN, never our disk) | Anything that grows without bound |

**This is why both exports push the bytes to the client's own hardware.** The
catalogue package is built in their browser; the media kit runs on their
machine. Neither routes media through our server, and that is the design
constraint that makes the rest of it affordable.

If the client wants stored audio, AI processing, or an admin surface that edits
records, **that is the point at which they need their own VPS** — and given they
now have two projects with a third arriving, one machine of their own is
cheaper and cleaner than three tenancies on somebody else's. It also settles
the authentication question in `docs/ai-layer.md` and the shared-library
question in `docs/clip-library.md`, both of which are waiting on the same
decision.

---

## Making it legible to an AI

The client's framing — *"hand this to any AI and say build this from it"* — is a
real design constraint, and a demanding one. What it requires:

- **It explains itself.** `README.md` and `DATA-DICTIONARY.md` are not
  courtesies; they are the difference between a folder of CSVs and a dataset.
  Every column defined, every enum listed, every date format stated.
- **A machine-readable manifest.** `datapackage.json` (the Frictionless Data
  spec) describes the tables, their fields and their types in a format many
  tools already understand. It costs a few dozen lines.
- **Stable identity.** Rows key on **`guid`**, never on the integer `id`.
  Episode ids are assigned in ingest order, and this project has already been
  bitten once by treating them as stable — see `HANDOFF.md` and
  `docs/clip-library.md`. An exported dataset keyed on row ids is one rebuild
  away from being subtly wrong.
- **Deterministic output.** The same archive exported twice produces the same
  files in the same order with the same bytes. That makes two exports
  diffable, which turns a backup into a record of what changed.
- **Chunked with citations attached** — `passages.csv` again. A model handed a
  transcript can quote it; handed timed passages, it can *cite* them.

---

## Making it legible to an archive

Their organisation includes Library of Congress people, and there is a standard
built for exactly this handover.

**BagIt** is the Library of Congress's own packaging format for transferring a
digital collection: a `data/` directory, a `bagit.txt`, and a
`manifest-sha256.txt`. It is about thirty lines to emit, it is what an archivist
expects to receive, and its checksums do double duty — they are also how the
media download verifies itself. If any single item here makes this dataset
credible to an institution rather than merely useful to a producer, it is this
one.

**Dublin Core XML** per episode is the metadata half of the same answer, and is
already listed as outstanding in the handoff.

**Citations remain blocked on a question, not on effort.** Chicago, MLA, APA and
broadcast-archive convention disagree about how to cite a radio segment, and
choosing blind means building the wrong thing confidently. It is one email.

---

## Choice, by who is asking

The same package serves three jobs if the pieces are separable:

| | Wants | Takes |
|---|---|---|
| **Labor historian** | To quote and cite accurately | `passages.csv`, transcripts, Dublin Core, citations, BagIt |
| **Podcast producer** | Material to build a promo or fill a slot | `episodes.csv` with durations, audio, artwork, clip data |
| **Host** | To remember what was said and when | Readable transcripts, show notes, re-airs |

Which argues for a **picker rather than one button**: choose the parts, see the
estimated size before committing. Nobody should discover the size of this
after pressing it. The column picker already outstanding in `export-spec.md` is
the same idea one level down.

---

## Traps

1. **`audio_url` may rot** — the schema says so in its own comment. Every month
   this is not built is a month of links that might not resolve later. This is
   the strongest argument for doing the media export sooner rather than better.
2. **This is the client-facing form of the backup problem.** Both shows sit at
   Podbean's 100-episode feed cap, so the archive is already becoming the only
   reachable copy of what rotates out (`HANDOFF.md`, Backups). `backup.py`
   protects *us*; this export is what puts a copy in *their* hands. Same
   problem, two audiences.
3. **Never proxy media through our server.** 12 GB through a small VPS is the
   one change that would break the "lightweight" property this project has
   deliberately kept.
4. **Filenames.** Titles contain quotes, slashes, colons and accents. Slugged,
   numbered filenames plus a mapping in the manifest — never the raw title on
   disk, or the package will not survive being unzipped on Windows.
5. **Partial success must be visible.** Both exports need a status file listing
   anything that failed.
6. **The 50,000-character cell cap**, above. Text goes in files.
7. **One transcript URL 404s** ("MLK in Memphis" — Podbean's broken link, not
   ours). The export should record it as missing rather than omitting it
   silently.

---

## Phases

0. **Record when an episode was last seen in the feed.** ✅ **built**
   (9 August 2026). `episodes.last_seen_in_feed`, stamped by `ingest.py` on
   every feed appearance and by nothing else, with a `PRAGMA`-guarded migration
   that seeds existing rows from `updated_at` so the first run after it reports
   honestly rather than declaring the whole archive expired.
   `python3 ingest/ingest.py --stats` now names anything the feed no longer
   carries. Done first because it was the only item with a closing window.
1. **The catalogue package.** The ZIP, `episodes.csv`, `passages.csv`,
   transcripts in three formats, README and data dictionary. Audio as URLs.
   This is 80% of the value and it is all client-side. Ship it alone.
2. **The picker and size estimate.** Choose the parts; see the weight first.
   Absorbs the column picker already outstanding.
3. **At-risk episodes.** The filter, and rescue for the handful that have left
   the feed. Small, and it is the audio case that actually matters.
4. **The full media download kit.** Manifest plus `fetch.py`. Resumable,
   verifiable, incremental. Only worth building if they say they want all of it.
5. **The archival layer.** BagIt, Dublin Core, citations — the last gated on
   the format question.

---

## Open questions

1. **Which citation style?** Blocks one item, costs one email.
2. **Does Podbean keep serving an MP3 after the episode leaves the feed?**
   Testable the first time one expires, which is days away. The answer decides
   whether rescuing audio is urgent or merely tidy — and it is the single most
   consequential unknown in this document.
3. **Do they want the *whole* archive's audio**, or only the expiring tail?
   The tail is ~80 MB a week; everything is 12 GB and a decision about
   infrastructure.
4. **Where would stored audio live?** See the infrastructure boundary above.
   If the answer involves a server rather than their own disks, they need their
   own VPS, and that decision reaches well past this document.
5. **One package for both shows, or one each?** They are separate programmes
   with separate histories, and an archivist would probably expect separately.
