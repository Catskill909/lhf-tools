# Audio clip editor — specification

**Status:** **built and verified** (Phases 1–5). Supersedes the earlier WAV-based draft.

> **Scope note (9 August 2026).** Everything here about *export* — frame copy,
> bitrate probing, cut accuracy — is current and unchanged; it is the part that
> matters most and the part `tests/verify-clips.mjs` still proves on every run.
>
> The *editing surface* described below has since been rebuilt across four
> phases: a real transport, time rulers, click-to-listen, 10 ms detail peaks
> with RMS and a visible silence floor, zoom decoupled from the selection, and
> keyboard marking. Where this document and **`docs/audio-editor-dev.md`**
> disagree about the interface, the dev doc is right. The mock-up and the
> individual decisions that no longer hold are marked inline below. The build
> phases at the end are left as the historical record they are — don't
> implement from them.

Find a moment by search, adjust the in/out points against the episode waveform,
export an MP3 clip. Entirely in the browser; **our server does nothing** — audio
streams from Podbean's CDN direct to the user.

---

## The measurements everything rests on

Taken from real episodes, not assumed:

| | |
|---|---|
| Episode | 55 min (3,300 s) |
| File | **75.5 MB** at 192 kbps |
| Format | **mono, CBR** (sampled at 10/30/50/90% — identical) |
| Frame | 626–627 bytes at 192 kbps, **1,152 samples, 26.12 ms** |
| Rate | **bitrate × 1000 / 8** bytes/sec — exact at CBR |

Verified by walking 200 consecutive frames, chaining each to the next by its
own length header. That proves the frame maths is exact — which is what makes
everything below possible.

### The bitrate is not constant across the archive

The first draft of this spec hardcoded 24,000 bytes/sec from a single Power
Hour episode. **That was wrong, and it broke on real data.** Sampling both
shows found **128, 192 and 256 kbps** files. Every file is internally CBR, but
the rate differs episode to episode.

A hardcoded rate computes a byte offset past the end of a smaller file — the
server answers `416 Range Not Satisfiable` and the clip fails outright. On a
larger file it silently lands in the wrong place, which is worse.

So `probeMp3()` measures each file before cutting: it reads the ID3v2 tag
length to find where audio actually begins, then reads the first frame header
for the real bitrate. Two small range requests, cached per episode.

**The ID3 offset matters too.** Cover art can push the first frame a hundred
kilobytes in; treating byte 0 as time 0 would put every cut four seconds early.

---

## Export: copy frames, don't re-encode

You're right that WAV made no sense from an MP3 source. But the better answer
isn't re-encoding to MP3 either — it's **not encoding at all**.

MP3 is a sequence of independent frames. A clip is just *the frames between two
timestamps, copied out byte-for-byte*, with a fresh ID3 tag on the front.

| Approach | Quality | Speed | Code |
|---|---|---|---|
| **Frame copy** | **Bit-identical to source** | Instant — it's a byte copy | ~80 lines, no library |
| Decode → `lamejs` re-encode | Second-generation loss | Slow (seconds to minutes) | +200 KB library |
| Server-side `ffmpeg` | Clean | Fast | Contradicts the light-server goal |

**Frame copy wins on every axis.** No quality loss matters here: these are
already-lossy 192 kbps files, and re-encoding would audibly soften a clip
destined for broadcast.

**Cut accuracy is one frame — 26 ms.** Inaudible in speech; you cannot hear a
26 ms shift in a cut point. Precise enough that nobody will ever notice, and
it's the same granularity mp3splt and similar tools use.

**Output size:** a 2-minute clip is **2.9 MB** — versus 21 MB as WAV.

```
export(inSec, outSec):
  byteFrom = inSec  * 24000        # exact at CBR
  byteTo   = outSec * 24000
  fetch Range: bytes=(byteFrom-4000)-(byteTo+4000)   # pad for frame alignment
  scan forward to first frame sync
  copy whole frames until cumulative duration >= (outSec - inSec)
  prepend ID3v2 (title, episode, timestamp, source URL)
  Blob -> download
```

**The pad-and-scan is load-bearing.** Frames don't align to the byte offsets we
compute, and the first frame in a slice is usually partial. Always scan to a
real sync and accumulate whole frames.

---

## Waveform: decode low, display only

Display is the only thing that needs decoding, and it doesn't need fidelity.

| Decode target | Memory | |
|---|---|---|
| Full episode @ 44.1 kHz | 555 MB | ❌ |
| **Full episode @ 8 kHz** | **101 MB** | ✅ transient, then discarded |

Fetch the 75 MB once, decode through an `OfflineAudioContext` at 8 kHz, reduce
to ~4,000 min/max peak pairs, throw the audio away. Cache the peaks in
IndexedDB so re-opening is instant.

