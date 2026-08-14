# Touch support — exploratory audit and phased plan

**Status:** Phases 1–3 built locally 14 August 2026. The touch, keyboard,
layout, theme, waveform, clip-store, update-prompt and ingest regressions pass.
**Phase 4 is open: Paul will verify the producer workflow on a real iPad before
this is called shipped.**

**Scope assumption:** “touch” means operating the existing web app on a
touchscreen. The remaining real-device verification is tracked in the task box
in `HANDOFF.md`; the completed reasoning stays here.

---

## Decision

The app does **not** need a general mobile redesign. Its ordinary archive
workflows are already broadly touch-operable: search, filter chips, result
links, moment playback, transcripts, export, help and form controls are native
inputs/buttons driven by `click`. The responsive result layout and long-text
overflow protections are also already doing real work on a phone.

The audio editor was the exception and therefore owns the touch project. It was
a desktop mouse-and-keyboard editor rendered inside a responsive-looking modal.
Phases 1–3 now wire that same editor to touch without creating a second gesture
implementation; real hardware decides whether the work is complete.

The support boundary is therefore:

- **Phones / compact windows below 768 CSS px:** archive functions remain
  available, but audio editing shows a clear tablet-or-computer requirement.
- **Tablets and larger touchscreens from 768 CSS px:** target for the complete
  audio editor, in portrait and landscape.
- **Mouse and keyboard:** must keep every current editor behavior and shortcut.

The boundary is based on available viewport space rather than user-agent
sniffing. A coarse-pointer phone in a short landscape viewport gets the same
warning.

## Implementation status

| Phase | State | Evidence |
|---|---|---|
| 1 — Pointer input foundation | ✅ built locally | One pointer lifecycle, capture, cancel/lost-capture cleanup; no mouse-only editor gesture bindings |
| 2 — Tablet geometry | ✅ built locally | 44px touch targets, split handle hit areas, wrapping footer, dynamic viewport and safe-area rules |
| 3 — Touch feedback | ✅ built locally | Coarse-pointer instructions, pressed waveform/handle states, touch-sized controls |
| 4 — Real devices | ❓ awaiting Paul | iPad portrait/landscape producer journey first; Android/Windows follow before a broad support claim |

Nothing here changes the frame-copy MP3 export, waveform cache format, audio
source or server boundary. These are interaction and layout changes only.

## What was examined

- Responsive CSS, modal sizing, target geometry and hover-only states in
  `static/index.html`.
- Every mouse, click, wheel, keyboard and selection handler in the front end.
- The waveform state helpers and the existing keyboard, overflow, palette,
  hidden-state and waveform tests.
- A compact headless-Chrome render of the archive and a deep-linked audio edit
  (`?ep=101&from=30&to=60`). Chrome produced a 390 × 844 bitmap but reported a
  **500 × 757 CSS viewport**—its headless minimum—so the crop was used only to
  expose desktop assumptions, not represented as a real 390px device test.
  Actual iOS and Android hardware remains part of the release phase.

## Original audit findings

This section records what justified the work. Phases 1–3 close the
touch-specific findings in code; Phase 4 decides whether they are closed on
real hardware.

### The blocker was mouse-only editor gestures

The audio editor had no Pointer Events, pointer capture or `touch-action`
policy. Its interaction model used `mousedown` followed by window-level
`mousemove` / `mouseup`:

- drag either in/out handle;
- tap or drag the whole-episode overview;
- tap or drag the zoomed waveform to place the playhead or make a selection;
- tap or drag either time ruler;
- scrub the ordinary inline player.

A touchscreen-generated `click` reached normal buttons, so Play, Repeat, Snap,
Save and Download could fire. It did not make the editor's press/drag surfaces
work. The central job—setting and trimming a range—was therefore unavailable.

**As built:** handles, both rulers, both waveforms and the inline player scrubber
now use Pointer Events. A shared editor lifecycle accepts only the primary
pointer, captures it, and sends `pointerup`, `pointercancel`, lost capture and
modal close through cleanup. Touch uses a 10px click/drag threshold; mouse and
pen retain the tighter 4px behavior.

### The phone editor does not fit

The compact geometry cannot honestly support the current editor. Its modal asks
for 97vw while sitting inside a backdrop with another 2rem of horizontal
padding; its footer does not wrap; and the header, zoom group, Repeat, selection
values and three footer actions all compete on single rows. Before any finger
target expansion, the interface has no compact layout in which every essential
control can remain exposed.

