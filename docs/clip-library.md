# Clip library — design

**Status:** designed, not built. Written 9 August 2026, rewritten the same day
after the scope discussion that cut it down. **Companion to**
`docs/audio-editor-dev.md`, which lists "clip bin", "run sheet", "named clips as
citations" and "a shared clip library" as brainstorm bullets. This document
covers **only the first**, deliberately.

**Scope in one line:** the editor can cut a clip; nothing remembers it. Fix that
and stop.

---

## At a glance

**What this is:** a list of the clips you have made, saved in your browser, so
that finding a moment in a 143-hour archive is work you only do once.

**What this is not:** a place to assemble a programme. LHF's producers already
have audio editors, and `docs/audio-editor-dev.md` has taken the position that
multi-track assembly belongs to Descript, which is better at it. This tool's job
is **finding and extracting** the moment. The library's job is **not losing it**.

| | |
|---|---|
| **Storage** | `localStorage`, in the browser |
| **Surface** | A modal, like the other four |
| **Server change** | None |
| **Depends on** | Nothing. Not blocked on the identity fix — see below |
| **Rough size** | One or two days |

### In v1

- **`＋ Add to library`** in the clip editor footer, which **does not close the
  modal**
- **A counter in the header** — `Clips 3` — opening the list
- **Rows** carrying the spoken words as the title, show · date, in–out, length
- **Play in place**, without a trip through the editor
- **Re-open in the editor**, **download**, **remove with a ten-second undo**
- **Automatic grouping by date** — Today, Yesterday, Last week
- **A filter box**, because this is a search application and a list without one
  would be odd here

### Not in v1

