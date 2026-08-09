# Export — development plan

**Status:** planned, not built. Written 9 August 2026. **Companion to**
`docs/export-spec.md`, which records the export **as built** — CSV/TSV/JSON of
the current result set, plus the transcript route. That document is still
correct; this one covers what the export is *for* beyond a spreadsheet.

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

### The number that decides the design

Measured against the live archive, 9 August 2026:

| Part | Size | Notes |
|---|---|---|
| Transcript text | **4.7 MB** | 882,346 words, 14,937 passages |
| Descriptions (HTML) | **0.2 MB** | |
| Cover images | **~38 MB** | 144 distinct, ~267 KB each — verified by request |
| **Audio** | **~8–12 GB** | 143.1 hours; a 28-minute episode measured at 27.0 MB, and the archive carries both 128 and 192 kbps |

**The catalogue is five megabytes. The media is ten thousand.** A factor of two
thousand between them is not a difference of degree, and one mechanism cannot
serve both well. So there are **two exports**, and confusing them is the main
way this feature could go wrong.

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
spoken line — episode, show, date, start, end, text — is 14,937 rows, which is
nothing for a spreadsheet, and it makes "find every mention of the Pittston
strike, with timecodes" a filter rather than a project. It is also the single
most useful thing to hand a language model, because it is already chunked with
citations attached. `export-spec.md` lists this as outstanding; it should be
near the front.

**Transcripts ship as files, not cells.** Google Sheets truncates a cell at
50,000 characters and episodes average ~49,000. Putting them in a column would
silently lose text, which is the worst failure mode a backup can have.

---

## Export B — the media archive

Audio and artwork: 8–12 GB. This one is **not a download button**, and the
reasons are worth stating plainly because the obvious approach fails badly.

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

1. **The catalogue package.** The ZIP, `episodes.csv`, `passages.csv`,
   transcripts in three formats, README and data dictionary. This is 80% of the
   value and it is all client-side. Ship it alone.
2. **The picker and size estimate.** Choose the parts; see the weight first.
   Absorbs the column picker already outstanding.
3. **The media download kit.** Manifest plus `fetch.py`. Resumable,
   verifiable, incremental.
4. **The archival layer.** BagIt, Dublin Core, citations — the last gated on
   the format question.

---

## Open questions

1. **Which citation style?** Blocks one item, costs one email.
2. **Do they want the audio at all**, or are metadata and transcripts the
   backup they have in mind? 12 GB is a real commitment of disk and hours.
3. **Where would it live** — a NAS, an external drive, institutional storage?
   The answer changes whether BagIt matters and whether incremental updates do.
4. **One package for both shows, or one each?** They are separate programmes
   with separate histories, and an archivist would probably expect separately.
