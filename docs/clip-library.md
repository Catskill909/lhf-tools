# Clip library — design discussion

**Status:** discussion only. Nothing here is built, costed or committed.
Written 9 August 2026. **Companion to** `docs/audio-editor-dev.md`, which lists
"clip bin", "run sheet", "named clips saved as citations" and "a shared clip
library" as four separate brainstorm bullets. This document argues they are
mostly **one feature**, works out what it costs, and designs the surface.

The editing surface is now good enough to decide what to export
(`audio-editor-dev.md`, Phases 1–4). The next bottleneck is one level up: a
producer building a promo pulls three or four quotes and today that is three or
four unconnected trips through the modal, each ending in a file in a downloads
folder with no memory of where it came from.

---

## The one-paragraph version

**A clip is not a file. It is a citation:** a recording, an in-point, an
out-point, a title. About eighty bytes. Every hard-looking question about a clip
library dissolves once that is accepted — storage is trivial, sharing is a URL,
nothing needs uploading, and the only genuinely expensive feature in the whole
idea is playing a sequence back as continuous audio. What is left is not a file
manager but **an ordered list of moments with a duration target**, which is a
broadcast run sheet, which is the thing nobody else builds for podcast archives.
The MP3 is a render of a library entry, not the entry itself.

---

## Four brainstorm bullets, three real things

| Name in the brainstorm | Lifetime | Ordered? | Audience |
|---|---|---|---|
| Clip bin | one session | no | you |
| Run sheet | one production | yes, and to a target | you, then whoever reads the sheet |
| Named clips as citations | permanent | no | you, later |
| Shared clip library | permanent | curated | the organisation |

The first three differ only in **how long you keep it** and **whether order
matters** — not in what they store, not in what a row looks like, and not in
what you do to a row. Building them separately would produce three lists with
three add buttons and three places to look for the quote you know you saved.

**Recommendation: one list, one noun.** Call it the **Library**. Order is always
present (a list has an order whether or not you use it). The run sheet is not a
second screen but a **mode** on the library: set a target duration and the
cumulative column and the fill indicator appear. A clip that is "just saved" and
a clip that is "third in the promo" are the same record, viewed with the target
turned off or on.

The fourth — the shared library — is genuinely different, and it is different
for one reason only: it needs to know **who you are**, and this application has
no concept of that. See *Storage* below. It is a client conversation, in the
same category as fades.

---

## Constraints, verified today

Some of these are carried from `audio-editor-dev.md`; the server ones were
checked against the code for this document.