Folders, collections, run sheets, target durations, the cart wall, ZIP export,
joined export, AI, and any form of sharing. Each is argued in
[Parked for later](#parked-for-later) — they are ideas to consider, not a
roadmap, and none of them should be built before the flat list has been used in
anger.

---

## Three decisions, with the reasoning

### No folders

Folders solve a **scale** problem: too many items to scan. That problem does not
exist yet, and building the structure first means asking a producer to invent a
filing system for eleven clips — a taxonomy they have not yet formed an opinion
about.

There is a second reason specific to this application. **It is a search
application.** Search is the folder. A hierarchy layered on top of a full-text
index over 14,937 passages is a worse version of something already built.

There is also a modelling trap waiting, and it is worth recording now so nobody
walks into it later. The motivating example was *"save Introduction clips and
reuse them when putting a show together"* — a clip used in many shows. In a true
folder tree a clip lives in exactly one place, so reuse means copying, and two
copies drift. **If folders are ever built, they must be labels (many-to-many,
Apple Photos albums) rather than directories**, and the ordered-sequence idea is
a second object that *references* clips rather than containing them.

The right moment to build any of that is when somebody says "I can't find the
clip I saved last month". That day is legible; it has not arrived.

### No sessions, but grouped by date

"Save clips by session" resolves two ways, and one of them is folders in a
smaller coat:

- **A named batch the user creates and manages** — that is a folder. Same cost,
  same guessing, same premature taxonomy.
- **Clips accumulate as you work and are still there tomorrow** — that is just
  persistence, and it is free.

Build the second, and get the first's *feeling* for nothing by grouping the list
automatically under **Today / Yesterday / Last week / earlier dates**. Nothing to
name, nothing to file, nothing to manage, and it reads as "my session" without
being one.

### Local, not shared — and why, given the users

This was the closest call, because the users are **a few people working on the
same podcasts**, which is exactly the situation where a shared library sounds
obviously right. The reason to defer it anyway is that **nothing in the v1
feature set is a multi-user feature.**

Go through them: add a clip, see my clips, play one, re-open one, download one,
delete one. Every operation is *me and my clips*. Seeing a colleague's work is a
**different feature** — a genuinely valuable one — not a storage detail of this
one. Deciding storage on the strength of a feature we have not scoped is how the
first write endpoint in this application's history gets built as a side effect.

The costs are asymmetric, and that settles it:

- **Deferring is cheap**, given the storage seam below: swapping local for a
  server is one small module, not a rewrite spread through the UI.
- **Doing it now is not cheap.** It needs `do_POST` (this server has never had a
  write path), a way to stop strangers writing to a public endpoint, a separate
  database file, and client-side handling for network failure and conflicts. Call
  it two to three times the work, and it introduces a security decision that
  should be made deliberately rather than in passing.

Local-first also buys two things worth having: it works with **no network**,
which in a studio is a feature rather than a limitation, and it lets us find out
**what producers actually do with a library** before committing to a schema.

**When the answer changes:** the moment somebody asks to see another person's
clips. At that point read [Going shared](#going-shared-when-it-is-asked-for),
which records what was verified about the server and volume so that work starts
from facts rather than from scratch.

---

## Four decisions that make later features cheap

The way to be future-aware here is **not** to add empty columns for features
nobody has asked for. That is guessing, and guessed schema is worse than no
schema. What actually makes v2 cheap is a seam and three fields.

1. **One storage module with a narrow interface** — `list / add / update /
   remove`, and nothing else. Every other part of the UI goes through it.
   Swapping `localStorage` for the server, or adding labels, then touches one
   file. This is the single most valuable decision in the list.
2. **A stable unique id on every clip, from day one.** Retrofitting identity onto
   records that lack it is genuinely painful; generating one costs nothing.
3. **A `created_at` timestamp.** Needed for the date grouping regardless, and it
   is what any future sync or merge would be built on.
4. **Key the episode by its audio URL, not its row id.** See the identity trap
   below. This is what makes the library immune to a defect that already exists
   elsewhere in the application.

A record is therefore roughly:

```js
{ id, url, guid, title, show, date, in, out, createdAt }
```

About 150 bytes. A thousand clips is 150 KB against `localStorage`'s ~5 MB, so
there is no storage problem to solve and no reason to reach for IndexedDB, which
is already carrying the peaks cache and is asynchronous.

---

## The identity trap — and why the library sidesteps it

Episode ids are `INTEGER PRIMARY KEY` assigned in ingest order
([`ingest/ingest.py:240`](../ingest/ingest.py#L240)). Rebuilding the volume from
empty can hand the same number to a different episode.

**This project has already been bitten by exactly this.**
[`HANDOFF.md:600`](../HANDOFF.md#L600) records waveform peaks cached under
`ep-<id>`, which meant a returning visitor could get another show's waveform and
*cut a clip from the wrong audio while it all looked correct*. The fix was to key
on the audio URL, which identifies the recording rather than its row.

**The existing share link still has this bug.** `?ep=123&from=522&to=549`
([`static/index.html:3577`](../static/index.html#L3577)) is fine while the volume
survives and wrong the moment it does not — a link emailed in March opens a
different episode at the same timecode, silently.

**The library does not inherit it**, provided decision 4 above is followed. The
clip object already carries `url`
([`static/index.html:2618`](../static/index.html#L2618)), the peaks cache already
proved that is the right key, and a library keyed that way cannot re-point.

**So the share-link fix is not a blocker for this work.** It is a separate,
worthwhile repair — add an integrity token, `?ep=123&g=<first 8 hex of
sha1(guid)>`, resolve `ep`, compare, and fall back to a lookup by hash on
mismatch. It needs one extra branch in `do_GET`, still read-only. Do it on its
own merits, in its own commit, whenever.

---

## The interface

### Where it lives

**A modal, reusing the furniture that exists.** There are already four
(`#clipModal`, `#exportModal`, `#help`, the transcript), and this is a list you
open occasionally, not a place you live.

An earlier draft argued for a `?view=library` route on the grounds that it would
be linkable. That argument does not survive the storage decision: **a local-only
library is not shareable, so linkability buys nothing** — and a route costs more
than a fifth `.backdrop`.

**Stacking rule.** There is a note at
[`static/index.html:2386`](../static/index.html#L2386) about `#clipModal` and
`#exportModal` sharing a z-index and being told apart by DOM order. Fix the rule
rather than inheriting the accident: **the library sits under the clip editor.**
Edit on a row opens the editor on top, and closing it returns you to the list you
were reading rather than to the archive.

### Adding a clip

The footer today is `Cancel | Download MP3`
([`static/index.html:1478`](../static/index.html#L1478)). It becomes:

```
Cancel                    ＋ Add to library      Download MP3
```

Download stays primary — it is still the action that produces the deliverable,
and demoting it would be reorganising the tool around the newest feature. Add
takes the quiet-button weight, with an accent so it does not read as a dismissal.

**Adding must not close the modal**, and this is the decision that determines
whether the feature is worth building at all. The workflow that justifies a
library is pulling three quotes from one episode; if each add closes the
dialogue, the round trips it exists to remove are still there.

So the selection stays exactly where it is after an add. Nudge a handle and add
again and you have two variants of the same quote — which is a real thing
producers do when they cannot decide between two out-points, and today is
impossible without downloading both.

Confirmation goes in `#clipStatus`
([`static/index.html:1475`](../static/index.html#L1475)), the strip already used
for export progress: *"Added — 3 in library"*, with an **Undo** that lives about
ten seconds. No toast, no new furniture.

**Keyboard:** `A` is free and mnemonic. Note that the Space-exemption fix from
the Phases 1–2 audit — controls inside `.modal-actions` keep Space for activation
rather than yielding it to the transport — covers the new button automatically.
Worth verifying rather than assuming, since that fix was itself a shipped bug.

### The row

```
▶   "…and that's why we marched."               12:03 – 12:31   28.4s   ⋯
    Labor History Today · 14 Mar 2026
```

- **The title defaults to the words.** Where the episode has a transcript — 144
  do, with millisecond `segments` — the text at the in-point *is* the best name a
  clip can have, and it is a string slice. Episodes without one fall back to
  `Show — 12:03–12:31`. The title is editable inline, because the automatic one
  will sometimes start mid-word.
- **Play is in place.** A clip is a range of an MP3 already streaming from the
  CDN, so playing one is `currentTime = in` and stop at `out`, using the page's
  existing player. Do not open the editor to hear something.
- **`⋯` holds** Edit, Download, Remove. Remove undoes for ten seconds by the same
  mechanism as Add.

This extends the filename philosophy already stated in the help — *"a clip
sitting in a folder in six months still explains itself"* — to the list. Every
row says what it is, where it came from and when.

### The empty state

The library is empty on first open and after any storage clear, and a modal
saying "No clips" teaches nothing. This application already has the right
pattern: the help examples are runnable and clicking one performs the search
([`static/index.html:831`](../static/index.html#L831)). Say what the library is
for and where the Add button lives — one sentence and a picture of the footer
beats a paragraph.

### Principles carried from the editor work

- **Drag is never the only way to do anything.** Phase 4 exists to make marking
  and trimming mouse-free; a library control reachable only by mouse would be the
  first thing to break that.
- **Nothing destructive without undo.**
- **The list works offline.** Local storage means it does, and in a studio that
  matters.

---

## Going shared, when it is asked for

Recorded because it was verified for this document, so that the work starts from
facts. **None of this is v1.**

**Storage exists and persists.** `lhf-data` is a named Docker volume mounted at
`/data` on both containers (`docker-compose.yml`), holding the 53 MB archive
database. It survives redeploys, for three independent reasons: `.dockerignore`
keeps `data/` and `*.sqlite` out of the build context entirely; the volume mount
covers the image's empty `/data`; and
[`docker-entrypoint.sh:60`](../docker-entrypoint.sh#L60) only creates a database
`if [ ! -f "$DB" ]`, with no `DROP` or re-init path anywhere in the script. A
`clips.sqlite` in that volume inherits all three protections.

**The architecture already anticipates a writer.** `docker-compose.yml` opens
with *"SQLite is in WAL mode, which is what makes a reader and a writer on the
same file safe"*, and the refresh container is a writer to that volume today.

**What is genuinely missing is two things:**

1. **A write path.** [`serve.py:602`](../serve.py#L602) is a stdlib
   `BaseHTTPRequestHandler` with `do_GET` and nothing else.
2. **Any authentication.** There is none, deliberately, and that has been correct
   while everything served is already-published material. A save button ends
   that.

**Three decisions that would keep it proportionate:**

- **A separate `clips.sqlite`, not a table inside `lhf.sqlite`.** The archive's
  recovery story is "re-scrape", which cannot bring back a producer's saved
  clips. Different recovery stories should not share a file, and a runaway write
  then cannot bloat or corrupt the archive.
- **One shared passphrase**, held as a Coolify environment variable — the
  mechanism already exists for `DATABASE_PATH`. Not accounts; just enough that a
  stranger who finds the URL cannot write. For a handful of colleagues that is
  proportionate, and accounts would be over-building.
- **`POST` and `DELETE` only, with a size cap.**

**Worth confirming before anything irreplaceable goes in that volume:** whether
the backup `docker-compose.yml` asks for actually exists. The archive can be
re-scraped; saved clips cannot.

**And note the strategic overlap.** `docs/ai-layer.md` blocks its entire AI layer
on the same three things — a key held properly, an admin interface, and
authentication. That layer is written, has never run, and costs **$4.35 once and
about $2.26 a year**. If authentication is ever built, it unlocks both. Neither
is blocked on hard technical work; both are blocked on the same missing shell.

---

## Parked for later

Ideas to consider if the flat list proves itself, roughly in the order I would
revisit them. **None is committed, and the first question about each is whether
anyone has asked for it.**

- **Labels, presented as folders.** Many-to-many, never directories. See the
  modelling trap above.
- **Ordered collections and a run sheet** — sequence clips, show cumulative
  duration against a target. The feature most specific to who these users are
  (broadcast slots are exact), and the most likely of these to be genuinely
  wanted.
- **ZIP export.** Genuinely easy: MP3s do not compress, so a *stored* zip is
  correct, which is about sixty lines of hand-written JS plus a CRC32 table — no
  dependency, no build step, and the bytes stay bit-identical. Deferred only
  because clips can already be downloaded one at a time.
- **Joined single-file export.** Frame concatenation works where the streams are
  compatible, and `mp3cut.js` already probes bitrate. Must probe and *refuse with
  an explanation* when they differ; silently producing a file that plays at the
  wrong speed is worse than not offering it, and re-encoding forfeits the
  bit-identical guarantee.
- **A cart wall for live use.** If anyone plays clips live during a recording,
  this is a different and possibly better product than the run sheet: a grid of
  pads, number keys, a countdown rather than a progress bar, and an explicit
  "arm the board" step that pre-cuts every clip to a Blob so **nothing touches
  the network while on air**. Worth asking about, because finding out in six
  months would be a shame.
- **AI.** Per `docs/ai-layer.md`, the highest-value item for this feature is
  **segment boundaries** — open an episode and see six candidate clips with in
  and out already set, which is the difference between a scalpel and a source of
  material. **Name repair** becomes a dependency the moment titles come from
  transcripts, since a clip auto-titled with a mangled name is worse than an
  untitled one. Everything live and conversational needs the key-and-auth shell
  first.
- **Sharing.** See above.

---

## Open questions

1. **Does anyone play clips live during a recording?** Not to build it — only
   because the answer changes what this product is.
2. **Does the volume backup exist?** Blocks nothing in v1, blocks anything shared.
3. **Is a joined single file wanted**, or do producers prefer the parts to
   assemble in their own tool? Decides whether that item is ever worth
   prototyping.
