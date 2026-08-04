# Audio clip editor — specification

**Status:** specced, not built.

Select a passage found by search, adjust the in/out points against a waveform,
export the clip. Everything in the browser; **our server does nothing at all**
— the audio streams from Podbean's CDN direct to the user.

---

## The constraint that shapes everything

Measured against a real episode before designing anything:

| | |
|---|---|
| Episode length | 54.9 min |
| File size | **170.8 MB** |
| Bitrate | ~434 kbps (unusually high — near-lossless) |
| Decoded to PCM | **1,110 MB** stereo Float32 |

**A whole episode cannot be decoded in a browser tab.** 1.1 GB of Float32 will
either fail outright or make the machine crawl. wavesurfer's own documentation
warns about exactly this. Any design that starts "load the audio file" is dead
on arrival.

**A two-minute window, however, is 40 MB decoded — completely fine.**

So the rule is: **never load the whole episode. Fetch a window around the
moment.** Verified working — a range request into the middle of a file returns
`HTTP 206`, and an MP3 frame sync was found 28 bytes into an arbitrary slice, so
a mid-file chunk decodes without the preceding file.

This is also what makes the "light server load" goal trivially achievable: the
range request goes to Podbean's CDN, not to us. We serve a modal and some
JavaScript.

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

- Fetch the byte range covering that window, decode, draw.
- Handles drag to adjust in/out. Dragging near an edge extends the window
  (fetch more, append) rather than being a hard wall.
- Default window ±45s = ~90s = ~30 MB decoded and a ~5 MB fetch. Comfortable.

**Byte-range ↔ time mapping.** At a constant bitrate,
`byte_offset ≈ seconds × (bitrate_bits / 8)`. Verify these files are CBR — if
they're VBR the mapping drifts, so **pad the request generously (±5 s) and trim
after decoding**, using the decoded sample count as truth rather than the
estimate. Cheap insurance either way.

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