**Waveform, not spectrogram** — amplitude over time is what you select against;
you can see where a sentence starts and where the gaps are. A spectrogram shows
frequency and tells you nothing about where to cut.

---

## Integration audit — what already exists

Most of the scaffolding is built:

| Needed | Status |
|---|---|
| Modal shell (focus trap, `Esc`, backdrop) | ✅ Help and Export both use it — third instance |
| Audio transport (play/pause, seek, keyboard) | ✅ `buildPlayer()` in `static/index.html` |
| `start_sec` / `end_sec` per passage | ✅ `segments`, surfaced as `moments` in search |
| `audio_url` per episode | ✅ in the API response |
| CORS + range requests on the audio | ✅ verified `Access-Control-Allow-Origin: *`, `HTTP 206` |
| Design tokens, button/dialog styles | ✅ reuse as-is |
| **MP3 frame parser** | ✅ `static/mp3cut.js` |
| **Peak extraction + canvas waveform** | ✅ `static/waveform.js` |
| **Drag handles** | ✅ in the clip modal |

Nothing existing had to change. This was additive: a new modal opened from a
button on each moment. Two small server changes came with it — `serve.py` now
serves `.js` files (the UI was a single file until this point) and exposes
`/api/episode/<id>` for shared moment links.

### Library: build it, don't import it

The earlier draft recommended wavesurfer.js. **Reversing that.** Now that
export needs no decoding, our actual needs are narrow — draw peaks, two drag
handles, a playhead — perhaps 150 lines of canvas. wavesurfer is ~100 KB,
brings its own visual language we'd be fighting to match the letterpress design,
and expects to own the audio loading we're deliberately doing ourselves.

Keep wavesurfer as the fallback if the canvas work overruns.

---

## The interface — built for podcast production

```
┌─ Clip ─────────────────────────────────────────────────────┐
│  Striking At Kings (Encore) · Power Hour · 30 Jul 2026      │
│                                                             │
│  whole episode                                              │
│  ▁▂▄█▆▃▁▁▂▅█▇▄▂▁▃▆█▅▂▁▁▂▄▇█▅▃▁▂▄▆█▆▄▂▁▁▃▅█▇▄▂▁▂▄▆█▅▂▁      │
│              └────┘  ← selection, drag to move              │
│                                                             │
│  selection (zoomed)                                         │
│  ▁▂▅█▇▃▁ ▁▂▄▆█▅▂▁ ▁▃▆█▄▂▁▁▂▅█▇▄▂▁▁▂▄▇█▅▃▁▂▄▆█▆▄▂▁          │
│  ⟨                                              ⟩           │
│                                                             │
│  IN  8:42.31   OUT  9:15.80          LENGTH  33.5s          │
│  ⟨ ⟩ nudge 0.1s     ⌥⟨ ⟩ snap to silence                    │
│                                                             │
│  ▶ Hear the start  ▶ Hear the end  Snap in  Snap out        │
│  (superseded: play/pause, back-to-start and Repeat now      │
│   sit in a transport between the two waveforms, each        │
│   of which has a time ruler — see the dev doc)              │
│                                                             │
│                     [ Cancel ]  [ Download MP3 · 2.9 MB ]   │
└─────────────────────────────────────────────────────────────┘
```

Two waveforms — the whole episode for context, and a zoomed view of the
selection for precision. That pairing is what every editor uses, and it's the
difference between "roughly there" and "on the word."

**Decisions aimed at production work, not general audio editing:**

- **The entry point is the player, not the text.** A clip button on every
  timestamp was tried first and was wrong: it stretched the full width of the
  results column, competed with the excerpt it sat next to, and didn't read as
  an edit control. A scissors icon at the right-hand end of the transport is
  where a producer already is once they've found the spot. It seeds from the
  passage that opened the player, or from wherever they scrubbed to.
- ~~**Zoom keeps the selection centred.**~~ **Reversed.** The window was always
  wide enough to hold the whole selection plus context, so both handles stayed
  grabbable at any zoom level — and that made frame-level work impossible: with
  a 30-second selection the tightest view was 30.5 seconds. Detail work happens
  at one edge at a time, which the auditions below already assume. The window
  now frames the selection while it fits and follows the edge you last touched
  past that. The test that asserted the old invariant was rewritten, not worked
  around. See `docs/audio-editor-dev.md`, A5.
- **Snap to silence.** The single most useful aid. We already have the peak
  data — find the nearest local minimum and put the cut there. (It was later
  found to be quantised to a half-second grid by the overview's resolution, and
  so unable to reach the gap it was hunting for; it now reads the 10 ms tier.) A clean cut
  lands in the gap between words; a cut mid-syllable sounds broken. One
  keystroke.
