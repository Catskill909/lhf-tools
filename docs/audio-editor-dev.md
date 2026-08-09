aduition # Audio editor — audit and development plan

**Status:** audit complete. **Phases 1–4 built and verified** (9 August 2026).
Phase 5's test work was done alongside each phase rather than after —
`tests/test-waveform.mjs` is now 49 pure checks, and the browser suites are
listed at the end. Written 9 August 2026.
**Companion to** `docs/audio-editor-spec.md`, which records the editor **as
built** (frame-copy export, bitrate probing, cut accuracy). That document is
still correct and nothing here contradicts it — the export path is sound and is
not being touched. This document covers the **editing surface**: what a producer
sees, hears and manipulates before they press Download.

**Scope of the problem, in one line:** the export is broadcast-grade; the
editing surface is not yet good enough to decide *what* to export.

---

## The one-paragraph version

The editor's state model is `{in, out}` and nothing else. **There is no
playhead.** That single absence accounts for most of the complaints: there is
nothing to stop *to*, nowhere for a click-to-listen position to live, no cursor
to set in/out points from, and no reference for a time ruler. Separately, the
waveform is stored at **0.51 seconds per peak bucket**, which means the pauses
between words are not merely hard to see — they are absent from the data, and no
rendering change can recover them. Fix the state model, then fix the resolution.
Everything else follows from those two.

---

## Audit

### A1 — There is no stop. The editor locks you out.

