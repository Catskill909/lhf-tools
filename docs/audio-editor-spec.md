# Audio clip editor — specification

**Status:** specced, not built. Supersedes the earlier WAV-based draft.

Find a moment by search, adjust the in/out points against the episode waveform,
export an MP3 clip. Entirely in the browser; **our server does nothing** — audio
streams from Podbean's CDN direct to the user.

---

## The measurements everything rests on

Taken from a real episode, not assumed:

| | |
|---|---|
| Episode | 55 min (3,300 s) |
| File | **75.5 MB** |
| Format | **192 kbps mono, CBR** (sampled at 10/30/50/90% — identical) |
| Frame | 626–627 bytes, **1,152 samples, 26.12 ms** |
| Rate | exactly **24,000 bytes/sec** |

Verified by walking 200 consecutive frames, chaining each to the next by its
own length header. That proves the frame maths is exact — which is what makes
everything below possible.

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
| **MP3 frame parser** | ❌ build (~80 lines) |
| **Peak extraction + canvas waveform** | ❌ build (~150 lines) |
| **Drag handles** | ❌ build |

Nothing existing has to change. This is additive: a new modal, opened from a
button on each moment.

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
│  ▶ Play selection    ▶ Play with 2s lead-in                 │
│                                                             │
│                     [ Cancel ]  [ Download MP3 · 2.9 MB ]   │
└─────────────────────────────────────────────────────────────┘
```

Two waveforms — the whole episode for context, and a zoomed view of the
selection for precision. That pairing is what every editor uses, and it's the
difference between "roughly there" and "on the word."

**Decisions aimed at production work, not general audio editing:**

- **Snap to silence.** The single most useful aid. We already have the peak
  data — find the nearest local minimum and put the cut there. A clean cut
  lands in the gap between words; a cut mid-syllable sounds broken. One
  keystroke.
- **Play with lead-in** — 2 seconds before the in-point. You judge an edit by
  hearing the approach to it, not the clip in isolation.
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

**Phase 1 — Frame cutter** *(half a day, no UI)*
The load-bearing piece. Range-fetch a byte span, scan to a frame sync, copy
whole frames, write ID3, download. Verify the output plays in QuickTime, VLC and
a browser, and that its duration matches the request. Prove this before building
anything on top of it.

**Phase 2 — Peaks + waveform** *(half a day)*
Fetch, decode at 8 kHz through `OfflineAudioContext`, reduce to peaks, cache in
IndexedDB, render to canvas. Both views — full episode and zoomed selection.
Watch first-open time on a real connection; 75 MB is not instant.

**Phase 3 — Selection** *(half a day)*
Draggable handles, numeric readout, nudge keys, play-selection and play-with-
lead-in. Pre-seed the selection from the search passage's `start_sec`/`end_sec`.

**Phase 4 — Wire it in** *(2 hours)*
A "Clip" button on each moment in a search result. Modal reuses the existing
shell. Filename and ID3 from episode metadata.

**Phase 5 — Snap to silence** *(2 hours)*
Local-minimum search in the peak array. Small, and the thing producers will
actually thank you for.

**Risk sits in Phase 2**, not Phase 1 — decoding 75 MB in a tab is the part most
likely to be slow or memory-hostile on a modest laptop. If it disappoints, the
fallback is a coarse overview built from ~40 sampled range-requests rather than
a full decode, with the zoomed view decoded on demand.

---

## Worth doing first, cheaply

**Shareable moment links** — `?ep=123&from=522&to=549` opens the app at that
episode, cued to that passage. An hour's work, no decoding, no export. For "send
a colleague this bit", it may be the whole answer — and it's worth finding out
before building five phases of editor.
