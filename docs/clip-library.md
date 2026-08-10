# Clip library — design

**Status: ✅ BUILT, 9 August 2026.** Shipped as `static/clips.js` plus the
library, save and download dialogues in `static/index.html`, covered by
`tests/test-clips.mjs` (41 pure checks). Written, rewritten after the scope
discussion that cut it down, extended with labels and a
[What lives where](#what-lives-where) section, then built — all the same day.

**What shipped differs from this design in four places**, each recorded at
[As built](#as-built) rather than by editing the design silently:

1. **"Labels", not "tags"** — the word collided twice over.
2. **Labelling moved into a save dialogue.** Inline in the editor was invisible.
3. **A download icon on every row**, not a line in the `⋯` menu.
4. **Zip export shipped in v1**, with a naming dialogue. It was parked here.

**Companion to**
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
- **Tags, and a top-tags bar** — added to v1 on 9 August 2026 at the client's
  request. See [Tags](#tags--added-to-v1) for what that changed and what it
  replaced.

### Not in v1

Run sheets, target durations, the cart wall, ZIP export, joined export, AI, and
any form of sharing. Each is argued in
[Parked for later](#parked-for-later) — they are ideas to consider, not a
roadmap, and none of them should be built before the flat list has been used in
anger.

**Folders are not on that list**, and are not coming: tags do the job a folder
tree was wanted for, without the copying that makes a tree go wrong. See below.

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

> **Update, 9 August 2026.** Tags were added to v1 — see below. That does not
> reopen folders; it closes them. The prediction in this section was that if
> filing ever arrived it had to be labels rather than directories, and that is
> exactly what arrived. **No folder tree should be built on top of tags later**,
> because the reuse case that motivates one is already served.

## Tags — added to v1

Requested by the client on 9 August 2026, after seeing the flat list. Building
it, because the reasoning above already concluded that *if* filing arrived this
is the shape it had to take — so this is bringing a parked item forward, not
overturning a decision.

**One concern, stated once and then set aside.** Tags earn their keep at thirty
clips and are overhead at six: the first week of use will involve tagging things
that were findable anyway. That is a reason to keep the feature cheap and
optional, not a reason to withhold it, and the client asked with the list in
front of them. Nothing below makes tagging a required step.

### What it is

- **Tags are free text, many-to-many, user-authored.** A clip carries any number;
  a tag belongs to any number of clips. No hierarchy, no colours, no rename
  screen — a tag exists because a clip carries it and stops existing when the
  last one drops it.
- **A top-tags bar** above the list: the **six most-used** tags, with counts,
  ordered by use and tie-broken alphabetically so the bar does not reshuffle
  unpredictably as counts even out. The tail sits behind `+n more`. A bar that
  grows without limit stops being a summary and becomes a second list to read.
- **Selecting two tags is an AND**, and tags combine with the text filter. This
  matches the boolean search people already use upstairs rather than inventing a
  second mental model inside one product.
- **Tagging is inline** — hover a row, press the dashed `＋`, type, Enter.
  Existing tags autocomplete through a `<datalist>`.
- **Tags can also be set in the editor footer, before the add**, because you
  know a clip is a promo while you are cutting it, not later while scrolling a
  list. They persist across adds in one session: pulling four promos from one
  episode means tagging once. Re-typing `Promo` four times is how a tagging
  feature quietly stops being used.

### Two things that must be right or the feature rots

1. **Case folding on entry.** `promo` must resolve to an existing `Promo` rather
   than becoming a second tag beside it. A library where the same word exists
   twice in different cases stops working within a fortnight, and no amount of
   later tidying fixes the muscle memory. Match case-insensitively against
   existing names; keep the first spelling as canonical.
2. **Removing the last use removes the tag.** There is no tag registry to garbage
   collect, precisely so that there is nothing to garbage collect. Derive the tag
   list from the clips on every read.

### The naming collision — unresolved

**This product already uses "tags" to mean something else**: the 232 people,
bands, museums and books lifted from hyperlinks in the show notes. Those are
global, derived, identical for every visitor and attached to *episodes*. Clip
tags are local, hand-written, private to one person and attached to *clips*.

That is two meanings for one word inside one product, which is the exact problem
that barred *Replay* in `docs/audio-editor-dev.md` — "this product already uses
replay and re-air to mean putting an old episode back on the air, and two
meanings for one word inside one product is worse than a little jargon."

The consistent call would be **Labels** for the clip-side concept. The client
asked for "tags", so the mockup says Tags. **Flagged, not decided** — it is a
one-word change now and an expensive one after the client guide ships with it.
Recorded in [Open questions](#open-questions).

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

## What lives where

**Settled, and not a question this build reopens: v1 is browser storage.** What
the client is still deciding — shared clips, episodes that have fallen off the
feed, the AI features, how many people use this — is v2, and none of it blocks
the work. The seam in decision 1 above is what keeps that true.

This table is the whole boundary. It is the source for the plain-language
version in `docs/client-guide.md`, and the two must agree.

| Thing | Where | Rebuildable if lost? |
|---|---|---|
| Episodes, transcripts, search index | Server (`lhf.sqlite` on the `lhf-data` volume) | **No longer** — both shows are at the feed cap. See `HANDOFF.md` → Backups. |
| Light / dark choice | This browser — `localStorage["lhf-theme"]` | Trivially; it is one click. |
| Waveform peaks | This browser — IndexedDB `lhf-peaks`, keyed on audio URL, `v: 2` | Yes, at the cost of one 30–105 MB download. |
| **Saved clips and their tags** | **This browser — `localStorage`** | **No.** This is the new one, and the only client-side data that is not derived from something else. |

**Verified 9 August 2026** by reading the source, because a client-facing claim
about where their work is kept should not be written from memory: the app
persists exactly two things today, `lhf-theme`
([`static/index.html:2242`](../static/index.html#L2242)) and the peaks database
([`static/waveform.js:17`](../static/waveform.js#L17)). Nothing else. In
particular the update-prompt dismissal is **not** persisted — `hushedVersion`
([`static/index.html:4213`](../static/index.html#L4213)) is an ordinary variable,
so it is forgotten on reload. `HANDOFF.md`'s "dismissal is remembered per build"
is true only within a session, and the client guide must not imply otherwise.

### What this means for the interface

Saved clips are the **first thing in this application a user can lose**. Peaks
re-download; a theme is one click; a clip that took twenty minutes to find is
gone. Three consequences, all in the mockup:

- **Every surface that writes says so, once, quietly.** The library modal and its
  empty state both carry one line: *"Stored on this computer only. Clearing your
  browser data removes them."* Not a warning banner — a fact, stated where the
  belief is formed.
- **The empty state says it before there is anything to lose**, which is the only
  time saying it is free.
- **Download stays the primary action in the editor footer.** A downloaded MP3 is
  the copy that outlives the browser, and demoting it in favour of Add would
  quietly make the losable thing the default.

### Features that would need the server

All four want the same missing shell, and that is the point — it is one decision,
not four:

| Feature | Needs |
|---|---|
| Seeing a colleague's clips | Write path + auth |
| Clips that survive a new laptop | Write path + auth |
| Topics, guests, interviewers, segment boundaries | Key + admin screen + auth |
| Staff notes, tag corrections, `replayed_at` | Admin screen + auth |

`serve.py` is `do_GET` only ([`serve.py:602`](../serve.py#L602)) and there is no
authentication, deliberately, which is correct while everything served is
already-published material. **A save button ends that**, and the first write
endpoint is a security decision rather than a feature increment. Making it once,
on purpose, is much better than arriving at it three times by accident.

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
{ id, url, guid, title, show, date, in, out, createdAt, tags: [] }
```

About 150 bytes, plus a few per tag. A thousand clips is well under 200 KB
against `localStorage`'s ~5 MB, so there is no storage problem to solve and no
reason to reach for IndexedDB, which is already carrying the peaks cache and is
asynchronous.

**`tags` is an array on the clip, and there is no tag table.** The list of tags
that exists is whatever the clips currently carry, derived on read. This is the
cheap half of decision 1 above: a separate registry would need creating,
renaming, merging and garbage collecting, all to store information the clips
already hold.

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

### The tag bar

Directly under the filter box, above the list, built from the app's existing
filter furniture rather than a new control: `.chip`, its `aria-pressed` state and
the dashed `.chip.all` that reads as the resting position
([`static/index.html:204-235`](../static/index.html#L204-L235)). The episode
filters upstairs already look and behave exactly like this, which is most of the
argument for it.

```
TAGS   [All 6]  [Promo 4]  [Interview 2]  [Intro 2]  [Music 1]  [Atmos 1]  +1 more
```

### The row

```
▶   "…and that's why we marched."               12:03 – 12:31   28.4s   ⋯
    Labor History Today · 14 Mar 2026
    [Promo ×] [Marches ×] [＋ tag]
```

- **The title defaults to the words.** Where the episode has a transcript — 144
  do, with millisecond `segments` — the text at the in-point *is* the best name a
  clip can have, and it is a string slice. Episodes without one fall back to
  `Show — 12:03–12:31`, **set in italic** so a generated label never passes for
  something that was said. The title is editable inline, because the automatic
  one will sometimes start mid-word.
- **Play is in place.** A clip is a range of an MP3 already streaming from the
  CDN, so playing one is `currentTime = in` and stop at `out`, using the page's
  existing player. Do not open the editor to hear something.
- **Tags sit on their own line**, quieter than the bar above — smaller, hairline
  border, `--ink-3`. They are labels first and controls second, but clicking one
  filters by it, because having read a tag the obvious next thought is "show me
  the others". The `×` and the dashed `＋ tag` appear on hover or focus only, so
  a row at rest is information rather than a control panel.
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

- **A separate `clips.sqlite`, not a table inside `lhf.sqlite`.** Different
  recovery stories should not share a file, and a runaway write then cannot
  bloat or corrupt the archive.
- **One shared passphrase**, held as a Coolify environment variable — the
  mechanism already exists for `DATABASE_PATH`. Not accounts; just enough that a
  stranger who finds the URL cannot write. For a handful of colleagues that is
  proportionate, and accounts would be over-building.
- **`POST` and `DELETE` only, with a size cap.**

**The volume needs a backup before anything irreplaceable goes in it — and the
archive already qualifies.** An earlier draft of this document said "the archive
can be re-scraped; saved clips cannot". That is no longer true. Measured on
9 August 2026, both shows hold **exactly 100 episodes**, which is Podbean's feed
cap, and `episodes` rows are never deleted. The next episode of each show
therefore pushes the oldest out of the feed while the database keeps it, and from
that moment the volume is the only copy of something. Both shows are weekly.

`HANDOFF.md` carries the numbers and the WAL-safe backup command
(`sqlite3 /data/lhf.sqlite ".backup /somewhere/else.sqlite"` — a plain file copy
of a live SQLite database is not safe). **This is a live task independent of the
clip library**, and it is the reason a shared library would need a backup story
rather than inheriting one.

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

- ~~**Labels, presented as folders.**~~ **Pulled into v1 on 9 August 2026** as
  tags — see [Tags](#tags--added-to-v1). Many-to-many, never directories, as this
  list always said it would have to be.
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

## As built

Shipped 9 August 2026. Everything above is the design as written; this section
is where it and the code disagree, and why.

### 1. "Labels", not "tags" — the collision was worse than recorded

The naming question above listed three claimants. Building it settled the
argument: the first two — the 232 producer-hyperlinked entities and the
proposed 34-term subject vocabulary — are both *shared, derived and attached to
episodes*. The clip-side one is **private, hand-typed and attached to a clip**.
It is the odd one out, so it takes the different word.

`Tags` therefore keeps its existing meaning throughout, `Topics` stays free for
the subject vocabulary in `docs/ai-layer.md`, and clips carry **Labels**. Zero
churn on anything already shipped. The help modal says so explicitly, because
two words for adjacent concepts needs one sentence of disambiguation or it
generates a support question a week.

### 2. Labelling moved out of the editor and into a save dialogue

The design put a `＋ label` chip in the editor body. Built, it was reported as
**"so dark I missed it entirely"** — correctly. The clip editor already carries
two waveforms, a transport, four tool buttons and a readout; a dashed `--ink-3`
chip in that company is decoration, not a control.

So `＋ Add to library` opens a dialogue instead, carrying the span, an editable
title, chosen labels as full-weight chips, a **Reuse** row of existing labels as
one-tap chips, and the storage line. Focus lands on the label field, not the
title, because labelling is why the dialogue exists.

**This is a better surface than the inline row ever was**, and not only for
visibility: it is the obvious home for anything else a saved clip should carry.

The lesson generalises and is worth keeping: **on a dense surface, `--ink-3` is
decoration.** Anything that must be found needs its own surface or full ink.

### 3. Download is a row control, not a menu item

`⋯` was to hold Edit, Download and Remove. Download is the outcome people came
for, so it is an icon on the row; the menu keeps the two that are rarer and more
consequential.

### 4. Zip export shipped in v1

Parked under [Parked for later](#parked-for-later) as "deferred only because
clips can already be downloaded one at a time". Asked for and built the same
day, and cheaper than the sixty hand-written lines estimated there, because
`static/zip.js` already existed for the archive package.

Three things the design did not anticipate:

- **Entries are stored, not deflated** (`makeZip(files, { compress: false })`).
  MP3 frames are already compressed, so deflating them is a wasted pass over
  every megabyte — and stored keeps the bytes bit-identical, which is the
  guarantee the whole export path exists to protect.
- **A naming dialogue.** `lhf-clips-2026-08-09.zip` in a downloads folder says
  nothing about why it was made, so the user names the file and can attach a
  note. The note lands at the top of `clips.txt` beside a listing of every clip.
- **Scope is stated, never implied.** Filtered by a label, the button reads
  *"Download these 3"* and the file is named `-filtered`. This is the archive
  export's own rule — both counts always visible so "a file quietly holding 78
  of 200" cannot happen — applied to a bag of clips.

Duplicate filenames are numbered (two clips from the same second of one episode
would otherwise unpack to a single file), and a clip that cannot be fetched is
named in `clips.txt` under **COULD NOT BE INCLUDED** rather than silently
missing.

### Also built, not in the design

- **A scrubber on the playing row.** It exists only while that clip plays and
  vanishes when it stops or another starts, so the bar itself is the signal for
  which row is live. Painted by direct DOM writes: `timeupdate` fires ~4×/second
  and re-rendering the list at that rate would discard a title mid-edit and
  close an open row menu.
- **Storage is versioned** (`{ v: 1, clips: [...] }`), and a wrong or missing
  version reads as empty rather than as current data — the same rule as the
  peaks cache, for the same reason.

### Two bugs found by building it

1. **`serve.py`'s `/api/version` did not hash `zip.js`.** It listed
   `index.html`, `mp3cut.js`, `waveform.js` only, so shipping a fix to the
   archive packager alone could never prompt an open tab to reload. Present
   since `zip.js` was added. Both it and `clips.js` are in the tuple now, and
   verified: touching either moves the hash.
2. **The editor's Space handler would have fired at a text field.** It exempted
   `.modal-actions` only, so typing a space in the new label input would have
   played audio instead. This is the third instance of the shape recorded in
   `docs/audio-editor-dev.md`, so it was fixed as a class: the editor's keyboard
   bails when a dialogue is open above it **and** whenever focus is in an
   `input`, `textarea` or contenteditable.

### One design flaw the build exposed

The masthead buttons were styled by **three copies of the same rule, keyed by
id**. A fourth button matched none of them and rendered as a white browser
default in a dark header. Consolidated to one `.mast-btn` class.

While there, the ink scale was measured: `--ink-3` was **3.31:1 dark / 3.30:1
light** — a non-text contrast level, used throughout for small-caps labels at
0.66rem, placeholders and meta lines. Raised to `#837f75` / `#746f66`
(**4.53:1 / 4.50:1**), hue untouched so the warm bias survives. This is why the
interface reads brighter; it was not a clip-library change.

---

## Open questions

1. ~~**"Tags" or "Labels" for the clip-side concept?**~~ **Resolved 9 August
   2026 — Labels.** See [As built](#1-labels-not-tags--the-collision-was-worse-than-recorded).
   The reasoning, kept because the table is what settled it: the word had
   **three claimants**, and the clip-side one is the odd one out.

   | Meaning | Scope | Source |
   |---|---|---|
   | 232 entities — people, bands, museums, books | Episodes, global, shared | Producer hyperlinks (≈LCNAF names) |
   | 34 subjects — Mining, Organizing, Child Labor | Episodes, global, shared | *Proposed* — `docs/ai-layer.md` → A shared vocabulary (≈LCSH) |
   | Personal labels — promo, intro, atmos | Clips, local, private to one person | This document |

   The first two are legitimately both "tags" and libraries deliberately carry
   both axes. **The third is the odd one out** — it is the only one that is
   hand-written, private and unshared — which makes it the one that should take
   the different word. See [the naming collision](#the-naming-collision--unresolved).
   A one-word change today; an expensive one once the client guide is out.
2. **Does anyone play clips live during a recording?** Not to build it — only
   because the answer changes what this product is.
3. **Does the volume backup exist?** Blocks nothing in v1, blocks anything shared.
4. **Is a joined single file wanted**, or do producers prefer the parts to
   assemble in their own tool? Decides whether that item is ever worth
   prototyping.