That evidence is why the phone message is a support boundary rather than a
soft “best experienced on desktop” hint. Showing the editor would promise a
workflow the screen cannot expose.

### Precision targets were too small for a finger

The visible in/out line was backed by an **11px-wide** handle. Zoom buttons were
22px, the inline player Edit button was 30px, its Play button was 32px, and the
editor's secondary transport button was 38px. Only the primary editor Play and
search Clear controls reached 44px.

**As built:** on a touch-capable tablet, the interactive handle box is 44px
while its visible line stays 3px. The in handle owns the upper half of the
waveform and out owns the lower half, so overlapping handles remain separately
reachable. Zoom, transport, player and modal-action targets also reach 44px.

### Touch needed explicit scroll/drag arbitration

The editor body scrolls vertically and its waveforms drag horizontally. Without
a scoped `touch-action` policy, the browser may interpret the same movement as
page panning, text selection or browser navigation. Disabling touch behavior on
the entire modal would also be wrong because the user still needs vertical
scrolling and pinch zoom outside the editing strips.

**As built:** rulers and waveforms use `touch-action: pan-y`, retaining vertical
modal scrolling while the app owns horizontal editing gestures. Handles use
`touch-action: none`. A vertical touch movement is not turned into an edit;
mouse and pen retain the original drag behavior. A cancelled pointer clears
capture, feedback and the frozen zoom window.

### The copy taught desktop behavior

The modal and Help described “click,” “drag,” “scroll wheel,” `I`, `O`, brackets,
Space and arrow-key nudge. The modal now swaps to tap/sideways-drag instructions
when any coarse pointer is present. Help and the client guide say click or tap;
keyboard help remains for desktop and keyboard-equipped tablets.

### Non-editor functions are usable, not yet device-certified

The audit did not find another touch blocker on the scale of the editor.
Ordinary buttons use `click`, inputs are native, dialogs have reachable close
controls, and the result grid collapses at phone width. The hover-disclosure
pass is also built: transcript Edit on tablets, the player scrubber knob,
clip-label remove, “+ label” and clip-row actions are visible and finger-sized
on touch; their hover-only versions are gated to devices that genuinely hover.
This prevents iPad from spending the first tap revealing a control instead of
playing transcript audio or opening Edit. On phones, transcript audio-editing
routes are deliberately absent; the compact transcript surface below replaces
them with more room to read. Tightly packed filter groups still deserve a
physical-phone overflow pass, but do not prevent the primary archive journey.

### Phone transcript reading surface — built locally

The real-phone pass exposed a second, narrower problem rather than a reason to
bring back the waveform editor. At 390px, the transcript modal stacked a large
title, three option rows, player, always-visible passage-selection lesson and
download footer around a very small scrolling area. Its Edit button also took a
third column from every passage even though the destination editor is guarded
on phones.

Below 768px—or on a short coarse-pointer landscape screen—the transcript now
becomes a focused **find, listen and read** surface. It is edge-to-edge and
dynamic-viewport-height; title and metadata are clamped, search and match
navigation remain 44px, and the compact player stays above the independently
scrolling prose. Timestamps and Follow audio keep their useful defaults without
occupying rows. Matches only appears only after a query, when it has a job.
Per-line Edit, the player scissors, selection lesson and export footer are
withheld. Native text selection and copy still work.

A Chrome mobile/touch render at 390×844 measured 642px of transcript scroll
area—76% of the viewport—with all four phone-inappropriate editing surfaces
confirmed hidden. Real Safari remains the release authority for address-bar,
safe-area and audio-policy behavior.

## Phone guard — built in this audit

On a viewport below 768px, or a short landscape viewport with a coarse pointer,
opening the editor now shows only:

- the episode heading;
- a 44px close control;
- “Audio editing needs a larger screen” and a tablet/computer instruction.

The waveforms and action footer are hidden at that size. This avoids clipped
controls and avoids inviting the user into a precision editor that does not fit.
The rest of the app stays available behind the modal.

## Implementation phases

### Phase 1 — one pointer input foundation — built locally

Replace editor `mousedown` / `mousemove` / `mouseup` paths with Pointer Events,
not parallel mouse and touch implementations.

