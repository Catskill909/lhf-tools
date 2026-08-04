/**
 * waveform.js — episode peaks and canvas rendering.
 *
 * A full episode is 75 MB and decodes to 555 MB of Float32 at 44.1 kHz, which
 * a browser tab will not tolerate. But a waveform needs amplitude envelopes,
 * not fidelity — so we decode at 8 kHz instead (101 MB, transient), reduce to
 * a few thousand min/max pairs, and throw the audio away.
 *
 * The peaks are ~32 KB and cached in IndexedDB, so an episode is only ever
 * downloaded once.
 *
 * Nothing here touches our server: the audio comes from the host's CDN.
 */

const BUCKETS = 4000;          // peak pairs per episode — ~32 KB cached
const DECODE_RATE = 8000;      // plenty for an amplitude envelope
const DB_NAME = "lhf-peaks";
const STORE = "peaks";

/* ------------------------------------------------------------ peaks */

/**
 * Reduce samples to `buckets` min/max pairs.
 * Pure and synchronous so it can be tested without a browser.
 * Returns Float32Array [min0, max0, min1, max1, …].
 */
export function reducePeaks(samples, buckets = BUCKETS) {
  const out = new Float32Array(buckets * 2);
  const per = samples.length / buckets;
  for (let b = 0; b < buckets; b++) {
    const from = Math.floor(b * per);
    const to = Math.min(samples.length, Math.floor((b + 1) * per));
    let lo = 0, hi = 0;
    for (let i = from; i < to; i++) {
      const v = samples[i];
      if (v < lo) lo = v;
      else if (v > hi) hi = v;
    }
    out[b * 2] = lo;
    out[b * 2 + 1] = hi;
  }
  return out;
}

/** Decode compressed audio at DECODE_RATE and reduce it. Browser only. */
export async function decodePeaks(arrayBuffer, buckets = BUCKETS) {
  // A 1-frame context is enough — decodeAudioData resamples to the context
  // rate regardless of the declared length.
  const ctx = new OfflineAudioContext(1, 1, DECODE_RATE);
  const audio = await ctx.decodeAudioData(arrayBuffer);
  const peaks = reducePeaks(audio.getChannelData(0), buckets);
  return { peaks, duration: audio.duration };
}

/* ------------------------------------------------------------ cache */

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function cacheGet(key) {
  try {
    const db = await openDB();
    return await new Promise((resolve) => {
      const r = db.transaction(STORE).objectStore(STORE).get(key);
      r.onsuccess = () => resolve(r.result || null);
      r.onerror = () => resolve(null);
    });
  } catch { return null; }        // private browsing, quota, etc — just re-decode
}

async function cachePut(key, value) {
  try {
    const db = await openDB();
    db.transaction(STORE, "readwrite").objectStore(STORE).put(value, key);
  } catch { /* caching is an optimisation, never a requirement */ }
}

/* ------------------------------------------------------------ fetch */

/**
 * Peaks for an episode, from cache when possible.
 * `onProgress(loaded, total)` fires during the initial download — 75 MB is
 * not instant and silence would read as a hang.
 */
export async function getPeaks(url, key, { onProgress, signal } = {}) {
  const hit = await cacheGet(key);
  if (hit) return { peaks: new Float32Array(hit.peaks), duration: hit.duration, cached: true };

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Couldn't load the audio (${res.status}).`);

  const total = Number(res.headers.get("Content-Length")) || 0;
  let buf;

  if (res.body && onProgress) {
    const reader = res.body.getReader();
    const chunks = [];
    let loaded = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      loaded += value.length;
      onProgress(loaded, total);
    }
    buf = new Uint8Array(loaded);
    let o = 0;
    for (const c of chunks) { buf.set(c, o); o += c.length; }
    buf = buf.buffer;
  } else {
    buf = await res.arrayBuffer();
  }

  const { peaks, duration } = await decodePeaks(buf);
  cachePut(key, { peaks: Array.from(peaks), duration });
  return { peaks, duration, cached: false };
}

/* ------------------------------------------------------------ draw */

/**
 * Render peaks to a canvas.
 *
 * `from`/`to` are seconds — pass the whole duration for the overview, or a
 * narrow span for the zoomed view. Selection and playhead are drawn on top.
 */
export function drawWave(canvas, peaks, {
  duration, from = 0, to = duration,
  selection = null, playhead = null,
  colors = {},
} = {}) {
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth || canvas.width;
  const cssH = canvas.clientHeight || canvas.height;
  if (canvas.width !== cssW * dpr || canvas.height !== cssH * dpr) {
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const c = {
    wave: "#6d6961", waveSel: "#d8503a",
    selFill: "rgba(216,80,58,0.14)", playhead: "#efece4",
    ...colors,
  };

  const pairs = peaks.length / 2;
  const mid = cssH / 2;
  const span = Math.max(1e-6, to - from);
  const xToSec = x => from + (x / cssW) * span;

  // One vertical bar per pixel column, from the peak bucket it falls in.
  for (let x = 0; x < cssW; x++) {
    const t0 = xToSec(x), t1 = xToSec(x + 1);
    const b0 = Math.max(0, Math.floor((t0 / duration) * pairs));
    const b1 = Math.min(pairs - 1, Math.ceil((t1 / duration) * pairs));
    let lo = 0, hi = 0;
    for (let b = b0; b <= b1; b++) {
      const l = peaks[b * 2], h = peaks[b * 2 + 1];
      if (l < lo) lo = l;
      if (h > hi) hi = h;
    }
    const inSel = selection && t0 >= selection.from && t1 <= selection.to;
    ctx.fillStyle = inSel ? c.waveSel : c.wave;
    const yTop = mid - hi * mid * 0.95;
    const yBot = mid - lo * mid * 0.95;
    ctx.fillRect(x, yTop, 1, Math.max(1, yBot - yTop));
  }

  if (selection) {
    const sx = ((selection.from - from) / span) * cssW;
    const ex = ((selection.to - from) / span) * cssW;
    ctx.fillStyle = c.selFill;
    ctx.fillRect(sx, 0, ex - sx, cssH);
    ctx.fillStyle = c.waveSel;
    ctx.fillRect(sx - 1, 0, 2, cssH);
    ctx.fillRect(ex - 1, 0, 2, cssH);
  }

  if (playhead != null && playhead >= from && playhead <= to) {
    const px = ((playhead - from) / span) * cssW;
    ctx.fillStyle = c.playhead;
    ctx.fillRect(px, 0, 1, cssH);
  }
}

/* ------------------------------------------------- snap to silence */

/**
 * Nearest quiet point to `sec`, within `windowSec`.
 *
 * A cut landing mid-syllable sounds broken; one landing in the gap between
 * words sounds deliberate. This is the single most useful editing aid, and
 * the peak data we already have is enough to find it.
 */
export function snapToSilence(peaks, duration, sec, windowSec = 1.5) {
  const pairs = peaks.length / 2;
  const perSec = pairs / duration;
  const centre = Math.round(sec * perSec);
  const span = Math.max(1, Math.round(windowSec * perSec));

  let best = centre, bestAmp = Infinity;
  for (let b = Math.max(0, centre - span); b <= Math.min(pairs - 1, centre + span); b++) {
    const amp = Math.abs(peaks[b * 2]) + Math.abs(peaks[b * 2 + 1]);
    // Prefer quiet, but break ties toward the original point so the handle
    // doesn't leap across the screen for a marginal gain.
    const score = amp + Math.abs(b - centre) / (span * 200);
    if (score < bestAmp) { bestAmp = score; best = b; }
  }
  return best / perSec;
}