`playRange(from, to)` at [`static/index.html:2790`](../static/index.html#L2790)
has no stop path. All six transport buttons call it. A second click *restarts*
playback rather than stopping it. Nothing binds Space inside the modal — the
Space handler at [`static/index.html:2318`](../static/index.html#L2318) belongs
to the page's main player, not the editor. The clip modal binds only `Escape`,
which closes the whole dialogue.

The only `pause()` reachable by a user is inside `closeClip()`
([`static/index.html:2704`](../static/index.html#L2704)).

**Consequence:** press "Play selection" on a 30-second selection and you have no
way to stop it except discarding your edit. For an editor — a tool whose entire
job is repeated listen/adjust cycles — this is the defect that makes the others
matter.

**Severity: blocking.** Nothing else on this list is worth doing first.

### A2 — The waveform is stored at half-second resolution

[`static/waveform.js:15`](../static/waveform.js#L15) sets `BUCKETS = 4000` for
the **whole episode**, regardless of length.

| Episode length | Seconds per bucket |
|---|---|
| 32 min (Labor History Today, average) | 0.48 s |
| 34 min (the episode in the screenshot) | 0.51 s |
| 54 min (Power Hour, average) | 0.81 s |

The zoomed view in the reference screenshot spans ~42 s across ~1,860 CSS
pixels. That is **~82 peak buckets stretched over 1,860 pixels — 23 pixels per
bucket**. Hence the staircase.

The decisive detail is not the blockiness, it's the reduction. `reducePeaks()`
([`static/waveform.js:27`](../static/waveform.js#L27)) takes the **min and max**
over each bucket. A 0.3-second pause between two words is absorbed into whichever
syllable is loudest within the same half-second. **The silence is not in the
stored data.** Redrawing, smoothing or interpolating cannot bring it back.

### A3 — Snap-to-silence inherits A2, and is quantised to a half-second grid

This one was not obvious until the numbers were worked through, and it is worse
than a display problem.

`snapToSilence()` ([`static/waveform.js:227`](../static/waveform.js#L227))
computes `perSec = pairs / duration` — for a 34-minute episode that is
**1.96 buckets per second**. Its default `windowSec = 1.5` therefore becomes
`span = round(1.5 × 1.96) = 3` buckets, and it returns `best / perSec`.

So the function:
- searches ±3 buckets (±1.5 s, correct), but
- **can only return a value on a 0.51-second grid.**

It cannot land in the gap between two words, because the gap is narrower than
one step of its output. "Snap to silence" — described in the handoff as "the
single most useful editing aid" — is currently rounding the cut to the nearest
half-second. Fixing A2 fixes this for free, at roughly 50× the precision, with
no change to the algorithm.

### A4 — Linear amplitude scaling hides everything quiet

[`static/waveform.js:173`](../static/waveform.js#L173) maps amplitude to pixels
linearly (`hi * mid * 0.95`). For speech that means normal dialogue saturates
near full height while room tone, breath and low-level hum sit within a pixel or
two of the centre line — visually indistinguishable from digital silence.

This is the second half of "see low audio volume clearly." Even at perfect time
resolution, a linear scale will not show a producer that a passage is quiet but
not empty, which is exactly the judgement they need to make.

### A5 — You cannot zoom in past the length of your own selection

`clipWindow()` ([`static/waveform.js:207`](../static/waveform.js#L207)) computes
`span = min(dur, (outSec - inSec) + pad * 2)` — the window **always contains the
entire selection**. `PAD_MIN` is 0.25 s.

With a 30-second selection, the tightest possible view is **30.5 seconds**. The
zoom control bottoms out long before it reaches frame-level detail, and the "6.0s"
label describes only the padding, not what you are looking at.

The invariant is deliberate and documented — both handles stay grabbable at every
zoom level. But it is in direct conflict with detail work, because **detail work
happens at one edge at a time**. The existing "Audition in" / "Audition out"
buttons already concede this: they treat the edges separately. The zoom should
do the same.

### A6 — The overview cannot preview, because there is nowhere to preview to

`mousedown` on `#waveAll` ([`static/index.html:2777`](../static/index.html#L2777))
is hard-bound to `overviewSeek()`, which moves the whole selection. There is no
second interaction available and no playhead to carry a preview position.

### A7 — No time axis on either waveform

Neither canvas draws a ruler. Nothing on screen tells you where 12:30 is in the
episode, or how wide the zoomed window actually is. The `In` / `Out` / `Length`
readout gives absolute values but no spatial reference.

### A8 — The tool row does not distinguish listening from trimming

Six buttons sit in one undifferentiated row
([`static/index.html:1383`](../static/index.html#L1383)): four play actions and
two edit actions, identical in weight. Nothing reads as a transport, which is
part of why the missing stop is not immediately obvious as an omission.

---

## Constraints that shape every fix below

Carried forward from `docs/audio-editor-spec.md`, because they rule options in
and out:

- **Export is a byte copy of MP3 frames.** No decode, no re-encode, bit-identical
  output. This is a headline client-facing guarantee.
- **Therefore fades are impossible without giving that up.** A cut at a non-silent
  point will click. This is the real reason snap-to-silence carries so much weight,
  and the strongest argument for making the noise floor *visible*. Any fade,
  normalise or gain feature forfeits the lossless guarantee — a client decision,
  not a bug fix. **Flag it; do not quietly implement it.**
- **Zero server load.** Everything runs in the browser against the CDN.
- **No build step, no dependencies.** Single HTML file plus two ES modules.
- **The first open of an episode is a 30–105 MB download.** Peaks are cached in
  IndexedDB keyed on the audio URL. Any change to the peak format must not force
  a re-download of episodes users already have — see the cache-versioning trap
  in Phase 3.

---

## Phase plan

Phases are ordered so each one is independently shippable and independently
verifiable. Phases 1 and 2 are an afternoon each. Phase 3 is the substantial one
and changes a persisted format, so it is deliberately last among the fixes.

### Phase 1 — Playhead and a real transport — ✅ **built**

**Goal:** you can stop. Everything downstream becomes possible.

**The state change:** add `clip.playhead` (seconds) and `clip.playing` (bool) to
the `clip` object created at
[`static/index.html:2643`](../static/index.html#L2643). This is the load-bearing
part of the whole plan — do it as its own commit.

**Changes**
- Rewrite `playRange()` into a small transport: `play(from, to)`, `pause()`,
  `stop()`, `toggle()`. Pause holds the playhead; stop returns it to the
  selection's in-point.
- The RAF tick updates `clip.playhead` rather than only repainting.
- `drawWave()` already accepts `playhead` — start passing it on both canvases.
- New transport row **between the two waveforms**: play/pause, stop, playhead
  timecode, loop-selection toggle. It acts on both views, so it belongs at the
  seam; the modal footer stays reserved for Download.
- Move `audIn` / `audOut` / `snapIn` / `snapOut` to a separate row *under* the
  zoom view, where trimming happens. Split listening from trimming (fixes A8).
- Bind `Space` (play/pause) and `Home` (playhead to in-point) inside the modal.
  Guard against firing while focus is in a text field.

**Loop selection** matters more than it looks: judging an edit means hearing the
same three seconds ten times in a row. It is a checkbox on the `tick` function's
end-of-range branch.

**Risks:** the modal's `Space` binding must not leak to the page player, and vice
versa. Check `clipOpen()` first.

**Done when:** you can start playback, stop it, restart from the same place, and
loop the selection — without closing the modal.

#### As built

Landed as described, with three decisions worth recording:

- **"Play selection" was removed rather than kept.** The transport's play button
  *is* play-selection; keeping both would have been two controls for one job.
  Stop-then-play reproduces the old behaviour exactly. Help text updated.
- **Space no longer activates the focused button inside the modal.** It toggles
  playback. This is the trade every audio editor makes and the right one here —
  Space is pressed constantly, a given tool button once — and Enter still
  activates buttons, so nothing became unreachable from the keyboard.
- **`playRange(from, to)` accepts a null `to`**, meaning "play to the end of the
  episode". Nothing calls it that way yet; Phase 2's click-to-listen will.

**One bug found by building it.** `drawWave`'s default colours are the *dark*
palette, and `paintClip` never passed a `colors` override — so the playhead
rendered near-white (`#efece4`) on the light theme's near-white paper, i.e.
invisible. It had gone unnoticed because the playhead only ever appeared during
playback; promoting it to a permanent cursor made it a real defect. It now takes
`--ink` and was checked by screenshot in both themes. **Anything Phase 3 adds to
the waveform — the RMS body, the dB floor line — has the same trap waiting:
`waveform.js` hardcodes a dark palette that the light theme never overrides.**

**Verification.** `tests/test-waveform.mjs` still passes (15/15, untouched). A
browser smoke test drove the real editor against the live CDN and asserted
elapsed audio time rather than merely that a readout changed: playhead advances
1.42 s across 1.5 s of wall clock; pause holds the position across 2.5 s; stop
returns to the in-point; selection playback parks exactly on the out-point
(33.00 s); loop passes the out-point and comes back round while still playing.
The scripts are throwaway and were not committed — they need a browser and the
network, which is the same reason `verify-clips.mjs` is kept separate from the
pure tests.

### Phase 2 — Click to listen, and a time ruler — ✅ **built**

**Goal:** the overview becomes navigable; both views become legible in time.

**Changes**
- Overview interaction, split by target:
  - **Click anywhere** → playhead moves there and plays (this is the request).
  - **Drag inside the shaded selection band** → move the selection, as today.
    Grab cursor over the band so it is discoverable.
  This preserves the existing capability while adding the missing one. Update
  the label at [`static/index.html:1353`](../static/index.html#L1353), which
  currently promises only "drag to move the selection."
- Ruler strip on the overview: mm:ss, adaptive tick spacing by episode length.
- Ruler strip on the zoom view: adaptive to span — mm:ss above 60 s, whole
  seconds around 10 s, tenths below 2 s. This is what makes the zoom level
  legible (see A5/A7).
- Draw the rulers in `waveform.js` as an exported `drawRuler(canvas, {from, to})`
  so both views share one implementation and one tick-choosing rule.

**Risks:** low. Purely additive except for the overview mousedown split.

**Done when:** clicking the top waveform plays from that point, and you can read
your position on both views without doing arithmetic.

#### As built

**The plan's interaction model was wrong and was replaced.** "Drag inside the
shaded selection band to move it, click outside to listen" does not survive
contact with the numbers: a 3-second selection inside a 30-minute episode is
**about two pixels wide** on the overview. The drag target would have been
unhittable exactly when the selection is tightest — which is when a producer is
working hardest.

The two gestures are told apart by **distance travelled** instead. A press that
stays put (under `DRAG_SLOP`, 4 px) is a click → play from there to the end of
the episode. A press that moves is a drag → take the selection there, exactly as
before. No hit-target failure mode at any selection length, and it removes the
old behaviour where a stray click made the selection leap. A click plays to the
end of the episode rather than to the out-point, because clicking the overview
means hunting for a moment, not auditioning a cut — this is the `to = null` case
Phase 1 left ready.

**Rulers** are `drawRuler()` in `waveform.js`, shared by both views so the two
can't drift apart in style or in the rule that picks their spacing. The two
parts worth arguing about were pulled out as pure functions and tested:
`niceTick()` picks from a fixed ladder of steps that read as time (…0.5, 1, 2,
5, 10, 15, 30, 60…) rather than computing a round decimal like 2.5 s, which
would make you do arithmetic to place a mark; `tickLabel()` matches precision to
the step, showing tenths only below a 1-second step. A 55-minute episode gets
5-minute ticks; a 3-second window gets 0.2-second ticks.

**Also fixed here:** the download-size estimate rendered a perfectly good 48 KB
clip as "0.0 MB". Short clips are the *normal* case for a promo, so it now falls
back to KB below a megabyte. Noticed in a Phase 1 screenshot, not by testing.

**Carried the Phase 1 lesson:** the ruler takes its colours from `--ink-3`
rather than `drawRuler`'s dark-palette defaults, so it is legible in both themes
from the start. This is the trap the Phase 1 note warned about, and it is still
waiting for Phase 3's RMS body and dB floor line.

**Verification.** `tests/test-waveform.mjs` is now 26 checks (11 new, all pure).
In-browser: both rulers draw; the zoom ruler redraws on zoom while the episode
ruler doesn't; a click at 70% along a 29½-minute episode played from 1237.8 s
against an expected 1239 s **and left the selection untouched**; a drag moved
the selection **and started no playback**; a 3-second clip reports "47 KB". The
Phase 1 transport suite still passes unchanged.

### Audit of Phases 1–2 (before starting Phase 3)

Four defects in the work just shipped. Two were user-visible.

1. **Repeat froze its range at press time.** `playRange` captured `playTo` once,
   so turning Repeat on and then trimming an edge kept looping the range you
   started with — the precise workflow Repeat exists for. Ranges that *are* the
   selection now carry a `follow` flag and re-read `clip.in`/`clip.out` every
   frame. The auditions deliberately don't follow: they are fixed two-second
   windows onto one edge. **The Phase 1 test missed this because it only ever
   looped a static selection** — the fix came with a test that trims mid-loop.
2. **Space was swallowed on Download.** A keyboard user tabbing to the primary
   action and pressing Space got audio and no file. Controls inside
   `.modal-actions`, plus the close button, are now exempt; body tool buttons
   still yield Space to the transport.
3. **Two `getComputedStyle` calls per frame**, i.e. a forced style recalc 60×/s
   during playback. Collapsed to one read per paint.
4. **`tickLabel` broke past an hour** — 1:15:00 rendered as `72:00`. No episode
   in this archive reaches an hour, so it was correct today and wrong the moment
   it wasn't. Fixed and tested.

**"Loop selection" renamed to "Repeat".** Loop is music-studio vocabulary; this
is a talk archive, where the job is hearing one edge repeatedly while nudging
it. *Replay* was the obvious alternative and is barred — this product already
uses replay and re-air to mean putting an old episode back on the air, and two
meanings for one word inside one product is worse than a little jargon. The
function is unchanged, and fix 1 above is what makes it worth having.

### Found in use: trimming the lead handle didn't move where Play starts

Reported after Phases 1–3 landed, from actually editing with it. Play, pause
mid-selection, drag the **in** handle earlier, press Play — and it resumed from
the paused position rather than starting at the new edge, which is the one
thing you moved the handle to hear.

Play resumes from the playhead when the playhead still sits inside the range
you were listening to. That is right after a pause and wrong after a trim:
moving the in-point earlier leaves the stale playhead *technically* still
inside the range, so the resume branch won. The condition was correct for the
case it was written for and silently wrong for the one next to it.

`selectionEdited(which)` now clears the resume position — but only when the
edit actually changes where playback should start:

- **in-point moved** → always reset; the new edge is what you want to hear.
- **out-point moved** → keep a paused position that is still inside the range.
  Blanket-resetting on any edit would mean pausing to look at something,
  nudging the out handle, and being thrown back to the top.
- **whole selection moved** from the overview → treated as an in-point move.
- **while playing** → no reset; a following range already tracks the handles,
  and interrupting would fight the user.

`tickPlay` also pulls a running playhead into the range when the in-point is
dragged past it, rather than playing audio that is no longer part of the clip.

A welcome side effect: while stopped, moving the lead handle drags the playhead
cursor with it, so the transport readout always shows where Play will start.

**The lesson worth keeping.** Both this and the Repeat defect in the audit above
are the same shape — state captured at press time, then invalidated by an edit,
with a test that only exercised the static case. Anything the transport
remembers needs a test that *changes the selection underneath it*.

### Phase 3 — Detail peaks — ✅ **built**

**Goal:** you can see the silences, and see that quiet audio is not silent.
This is the phase that makes the editor genuinely usable for podcast work.

**Two tiers of peaks:**

| Tier | Resolution | Used by | Size (34 min) | Size (60 min) |
|---|---|---|---|---|
| Overview | 4,000 buckets, as today | top waveform | 32 KB | 32 KB |
| Detail | **100 pairs/sec (10 ms)** | zoom waveform, `snapToSilence` | ~1.6 MB | ~2.9 MB |

10 ms resolves breaths, plosives and inter-word gaps. Below about 20 ms you are
past where podcast editing happens, so this is the right stopping point.

**The decode does not get more expensive.** The existing decode is already at
8 kHz ([`static/waveform.js:16`](../static/waveform.js#L16)) — 8,000 samples per
second. 100 buckets/sec is 80 samples per bucket. The change is entirely in what
we *keep*, not in what we compute. Transient memory is unchanged.

**Also store RMS per bucket, alongside min/max.** Draw RMS as a solid inner body
under a lighter peak outline — the two-tone look from Audition and Audacity. Peak
describes transients; RMS describes perceived loudness, which is the judgement a
producer is actually making ("is this quiet dialogue or a loud room?"). Three
values per bucket instead of two.

**Scale the detail view in dB** (or √ as a cheaper approximation), so a −40 dB
noise floor renders as a few visible pixels rather than sub-pixel (fixes A4).
Keep the overview linear — at that scale a dB curve just looks like a solid bar.

**Draw the silence threshold as a horizontal line** on the detail view, using the
*same* threshold `snapToSilence()` searches against. This turns Snap from a
mystery button into a visible affordance: you see the floor, you see which gaps
clear it, and you can predict where the cut will land. It also makes A3's fix
self-evidently correct on screen.

**Two implementation traps, both cheap to avoid and expensive to hit:**

1. **Cache versioning.** `cacheGet()`
   ([`static/waveform.js:66`](../static/waveform.js#L66)) returns whatever is
   stored under `audio:<url>` with no schema marker. Ship a new peak format
   without one and every returning user gets old-format data read as new — a
   silently wrong waveform, which is the same class of bug as the episode-id
   caching mistake already recorded in the handoff. Add a `v:` field to the
   stored record and treat a missing or mismatched version as a cache miss.
   Bump `DB_NAME`'s version only if the store shape changes.
2. **`Array.from(peaks)` at
   [`static/waveform.js:121`](../static/waveform.js#L121)** converts the
   `Float32Array` to a plain JS array before storing. At 4,000 buckets that was
   merely wasteful; at 200,000+ it is the difference between a fast structured
   clone of a typed array and a very slow one of a boxed-number array. Store the
   `Float32Array` directly — IndexedDB's structured clone handles typed arrays
   natively.

**Also in this phase:** decouple the zoom window from the selection (fixes A5).
The window should follow the **active edge** — the handle last touched, or the
playhead — rather than being forced to contain both handles. Keep a "fit
selection" button to get the current behaviour back on demand. `clipWindow()` is
pure and already has tests, so this is a contained change with a test to update.

**Risks:** highest of any phase. It changes a persisted format, changes what
`drawWave()` receives, and changes `snapToSilence()`'s effective precision.
Do it after Phases 1–2 are shipped and stable, not alongside them.

**Done when:** at a 2-second zoom you can see the gap between two words, tell
quiet speech from room tone, and Snap lands in the gap rather than on a
half-second boundary.

#### As built

Landed as planned. Measured on a real 29½-minute episode: the zoomed waveform
went from a staircase of ~14 half-second blocks to **221 column-to-column
changes across 67 distinct heights** in 1,400 pixels. Snap moved an out-point
from `10:03.00` to `10:03.59` — off the half-second grid it had been stuck on.
Stored **100.0 buckets per second**, as `Float32Array`, under `v: 2`, with a
measured noise floor of 0.00375 (≈ −48 dB).

**Both cache traps were closed as specified**, and the versioning was verified
by seeding a v1-shaped entry (`peaks` as a plain array, no `v`) under the real
cache key and confirming the editor refuses it and re-derives.

**`noiseFloor` uses the 10th percentile, not the 15th.** The first draft used
15%, and a test fixture with 13% pause time put the floor *inside speech*. A
talk programme runs somewhere in the 10–25% range for pause time, so a
percentile at the top of that range lands in speech on the shows that pause
least. Erring low costs a conservative line; erring high marks quiet speech as
silence and invites a cut through a word.

**A floor below the dB scale's own bottom is not drawn.** It would map to zero
height and put both floor lines on the centre line — a duplicate that reads as
a rendering bug rather than information.

##### A5, and the invariant that had to go

The zoom window is no longer forced to contain the whole selection. While the
selection fits, the view frames it exactly as before; past that it follows
`anchor` — the edge you last touched, set by dragging a handle, nudging with
arrows, or snapping. A `⤢` **Fit** button reframes the selection, because
without one, getting back out would be a hunt.

**A 30-second selection can now be inspected in a 0.5-second window**, against
an old floor of 30.5 s. The `clipWindow` test that asserted "selection always
inside the window" was not a test of correct behaviour — it was the bug written
down as a guarantee. It was rewritten rather than worked around: the selection
is visible *while it fits*, and past that the anchored edge is what stays on
screen.

**The zoom label was also lying.** It reported `pad`, so it read "6.0s" while
showing a 42-second window. It reports the window now, which is the number you
need when placing a mark.

##### Known limit

The detail tier is 10 ms, so below roughly a **14-second window** (one bucket
per pixel at ~1,400 px) individual buckets become visible, and at the 0.5 s
floor they are ~28 px blocks. This is honest — every block is a real 10 ms
measurement rather than a 0.51 s average — and it is how Audacity behaves at
maximum zoom. Raising `DETAIL_RATE` to 5 ms would double per-episode storage to
~5 MB for detail nobody edits at; not worth it.

**Verification.** `tests/test-waveform.mjs` is now 40 checks. The one that
matters: at overview resolution `snapToSilence` **cannot** place a cut inside a
0.3 s gap (lands at 999.600 s, outside it); at detail resolution it lands at
1000.200 s, inside. That test fails on the old code by construction. In-browser:
the staircase measurement above, snap off the grid, cache shape and version,
stale-entry rejection, zoom to 0.5 s with the worked edge held on screen, Fit
returning to 42 s, and the Phase 1–2 suites still passing.

### Phase 4 — Marking and navigation — ✅ **built**

**Goal:** the keyboard workflow a producer already has muscle memory for.

- **`I` / `O` set in / out at the playhead.** The single biggest workflow win in
  this document, and the reason Phase 1's playhead pays for itself. This is how
  marking works in every editor anyone on this project has used.
- **Jump to next / previous silence** (`[` / `]`, or similar). With 10 ms peaks
  the silence data is good enough to navigate by, which makes finding an edit
  point a keypress instead of a hunt.
- **Zoom to selection** and **zoom to fit** as explicit buttons, now that zoom is
  decoupled from the selection.
- Keep the existing arrow-key nudge (±0.1 s, ±1 s with Shift) unchanged.

**Done when:** a producer can find, mark and trim a clip without touching the
mouse.

#### As built

`I` / `O` place the in and out points on the playhead. `[` / `]` move the
playhead to the middle of the previous / next gap — the middle rather than the
edge, because that is where a cut has the most room either side of it.
`nextSilence()` is pure and reads the RMS tier against the episode's own floor,
so it inherits the self-calibration rather than needing a threshold of its own.
It steps out of the gap it is standing in before searching, or repeated presses
would land on the same one for ever, and returns `null` past the last gap so the
caller leaves the playhead alone rather than sliding it to the end of the file.

Measured on real speech: `]` moved 601.57 → 607.61 → 608.17. That 0.56 s hop is
inter-word spacing — it is finding genuine pauses, not artefacts of the data.

**Sweeping for the bug class found a third instance.** "With 2s lead-in" played
to `clip.out` as captured at press time, so trimming the out-point mid-playback
left it stopping at the old one. It was given a third `follow` state, `"end"`,
and verified: pulling the out-point from 612 s to 603 s during a lead-in that
started at 598 s made it stop at 603.00.

**Then the button was removed entirely** — see below — and `follow` went back to
`"sel"` / `false`.

**Other loose ends closed in the same pass:**

- The Snap buttons were gated on `clip.peaks` when Snap now reads `clip.detail`.
  Same arrival time today, wrong reason.
- The episode ruler was dead to clicks. A timeline is the obvious thing to click
  when you know the time you want, and nothing happening reads as a broken
  control. It seeks now, with a crosshair cursor; the zoom ruler stays a readout
  and keeps the default cursor.
- The help still claimed the zoom keeps "the selection centred, so what you're
  adjusting never wanders off screen" — which Phase 3 made false. Rewritten,
  along with new entries for `I`/`O`, `[`/`]`, Fit, and an explanation of what
  the detailed waveform is showing (RMS body, peak outline, silence floor).

### Found in use: "With 2s lead-in" and "Audition in" were the same button

Reported from the client's own use of the editor, and correct on the numbers:

| Button | Played |
|---|---|
| With 2s lead-in | `in − 2` → **out** |
| Audition in | `in − 2` → **in + 2** |

**They began at the same instant**, so their first four seconds were always
identical, and they diverged only once the selection ran past two seconds. On a
three-second promo clip — the normal case for this tool — one played five
seconds and the other four, sharing the first four. Two buttons, one behaviour.

The fault was that the lead-in never had a job of its own. The real jobs are:
hear what will be exported (**Play**), judge the in cut (**Audition in**), judge
the out cut (**Audition out**). "Lead-in" was "Audition in, then keep going" —
Play with a run-up, not a fourth kind of listening. That it was also the only
control needing a bespoke `follow` state was the tell.

Removed: the button, its handler, its help entry, and the `"end"` state it was
the sole user of. Leaving a `follow` value with no caller would have sent the
next reader hunting for one; the reason it briefly existed is recorded in a
comment at `playRange` instead. The Audition help was rewritten too, since it
had been leaning on the lead-in's entry to explain hearing the approach to an
edit.

What is left under the zoomed view is four controls with four distinct jobs:
Audition in, Audition out, Snap in, Snap out — with Play in the transport above.

**Verified after removal:** Audition in still runs 598 → 602.00 on a selection
whose out-point is 630, i.e. it kept its own short window rather than inheriting
Play's; Play from the same in-point runs on past 605 and keeps going.

### Phase 5 — Verification

Extend `tests/test-waveform.mjs`, which is already pure and browser-free:

- `reducePeaks` at the detail resolution produces the expected bucket count for
  a range of durations.
- RMS is computed correctly against a known signal.
- `snapToSilence` finds a synthetic 0.3 s gap between two tones — **this test
  fails today** and is the clean regression proof for A2/A3.
- `clipWindow` under active-edge mode keeps the edge on screen at every zoom
  level, as the current test does for both handles.
- Cache version mismatch is treated as a miss.

`tests/verify-clips.mjs` covers the export path and should keep passing
untouched throughout. If it ever fails during this work, something has reached
into the cutting code that should not have.

#### As built — ✅ done, but not as a phase

Every item above was written alongside the phase that needed it rather than
saved for the end, which is why the `snapToSilence` gap test could be written as
a genuine before/after rather than retrofitted. `tests/test-waveform.mjs` is now
**49 pure checks**, still browser-free and network-free.

`tests/verify-clips.mjs` was not touched and its code path was not reached: no
change in Phases 1–4 goes anywhere near `mp3cut.js`. Worth running before any
commit all the same, since that is the check that the exported bytes are still
the broadcast audio.

##### The browser suites

These need Chrome, a running server and the network, so they live outside
`tests/` for the same reason `verify-clips.mjs` is kept apart from the pure
tests. They were driven with Playwright against the real Podbean CDN. They are
**not committed** — they are recorded here so the coverage is known and can be
rebuilt:

| Suite | Proves |
|---|---|
| transport | playback advances 1.42 s in 1.5 s of wall clock; pause holds across 2.5 s; stop parks on the in-point; selection playback stops exactly on the out-point; Repeat wraps and keeps running |
| audit fixes | Repeat follows a trim made mid-loop; Space is exempt on the commit/discard controls |
| Phase 2 | both rulers draw; zoom ruler redraws on zoom and the episode ruler doesn't; a click listens without moving the selection; a drag moves the selection without starting playback |
| Phase 3 | 221 column-to-column changes across 67 distinct heights on a real episode; snap off the half-second grid; cache shape, version and typed arrays; a v1-shaped entry is refused and re-derived |
| zoom | a 30 s selection zooms to a 0.5 s window with the worked edge held on screen; Fit reframes |
| lead-handle | the reported bug: Play starts at a moved in-point, not the stale playhead; moving the out-point preserves a paused position |
| Phase 4 | `I`/`O` land exactly on the playhead; `[`/`]` advance and reverse through real pauses; the lead-in stops at a mid-playback-trimmed out-point; the ruler seeks |

**The one thing these suites structurally cannot catch** is what the client
found in two minutes of real editing: state captured at press time and
invalidated by a later edit. Three bugs of that exact shape shipped from this
file — Repeat, Play-after-moving-the-lead-handle, and the lead-in — and only the
first was caught by a test written by the person who wrote the code. Hands on
the actual editor remain the better detector for that class.

---

## Phase 6 — Show that a momentary action is momentary (not started)

Reported from live use, 9 August 2026.

**The problem.** Audition in / Audition out play a fixed two seconds and stop on
their own. Nothing on screen says that is what will happen, and nothing marks
that it is happening. A play button that stops by itself is unusual — most keep
going until you stop them — so the silence afterwards reads as ambiguous: did it
finish, did it fail, did I mis-click? The user is left unsure what happened.

**The fix.** Light the button while its own playback is running and un-light it
when that playback ends. Seeing the highlight come on and go off *teaches* the
behaviour in one press: this button plays a segment and returns. No text needed.

**Notes for whoever picks it up:**

- `.tool.on` already exists — Repeat uses it. Reuse it rather than inventing a
  second "active" style, so "lit" means one thing across the editor.
- The transport needs to know *which* control started the current playback.
  `playRange` currently records `playFrom` / `playTo` / `follow`; add the
  originating element (or a small id) alongside them, and have `setPlaying`
  light and clear it. Do not track it in the click handlers — that is the
  press-time-capture shape that has already produced three bugs in this file.
- Clearing must be handled on **every** exit: natural end in `tickPlay`, `stop`,
  `pause`, a different control taking over, and `closeClip`. The failure mode is
  a button left lit after the audio stops, which is worse than no indicator.
- Same treatment applies to Snap in / Snap out, which are also momentary but
  have no feedback at all — the mark moves and that is the only signal. A brief
  flash of the same highlight would make the two families read alike. Worth
  doing in the same pass; consider whether Snap should also be *audible* (it
  currently changes a cut point without ever playing it).
- Play/pause in the transport is **not** in this family — it is a mode, not a
  momentary action, and already shows its state through the ▶/❚❚ glyph.
- Verification is a browser check: click Audition in, assert the button carries
  `.on` while `#tPlay` reads "Pause", then assert `.on` is gone once it reads
  "Play" again. Poll for the condition rather than sleeping — fixed sleeps
  against the CDN produced several false failures during Phases 1–4.

## Brainstorm — features for LHF and the labor podcast network

Not planned, not costed, not committed. Captured so the phase plan above can be
judged against where this is going.

Worth holding in mind who these users are (from the handoff): they are **podcast
producers**, **FM broadcasters** on WPFW 89.3, and **labor history researchers**,
often the same person in one afternoon. The broadcast hat has the hardest
constraints and is the easiest to forget.

### Directly on top of the editing surface

- **Clip bin.** Collect several clips in one session, export together. Building a
  promo means pulling three or four quotes, and today that is three or four
  separate trips through the modal.
- **Exact-duration trim.** "Make this exactly 3:00" — hold the in-point, move the
  out-point to hit a target length, then snap to the nearest silence within
  tolerance. Broadcast slots are exact; this is the fill-a-hole problem stated
  precisely.
- **Run sheet.** Sequence selected clips, show cumulative duration against a
  target. Already a seed in the handoff. Nothing on the market does this for
  podcast archives, and it is the feature most specific to who they are.
- **Loudness readout.** An approximate integrated LUFS from the 8 kHz decode we
  already perform. Not a mastering tool — just enough to say "this clip is 6 dB
  quieter than the last one," which is the failure mode when clips from different
  episodes land in one segment.
- **Trim by word.** Show the transcript under the waveform, aligned to the
  selection. The `segments` table already carries millisecond timestamps for 144
  episodes. Select text → in/out set from segment bounds → fine-trim on the
  waveform. This is the Descript workflow they already know, and it is the merge
  of this document with `docs/transcript-modal.md`.
- **Out-cue text.** Broadcast run sheets need the last words spoken — "…and
  that's why we marched." Generate it from the transcript at the out-point. The
  data is already there; this is string slicing.
- **Clip captions.** Export an SRT alongside the MP3, with segment timestamps
  rebased to zero. Social platforms want captions, and this costs a subtraction.
- **Named clips saved as citations.** `?ep=&from=&to=` already makes a moment
  shareable. Saving one with a title turns a clip from a file in a downloads
  folder into a catalogue entry — which is what the Library of Congress people in
  their organisation will actually want.

### Network scale — the Labor Radio Podcast Network

LHF runs two shows; the network around them is on the order of two hundred. The
ingest path keys on `<guid>` and is already feed-agnostic, so most of this is
configuration rather than architecture.

- **Point the pipeline at more feeds.** The single highest-leverage move
  available, and it needs no new code — only a decision about scope and hosting.
- **Cross-network search.** "Who has covered the Amazon campaign?" across two
  hundred shows is a genuinely new thing in this space, and it is the same search
  box already built.
- **A shared clip library.** "Best moments from labor podcasts this month" is an
  editorial product, not a feature — but it falls straight out of the clip bin
  plus saved citations.
- **Audiograms.** Waveform video for social is the most-requested podcast promo
  artifact there is, and we already have peaks and a canvas. In-browser MP4 is
  heavy, but canvas + `MediaRecorder` → WebM is plausible. Ambitious; listed
  because the raw materials are already on the page.

### Explicitly parked

- **Fades, normalise, gain.** All require re-encoding and forfeit the
  bit-identical guarantee. See the constraints section. This is a conversation
  with the client, not a ticket.
- **Multi-track or crossfade editing.** Out of scope by an order of magnitude.
  If they need it, they have Descript, and Descript is better at it.

---

## Reading order for whoever picks this up

1. `docs/audio-editor-spec.md` — what exists and why the export is the way it is.
2. This document's audit section — what is wrong with the editing surface.
3. Phase 1. Do not start anywhere else; the playhead is underneath everything.