- ~~**Play with lead-in**~~ — **removed.** It started at the same instant as
  *Audition in* (`in − 2`), so the two were identical for their first four
  seconds and indistinguishable on the short clips this tool is mostly used
  for. Play plus the two auditions cover the same ground. See
  `docs/audio-editor-dev.md`.
- ~~**Audition in / audition out** — two seconds either side of one cut point.~~
  **Reversed.** Straddling the mark meant *Audition out* played two full seconds
  of episode after the clip had stopped — material the listener never receives —
  and the fixed window overshot both marks on any selection shorter than it, so
  on a short promo the two buttons played nearly the same audio. That is the
  same flaw the lead-in button was deleted for, left in place in the two buttons
  that stayed. They are now **Hear the start / Hear the end**: the clip's own
  first and last three seconds, clamped to the selection at both ends. Edits are
  still usually wrong at one edge and checking one shouldn't mean sitting
  through the whole clip — but what you hear is now what the listener gets. See
  `docs/audio-editor-dev.md`.
- **Length shown prominently.** These people fill broadcast slots. "How long is
  it" is the question, not "where does it end."
- **Nudge ±0.1 s** by arrow key. Dragging can't hit a word boundary.
- **Filename carries provenance** — `LHPH_2026-07-30_Striking-At-Kings_0842-0915.mp3`
  — so a clip sitting in a folder three months later still says where it came
  from.
- **ID3 tags written on export** — title, source episode, timestamp, URL. Same
  reason.
- **Deliberately no** fades, gain, multi-region, or effects. That's Descript's
  job, and this is a *find-and-extract* tool, not an editor.

---

## Phases

**Phase 1 — Frame cutter** ✅ *(`static/mp3cut.js`)*
The load-bearing piece. Range-fetch a byte span, scan to a frame sync, copy
whole frames, write ID3, download. Verify the output plays in QuickTime, VLC and
a browser, and that its duration matches the request. Prove this before building
anything on top of it.

**Phase 2 — Peaks + waveform** ✅ *(`static/waveform.js`)*
Fetch, decode at 8 kHz through `OfflineAudioContext`, reduce to peaks, cache in
IndexedDB, render to canvas. Both views — full episode and zoomed selection.
Watch first-open time on a real connection; 75 MB is not instant.

**Phase 3 — Selection** ✅
Draggable handles, numeric readout, nudge keys, play-selection and play-with-
lead-in. Pre-seed the selection from the search passage's `start_sec`/`end_sec`.

**Phase 4 — Wire it in** ✅
A "Clip" button on each moment in a search result. Modal reuses the existing
shell. Filename and ID3 from episode metadata.

**Phase 5 — Snap to silence** ✅
Local-minimum search in the peak array. Small, and the thing producers will
actually thank you for.

**The risk was called correctly, and it landed in Phase 2.** Cutting was never
the problem; the waveform is. A clip needs ~0.5 MB, but drawing the waveform
needs the whole 30–105 MB file.

Rather than fall back to a coarse overview, the modal was made **usable without
the waveform**: in/out times, nudge keys, playback and download all work from
the moment it opens, and the waveform fills in when it arrives. Peaks are then
cached in IndexedDB, so an episode is only ever downloaded once. Closing the
modal aborts the download.

The sampled-range fallback remains available if first-open time disappoints on
a slow connection.

---

## Shareable links — built

`?ep=123&from=522&to=549` opens the clip editor on that episode with the passage
already selected. Every search is also reflected in the address bar
(`?q=picket+line&show=1&sort=oldest`), so a result set can be sent to a
colleague as-is.

That second form is the **external integration point from the original brief**:
laborheritage.org can put a search box on its own page and link straight in with
`?q=`, no API work required.


---

## Verification

Tested against live episodes, not fixtures.

**Cut accuracy.** Four random episodes, cut at ~15 minutes in:

```
192kbps  asked 927.20s  landed 927.22s  off by 0.019s
192kbps  asked 992.38s  landed 992.39s  off by 0.012s
128kbps  asked 945.75s  landed 945.76s  off by 0.008s
192kbps  asked 964.42s  landed 964.44s  off by 0.022s
```

Every clip is off by **less than one frame (26 ms)**, at two different
bitrates. Position was proved by searching the source file for the clip's bytes
and finding an **exact byte match** at the expected offset — which confirms
both that the cut lands where it should *and* that it is genuinely lossless.

**Playability.** `afinfo` reports every output as a valid `MPG3`, 1 channel,
44100 Hz, with a duration matching the request and the source bitrate preserved
(the 128 kbps source produced a 128 kbps clip, not a re-encode).

**The app.** Loaded in headless Chrome with no console errors. `?q=picket+line`
renders 86 results, 156 moments, 156 Clip buttons and 523 highlights.
`?ep=12&from=605.5&to=633.25` opens the editor reading
`10:05.50 / 10:33.25 / 27.8s` — correct, and displayed *before* the waveform
downloads.