The shared interaction layer should:

- accept the primary pointer only and ignore accidental multi-touch;
- use pointer capture so a finger may leave a narrow surface mid-drag;
- handle `pointerup`, `pointercancel` and lost capture through one cleanup path;
- preserve the existing frozen-window, one-undo-per-gesture and focus-transfer
  rules;
- preserve synthesized click behavior on ordinary buttons;
- give waveform/ruler surfaces scoped horizontal gesture ownership while
  retaining vertical modal scrolling.

**Current evidence:** the static suite rejects mouse-only editor gesture
bindings and requires capture plus all cancellation paths. Keyboard regressions
pass. The behavioral half of acceptance moves to the real-iPad run.

### Phase 2 — tablet geometry and controls — built locally

Make 768px portrait the minimum full-editor layout:

- expand handle hitboxes to at least 44px without thickening the 3px marks;
- make zoom, transport and trimming tools comfortable finger targets;
- let the footer wrap without hiding Save or Download;
- use dynamic viewport units and safe-area padding where modal chrome meets the
  screen edge;
- keep both waveforms large enough to read in portrait and landscape;
- keep the editor close control and current-time/selection values visible at
  every supported size.

**Current evidence:** structural tests enforce the 768px boundary, 44px targets,
thin visual handles, footer wrapping, safe-area placement and dynamic viewport
height. A 768px fine-pointer browser render has no horizontal overflow and keeps
every editor control visible. Portrait/landscape coarse-pointer behavior remains
an iPad check because headless Chrome cannot emulate that media query reliably.

### Phase 3 — touch-first editor feedback — built locally

Keep the present editor semantics, but teach them in touch language:

- tap overview → listen from that point;
- drag overview → move the selection;
- tap zoomed waveform → place the playhead;
- drag zoomed waveform → make a selection;
- drag a handle → trim one edge;
- use visible buttons for zoom, audition, snap, repeat, save and download.

Add an active/pressed state that remains visible under a finger, enlarge the
effective handle on the side being touched, and switch the inline instructions
from “click” to “tap” for coarse pointers. Pinch-to-zoom is deliberately not a
Phase 3 requirement; the explicit zoom controls are predictable and already
part of the editor.

**Current evidence:** coarse-pointer copy and active press states are present;
the full first-time producer journey is the central iPad acceptance test.

### Phase 4 — device validation and release boundary — open

Run the end-to-end producer journey on real hardware:

| Device class | Minimum checks |
|---|---|
| iPadOS, 768px portrait + landscape | drag arbitration, audio start, rotation, download |
| Android tablet, roughly 800px+ | pointer capture, scroll, audio start, download |
| Windows touch laptop | touch followed by mouse/trackpad, no duplicate events |
| Desktop Chrome + Safari | all current mouse and keyboard editor behavior |
| Phone portrait + landscape | guard always appears; close works; archive remains usable |

Also test a pointer cancellation, rotation during loading, closing during a
drag, changing a selection while Repeat is running, and returning from the Save
dialogue. Those state transitions match the editor's recurring shipped bug
class more closely than a static happy-path test does.

**Release boundary:** claim “tablet touch support” only after the first three
hardware rows pass. Keep the phone guard until a separate compact editor is
designed and tested; pointer-event support alone does not make the phone layout
viable.

## Test strategy as built

The production app remains dependency-free. Tests follow the existing split:

- `tests/test-touch.mjs` has 34 structural checks: phone editor boundary,
  compact phone transcript, Pointer Events, capture/cancellation, scoped
  `touch-action`, 44px geometry, touch instructions and tap-safe hover
  disclosure;
- a rebuildable browser/device checklist for actual pointer capture, canvas
  geometry, audio policies and downloads;
- the existing waveform, keyboard, hidden-state, overflow and palette suites as
  regressions.

Browser emulation is useful during development but cannot certify native text
selection, audio gesture policy, file downloads, safe areas or finger accuracy.
Those stay in the real-device phase.

## Explicitly outside this plan

- A phone-sized waveform editor.
- Pinch zoom or two-finger editing gestures.
- Re-encoding, fades, gain or any change to frame-for-frame MP3 export.
- Moving audio or peaks through the server.
- Redesigning archive search, export or the clip library unless hardware testing
  exposes an actual blocker. The phone transcript exception above exists
  because real-device testing did expose one.