- **The server is read-only and GET-only.** [`serve.py:602`](../serve.py#L602)
  is a stdlib `BaseHTTPRequestHandler` with `do_GET` and nothing else. There is
  no `do_POST`, no write path, and no library, cookie or header anywhere in the
  file that resembles authentication.
- **The deployment is public and unauthenticated.** `docker-compose.yml`
  publishes 8000 behind Coolify's proxy with no auth layer in front. **Any write
  endpoint added to this server is an open write endpoint on the public
  internet.** That is not an argument against ever adding one; it is an argument
  that the first write endpoint is a security decision, not a feature.
- **The database survives a refresh, and would carry a `clips` table safely.**
  Ingest is additive — `CREATE TABLE IF NOT EXISTS` throughout
  ([`ingest/enrich.py:42`](../ingest/enrich.py#L42),
  [`ingest/extract.py:179`](../ingest/extract.py#L179)) — and the file lives in
  the `lhf-data` volume shared by the web and refresh containers. But
  `docker-compose.yml` describes that volume as *"the only copy of the scraped
  archive"*, and its recovery story is "re-scrape". Putting user-authored clips
  in the same file changes backup from a convenience into an obligation, because
  a re-scrape cannot recreate a producer's saved quotes.
- **Zero server load, no build step, no dependencies.** Unchanged.
- **Export is a byte copy of MP3 frames.** This constrains joined export, below.

---

## The identity trap — read this before designing anything

Episode ids are `INTEGER PRIMARY KEY` assigned in ingest order
([`ingest/ingest.py:240`](../ingest/ingest.py#L240)). Rebuilding the volume from
empty can hand the same number to a different episode.

**This project has already been bitten by exactly this.**
[`HANDOFF.md:600`](../HANDOFF.md#L600) records waveform peaks cached under
`ep-<id>`, which meant a returning visitor could get another show's waveform and
*cut a clip from the wrong audio while it all looked correct*. The fix was to key
on the audio URL, which identifies the recording rather than its row.

**The existing share link has the same bug today.** `?ep=123&from=522&to=549`
([`static/index.html:3577`](../static/index.html#L3577)) is fine while the
volume survives, and wrong the moment it doesn't — a link someone emailed in
March opens a different episode at the same timecode, with no error and no
visible symptom. A clip library multiplies this by however many entries it
holds, and unlike a cache it cannot be silently re-derived: a stale library entry
is a producer's saved judgement pointing at the wrong recording.

**The fix, and it should land before any library work:**

- Store `guid` (or the audio URL — the peaks cache already settled that
  argument) as a clip's episode reference. Resolve it to a row id at open time.
- Keep `?ep=` working for links made inside a session, but add a cheap
  integrity token: `?ep=123&g=<first 8 hex of sha1(guid)>`. On open, resolve
  `ep`, compare, and on mismatch fall back to a lookup by hash. Short enough not
  to disfigure the URL, sufficient to make a wrong episode impossible rather
  than merely unlikely.
- The server needs a way to answer "which episode has this guid hash" — one
  extra branch in `do_GET`, still read-only.

This is **Phase A** below, and it is worth doing whether or not the library is
ever built.

---

## Storage — three options, one recommendation

| | Server change | Auth needed | Shared | Survives browser clear | Backup story |
|---|---|---|---|---|---|
| **A. localStorage only** | none | no | no | no | none |
| **B. `clips` table in SQLite** | `do_POST`, new table | **yes** | yes | yes | must be added |
| **C. Local, plus share-by-link** | one read endpoint | no | by sending a link | no | the link |

**Recommend C, which is A plus an export path, and defer B.**

The reasoning is arithmetic. A library entry is `{guid, in, out, title, note}` —
call it 150 bytes with a generous title. A thousand clips is 150 KB against
localStorage's ~5 MB. There is no storage problem to solve, so paying for a
server write path buys exactly one thing: **other people seeing your list**.

And that one thing is where the cost is. A public unauthenticated write endpoint
on a server whose data volume is the only copy of the archive is not a feature
increment — it is the moment this application acquires an accounts system, or
acquires a spam problem. Neither belongs in the same sprint as a list widget.

**Option C gets most of the value for none of it.** Six clips at 150 bytes
compress and base64 into a URL comfortably under 2 KB — a run sheet fits in a
link. "Send Harold the promo running order" becomes a copied URL, and the
receiving browser can merge it into their own library. A JSON file export covers
the archival case for the same code. Sharing without accounts, backup without a
server.

State the honest cost of C plainly in the client conversation: **a library held
in the browser is lost if the browser's storage is cleared, and is not visible
on a second machine.** For a producer working on one laptop that is acceptable;
for a newsroom of five it is not, and that is precisely the question that
decides whether B is ever needed.

---

## The GUI

### Where it lives

**A counter in the header, opening a modal.** The header currently holds
Export / Help / Theme ([`static/index.html:1350`](../static/index.html#L1350));
Library joins them as a fourth, showing a count when non-empty — `Library 3`.
The count is the whole ambient presence the feature needs: it answers "have I
already grabbed something from this episode today" without opening anything.

Two alternatives, both rejected:

- **A persistent dock or drawer at the page edge.** The search zone is already
  sticky and owns the top of the viewport
  ([`static/index.html:133`](../static/index.html#L133)), and the results list is
  dense by design. A permanently visible bin would compete with the archive for
  the same attention, every session, including the many sessions where nobody is
  making a clip.
- **Living inside the clip editor only.** Wrong scope: the list is most useful
  while *browsing*, deciding whether a quote you half-remember is already saved.
  A library you can only see while editing a clip is a bin, not a library.

**Stacking rule.** There is already a note at
[`static/index.html:2386`](../static/index.html#L2386) about `#clipModal` and
`#exportModal` sharing a z-index and being told apart by DOM order. A third
dialogue joins that arrangement, so fix the rule rather than inheriting the
accident: **the library sits under the clip editor.** "Edit" on a library row
opens the editor on top; closing the editor returns you to the list you were
reading, not to the archive. That is the only stacking that makes the round trip
feel like one task.

### Adding a clip, from the editor

The footer today is `Cancel | Download MP3`
([`static/index.html:1478`](../static/index.html#L1478)). It becomes:

```
Cancel                    ＋ Add to library      Download MP3
```

Download stays primary — it is still the action that produces the deliverable,
and demoting it to make room would be reorganising the tool around the new
feature rather than adding to it. Add takes the quiet-button weight already used
by Cancel, with an accent to distinguish it from a dismissal.

**Adding must not close the modal**, and this is the decision that determines
whether the feature is worth building. The workflow that justifies a library is
pulling three quotes from one episode; if each add closes the dialogue, the
round trips it was meant to remove are still there. So: the selection stays
exactly where it is after an add. Nudge a handle and add again and you have two
variants of the same quote — which is a real thing producers do when they cannot
decide between two out-points, and today is impossible without downloading both.

Confirmation goes in `#clipStatus` ([`static/index.html:1475`](../static/index.html#L1475)),
the strip already used for export progress: *"Added — 3 in library"* with an
**Undo** that lives for about ten seconds. No toast, no new furniture.

**Keyboard:** the editor binds `Space`, `I`, `O`, `[`, `]`, arrows and `Home`.
`A` is free and mnemonic. Note that the Space-exemption fix from the Phases 1–2
audit (controls in `.modal-actions` keep Space for activation rather than
yielding it to the transport) covers the new button automatically — worth
verifying rather than assuming, since that fix was itself a shipped bug.

### The row

```
⋮⋮   ▶   "…and that's why we marched."          12:03 – 12:31   28.4s   ⋯
         Labor History Today · 14 Mar 2026
```

- **The title defaults to the words.** If the episode has a transcript — 144 of
  them do, with millisecond `segments` — the text at the in-point *is* the best
  name a clip can have, and it is a string slice. This is the brainstorm's
  "out-cue text" idea arriving early, cheaply, and in the place where it does the
  most good. Episodes without a transcript fall back to
  `Show — 12:03–12:31`. The title is editable inline, because the automatic one
  will sometimes start mid-word.
- **Play is in-place.** A clip is a range of an MP3 already streaming from the
  CDN, so playing one is `currentTime = in`, stop at `out`, using the page's
  existing player rather than the editor's transport. Do not open the editor to
  hear something.
- **Reorder by drag *and* by keyboard** (`Alt+↑` / `Alt+↓`). This project has
  been deliberate about keyboard reach — Phase 4 exists to make marking and
  trimming mouse-free — and a drag-only reorder would be the first control that
  breaks that. It is also the accessible-by-default choice.
- **`⋯` holds** Edit (opens the clip editor at this range), Copy link, Download
  this one, Remove. Remove is undoable for ten seconds by the same mechanism as
  Add.

### The run-sheet layer

Off by default. Set a target duration (mm:ss) and three things appear:

1. **A cumulative column** — the offset at which each clip begins in the
   assembled piece. This is the actual working number: knowing clip 4 starts at
   2:12 is what tells you whether the piece is front-loaded.
2. **Running total against target**, stated as remaining or over — *"2:41 / 3:00
   — 19s short"*.
3. **A fill line** across the list where the target is reached, with rows past it
   dimmed. Over-running a broadcast slot is the failure this whole mode exists to
   prevent, and it should be visible without reading a number.

This connects directly to the brainstorm's **exact-duration trim**: once the
sheet says you are 8 seconds over, a row action "trim 8s from this clip" can open
the editor with that figure on screen and snap-to-silence bounded by it. The
run sheet is what turns "make this exactly 3:00" from a wish into a stated,
solvable problem — which is the argument for building the list before building
the trim.

### Getting things out

- **Download each clip** — the existing export path in a loop, reusing the
  per-file progress bar.
- **Download joined, as one MP3** — genuinely possible under the frame-copy
  guarantee, *conditionally*. Concatenating MP3 frames works when the streams are
  compatible; `mp3cut.js` already probes bitrate, so the check exists. Two shows
  from one publisher very likely share encoder settings, which makes this worth
  prototyping. **The rule must be: probe, and refuse with an explanation when the
  streams differ.** Silently producing a file that plays at the wrong speed after
  the join is worse than not offering the feature, and re-encoding to force it
  forfeits the bit-identical guarantee — the same client decision as fades.
- **The run sheet as text or CSV** — titles, timecodes, cumulative offsets,
  out-cue words. This is the artefact a broadcaster actually hands to someone.
  The delimited writer at [`serve.py:514`](../serve.py#L514) already exists,
  though for a client-side list it is probably less code to do it in the browser.
- **Copy all as a link** — option C's sharing path.

### The empty state

The library is empty on first open and after any storage clear, and an empty
modal that says "No clips" teaches nothing. This application already has a good
pattern for this: the help examples are runnable, and clicking one performs the
search ([`static/index.html:831`](../static/index.html#L831)). The empty state
should say what the library is for, and where the Add button lives — one
sentence and a picture of the footer beats a paragraph.

---

## Sequencing

Each phase is independently shippable, as in `audio-editor-dev.md`.

- **Phase A — Stable clip identity.** `guid`-based references and the `&g=`
  integrity token on share links. Independent of the library, worth doing on its
  own merits, and the thing that ages worst if left. Do it first.
- **Phase B — The library, locally.** Add button, header counter, modal, list,
  reorder, remove, per-row play and edit, localStorage persistence, empty state.
  No server change whatsoever.
- **Phase C — The run-sheet layer.** Target, cumulative column, fill line,
  transcript-derived titles, CSV/text export.
- **Phase D — Joined export.** Prototype first, gated on the bitrate probe
  across both shows. May come back "not possible without re-encoding", which is
  a finding, not a failure.
- **Phase E — Sharing.** Link/JSON round trip is small and belongs in B or C.
  A *server-side* shared library is blocked on the identity and authentication
  conversation with the client and should not be scheduled before it happens.

Sequenced playback — hearing the assembled run sheet as continuous audio — is
deliberately absent. It means gapless-ish playback across several CDN files, and
while it is achievable by pre-loading the next clip's audio element, it is a
different order of difficulty from everything above and would drag the first
useful version out by weeks. Revisit once the list exists and someone asks.

---

## Open questions for the client

These change the design, not just the schedule:

1. **Who is the library for — one producer's afternoon, or the newsroom?** This
   single answer decides between option A/C and option B, and with it whether
   this application acquires user accounts.
2. **Should a saved clip ever be public?** "Best moments from labor podcasts
   this month" is an editorial product, and an attractive one, but it implies
   curation, moderation and a public write path.
3. **Is a joined single-file export actually wanted**, or do producers want the
   parts to assemble in their own tool? The answer decides whether Phase D is
   worth prototyping.
4. **Is losing the library when a browser clears its storage acceptable** for the
   first version? If yes, ship B and C quickly. If no, question 1 has already
   been answered and the accounts conversation starts now.

---

## The bug class to watch for

Three bugs of one shape shipped out of `audio-editor-dev.md`: **state captured
at press time, invalidated by a later edit** — Repeat, play-after-moving-the-lead
-handle, and the 2s lead-in. Each had a test that only exercised the static case.

A library has the same shape with a longer timescale: **a row captured at add
time, invalidated by a refresh that changes the world underneath it.** Episode
renumbered, audio URL changed by the CDN, transcript re-derived so the out-cue
words move, episode withdrawn from the feed entirely. The test discipline is
identical to the one that caught the transport bugs — *change the world under the
saved object and assert what happens* — and Phase A is the first instance of it.
