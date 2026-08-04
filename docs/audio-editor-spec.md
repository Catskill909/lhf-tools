# Audio clip editor — specification

**Status:** specced, not built.

Select a passage found by search, adjust the in/out points against a waveform,
export the clip. Everything in the browser; **our server does nothing at all**
— the audio streams from Podbean's CDN direct to the user.

---

## The numbers (measured, corrected)

An earlier draft of this spec had the file size wrong by 2.2x and assumed
stereo. Corrected against a real episode:

| | |
|---|---|
| Episode length | 55 min (3,300 s) |
| File size | **75.5 MB** |
| Format | **192 kbps mono, CBR** — same bitrate sampled at 10/30/50/90% |
| Computed duration | 3,300 s vs 3,299 s in the feed — matches |

Two consequences, both good:

**1. The byte↔time mapping is exact.** Constant bitrate means
`byte_offset = seconds × 24,000`, no estimation and no drift. A two-minute
window is a 2.7 MB range request. (Verified: mid-file ranges return `HTTP 206`
and carry an MP3 frame sync, so a chunk decodes standalone.)

**2. A full-episode waveform is viable in the browser** — as long as you decode
at a reduced sample rate:

| Decode target | Memory | |
|---|---|---|
| Full episode @ 44.1 kHz | 555 MB | ❌ too much |
| Full episode @ 16 kHz | 201 MB | ❌ marginal |
| **Full episode @ 8 kHz** | **101 MB** | ✅ fine — and plenty for a waveform |
| 2-min selection @ 44.1 kHz | 20 MB | ✅ full quality for export |

---

## Answering the question directly: no, you don't need the VPS

Both halves work in the browser:

**Full-episode waveform.** Fetch the 75 MB once, decode it through an
`OfflineAudioContext` at 8 kHz, walk it to compute ~4,000 peak values, then
throw the audio away. Peak memory ~101 MB, transient. A waveform needs
amplitude envelopes, not fidelity — 8 kHz is far more than enough to draw one.

**Clip extraction.** Range-fetch just the selection at full quality, decode,
export. 2.7 MB and 20 MB of memory for a two-minute clip.

Server load: **zero.** Every byte comes from Podbean's CDN direct to the
browser. We serve a modal and some JavaScript.

Worth caching the computed peaks in `IndexedDB` so re-opening an episode is
instant. If that ever proves too slow on first open, the fallback is computing
peaks once at ingest — but that would mean the VPS downloading 75 MB × 200
episodes (~15 GB) and running ffmpeg, which is exactly what you're trying to
avoid. Try the browser route first; the numbers say it works.

---

## Waveform, not spectrogram

You said spectrogram — for this job you want a **waveform**, and it's the
cheaper of the two.

- **Waveform** — amplitude over time. The shape editors use for selecting,
  because silence, speech and music are visually obvious and you can see where
  a sentence starts.
- **Spectrogram** — frequency over time. For diagnosing hum, hiss or EQ. It
  tells you nothing useful about where to cut.

Waveform it is. Spectrogram could be added later if anyone ever wants it, but
nobody trimming a clip does.

---

## The window model

A search result gives us `start_sec` and `end_sec` for the passage. The editor
opens on a window around it:

```
     window (default ±45s around the passage)
├─────────────────────────────────────────────────┤
        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓
        └ selection ┘        ← draggable handles
```

The full episode is drawn from the low-rate decode; the **selection window** is
range-fetched at full quality for playback and export.

- Whole waveform visible, with the search passage pre-marked inside it.
- Handles drag anywhere along the episode — no window walls, because the
  overview covers the whole file.
- On export, range-fetch exactly the selected span at 44.1 kHz.

**Byte↔time is exact** at CBR: `byte_offset = seconds × 24,000`. Still pad the
request ±2 s and trim after decoding, using the decoded sample count as truth —
MP3 frames don't align to byte boundaries and the first frame in a slice may be
partial.

---

## Library

**Use `wavesurfer.js` v7 + its Regions plugin, vendored into `static/`.**

Building peak extraction, canvas rendering, zoom, and draggable resize handles
from scratch is days of work for something that already exists and is the
standard in this space. Regions gives draggable, resizable selections directly.

Two notes:

- **Feed it a decoded buffer, not a URL.** If you hand wavesurfer the episode
  URL it will try to fetch and decode all 170 MB. Decode the window ourselves
  and pass it via `loadBlob()` with peaks and duration.
- **Vendor the file** (`static/vendor/wavesurfer.min.js`) rather than a CDN
  link. Keeps the app self-contained and offline-capable, which has been
  valuable throughout. ~100 KB.

This doesn't break the zero-dependency property — that was always about Python:
no pip, no venv, no build step. A vendored JS file adds none of those back.

---

## Export

**WAV first. It needs no encoder.**

An `AudioBuffer` becomes a `.wav` with about 30 lines: write a 44-byte RIFF
header, then interleaved 16-bit PCM. No library, no WASM, no server.

It's also the right format for this audience — broadcasters want uncompressed,
and re-encoding an already-lossy MP3 into another MP3 loses a second generation
of quality.

| Format | How | Verdict |
|---|---|---|
| **WAV** | Hand-rolled RIFF header + PCM | ✅ Build this |
| MP3 | `lamejs` (~200 KB, slow in-browser) | Only if someone asks |
| Server-side `ffmpeg` | Clean cuts, any format | Contradicts the light-server goal; keep as a fallback |

Size check: 2 minutes of 44.1 kHz 16-bit stereo WAV ≈ **21 MB**. Fine to
download. Worth showing the size on the button so nobody is surprised.

---

## The modal

Same shell as Help and Export — focus trap, `Esc`, backdrop dismiss are already
solved.

```
┌─ Clip ───────────────────────────────────────────────┐
│ Striking At Kings (Encore) · Power Hour              │
│                                                      │
│   ░░░░▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░            │
│   8:20    ⟨────── selection ──────⟩         10:05    │
│                                                      │
│   ▶  in 8:42.31   out 9:15.80   length 33.5s        │
│                                                      │
│   [ ⟨ ] [ ⟩ ]  nudge   ·   [ Play selection ]        │
│                                                      │
│                    [ Cancel ]  [ Download WAV 5.9MB ]│
└──────────────────────────────────────────────────────┘
```

Deliberately bare, per the brief:

- **Drag the handles** to adjust; numeric in/out shown to 2 decimals.
- **Nudge buttons** (±0.1 s) — dragging can't hit a precise word, and trimming
  a breath before a sentence is the single most common edit.
- **Play selection** loops just the selection, which is how you actually check
  an edit.
- **Live length and file size**, so the download is never a surprise.
- No fades, no gain, no multi-region. Those are Descript's job.

---

## Build order

1. **Range-fetch + decode a window** — the load-bearing piece. Prove a mid-file
   chunk decodes cleanly before building any UI on top.
2. **Vendor wavesurfer + render the window** with the passage pre-selected.
3. **Draggable handles + play selection.**
4. **WAV export.**
5. Nudge controls, window extension on drag-to-edge.

Steps 1–2 are where the risk is. If a mid-file MP3 chunk turns out to decode
badly in Safari (different decoder), the fallback is fetching from byte 0 to
the window end and discarding the front — slower but certain.

---

## Cheaper thing worth doing first

**Shareable moment links** — `?ep=123&from=522&to=549` opens the app at that
episode with the player cued to that passage.

No decoding, no export, no library, maybe an hour's work. For a lot of the
"send a colleague this bit" use case, it's the whole answer — and it's worth
seeing whether that covers the need before building an editor.
