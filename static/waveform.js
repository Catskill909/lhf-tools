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

const BUCKETS = 4000;          // overview pairs per episode — ~32 KB cached
const DECODE_RATE = 8000;      // plenty for an amplitude envelope
const DB_NAME = "lhf-peaks";
const STORE = "peaks";

/* The detail tier: 100 buckets a second, i.e. 10 ms.
 *
 * The overview's 4,000 buckets span the whole episode, which on a 34-minute
 * show is 0.51 s per bucket — and each bucket is a min/max over that window.
 * A 0.3 s pause between two words is therefore absorbed into whichever
 * syllable beside it is loudest. The silence wasn't hard to see; it wasn't in
 * the data. No rendering change could recover it.
 *
 * 10 ms resolves breaths, plosives and the gaps between words. Below about
 * 20 ms is past where speech editing happens, so this is the right place to
 * stop. It costs nothing extra to compute: the decode is already at 8 kHz, so
 * a bucket is 80 samples — the change is in what we keep, not what we do.
 */
const DETAIL_RATE = 100;

/* Bumped whenever the stored shape changes. A cache entry without a matching
 * version is treated as a miss and re-derived.
 *
 * Without this, shipping a new peak format hands every returning visitor
 * old-format data read as new — a silently wrong waveform, which is the same
 * class of bug as keying the cache on episode id was. Cheap to add, expensive
 * to omit. */
const PEAKS_VERSION = 2;

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

/**
 * Root-mean-square per bucket — the same buckets `reducePeaks` uses.
 *
 * Peak says how far the waveform reached; RMS says how loud it actually was.
 * Drawn together they separate a quiet passage from a loud one with a single
 * transient in it, which is the judgement a producer is making when they ask
 * "is this usable audio or is it just noise?". Pure and synchronous.
 */
export function reduceRms(samples, buckets) {
  const out = new Float32Array(buckets);
  const per = samples.length / buckets;
  for (let b = 0; b < buckets; b++) {
    const from = Math.floor(b * per);
    const to = Math.min(samples.length, Math.floor((b + 1) * per));
    let sum = 0;
    for (let i = from; i < to; i++) sum += samples[i] * samples[i];
    out[b] = to > from ? Math.sqrt(sum / (to - from)) : 0;
  }
  return out;
}

/**
 * Where this episode's silence actually sits, as an RMS amplitude.
 *
 * A fixed threshold can't work across an archive whose levels vary by episode:
 * too high and every gap in a quiet show reads as silence, too low and a noisy
 * one never has any. Taking a low percentile of the episode's own RMS makes
 * the floor self-calibrating, and guarantees that snap targets exist — there
 * is always something below the percentile.
 *
 * The tenth, not the fifteenth: a talk programme runs somewhere in the 10–25%
 * range for pause time, and a percentile chosen at the top of that range lands
 * inside speech on the shows that pause least. Erring low costs a floor line
 * drawn slightly conservatively; erring high marks quiet speech as silence and
 * invites a cut straight through a word.
 *
 * This assumes the episode contains pauses, which speech does. On continuous
 * unbroken audio — wall-to-wall music, say — the 15th percentile lands inside
 * the audio, and the floor line then marks "the quietest this gets" rather
 * than silence. That is the honest answer for such a file: there is no silence
 * to find, and neither the line nor the snap can invent one.
 *
 * Pure.
 */
export function noiseFloor(rms, percentile = 0.10) {
  if (!rms.length) return 0;
  // Sampled rather than sorting 200k floats: the percentile of a 4,000-point
  // sample of a smooth distribution is indistinguishable here, and this runs
  // during a decode the user is already waiting on.
  const stride = Math.max(1, Math.floor(rms.length / 4000));
  const s = [];
  for (let i = 0; i < rms.length; i += stride) s.push(rms[i]);
  s.sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(s.length * percentile))];
}

/**
 * Decode compressed audio at DECODE_RATE and reduce it to both tiers.
 *
 * One decode, two resolutions: the overview spans the episode at 4,000
 * buckets, the detail tier runs at 10 ms for the zoomed view and for
 * snap-to-silence. Browser only.
 */
export async function decodePeaks(arrayBuffer, buckets = BUCKETS) {
  // A 1-frame context is enough — decodeAudioData resamples to the context
  // rate regardless of the declared length.
  const ctx = new OfflineAudioContext(1, 1, DECODE_RATE);
  const audio = await ctx.decodeAudioData(arrayBuffer);
  const ch = audio.getChannelData(0);
  const detailBuckets = Math.max(1, Math.round(audio.duration * DETAIL_RATE));
  const detail = reducePeaks(ch, detailBuckets);
  const detailRms = reduceRms(ch, detailBuckets);
  return {
    peaks: reducePeaks(ch, buckets),
    detail, detailRms,
    floor: noiseFloor(detailRms),
    duration: audio.duration,
  };
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
  // An entry from before versioning, or from an older format, is a miss.
  // Reading it as the current shape would draw a confidently wrong waveform.
  if (hit && hit.v === PEAKS_VERSION) {
    return {
      peaks: hit.peaks, detail: hit.detail, detailRms: hit.detailRms,
      floor: hit.floor, duration: hit.duration, cached: true,
    };
  }

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

  const out = await decodePeaks(buf);
  // Typed arrays go in as typed arrays. `Array.from` was merely wasteful at
  // 4,000 buckets; at 200,000+ it turns a fast structured clone of a Float32
  // buffer into a slow one of a boxed-number array, and inflates what is
  // stored several-fold.
  cachePut(key, {
    v: PEAKS_VERSION,
    peaks: out.peaks, detail: out.detail, detailRms: out.detailRms,
    floor: out.floor, duration: out.duration,
  });
  return { ...out, cached: false };
}

/* ------------------------------------------------------------ draw */

/**
 * Render peaks to a canvas.
 *
 * `from`/`to` are seconds — pass the whole duration for the overview, or a
 * narrow span for the zoomed view. Selection and playhead are drawn on top.
 */
/* Amplitude → height, in decibels.
 *
 * Linear scaling is what an oscilloscope does, and it's wrong for judging
 * speech: normal dialogue saturates near full height while room tone, breath
 * and hum sit a pixel or two off the centre line, indistinguishable from
 * digital silence. On a dB scale −40 dB is a third of the height — visibly
 * quiet, visibly not nothing, which is the distinction being made. */
const DB_FLOOR = -60;
function dbScale(a) {
  if (a <= 0) return 0;
  const d = 20 * Math.log10(a);
  return d <= DB_FLOOR ? 0 : (d - DB_FLOOR) / -DB_FLOOR;
}

export function drawWave(canvas, peaks, {
  duration, from = 0, to = duration,
  selection = null, playhead = null,
  rms = null, scale = "linear", floor = null,
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
    // The RMS body sits inside the peak envelope, so it needs to read as the
    // same material at a different weight rather than as a second thing.
    body: "#8f8a80", bodySel: "#e8705c",
    selFill: "rgba(216,80,58,0.14)", playhead: "#efece4",
    floor: "rgba(140,135,125,0.55)",
    ...colors,
  };

  const pairs = peaks.length / 2;
  const mid = cssH / 2;
  const span = Math.max(1e-6, to - from);
  const xToSec = x => from + (x / cssW) * span;
  const amp = scale === "db" ? dbScale : (a => a);
  const h2 = mid * 0.95;

  // One vertical bar per pixel column, from the peak bucket it falls in.
  for (let x = 0; x < cssW; x++) {
    const t0 = xToSec(x), t1 = xToSec(x + 1);
    const b0 = Math.max(0, Math.floor((t0 / duration) * pairs));
    const b1 = Math.min(pairs - 1, Math.ceil((t1 / duration) * pairs));
    let lo = 0, hi = 0, r = 0;
    for (let b = b0; b <= b1; b++) {
      const l = peaks[b * 2], h = peaks[b * 2 + 1];
      if (l < lo) lo = l;
      if (h > hi) hi = h;
      if (rms && rms[b] > r) r = rms[b];
    }
    const inSel = selection && t0 >= selection.from && t1 <= selection.to;

    // Peak envelope first, then the RMS body over it: the outline says how far
    // the signal reached, the body says how loud it was.
    ctx.fillStyle = inSel ? c.waveSel : c.wave;
    const yTop = mid - amp(hi) * h2;
    const yBot = mid + amp(-lo) * h2;
    ctx.fillRect(x, yTop, 1, Math.max(1, yBot - yTop));

    if (rms && r > 0) {
      ctx.fillStyle = inSel ? c.bodySel : c.body;
      const rh = amp(r) * h2;
      ctx.fillRect(x, mid - rh, 1, Math.max(1, rh * 2));
    }
  }

  // Where this episode's silence actually sits. Snap-to-silence hunts for
  // buckets under this line, so drawing it turns that button from a guess into
  // something you can predict: you see the floor, you see which gaps clear it.
  if (floor != null && floor > 0) {
    const fy = amp(floor) * h2;
    // A floor below the scale's own bottom maps to zero height, and the pair
    // of lines would land on the centre line — drawing what looks like a bug
    // instead of information. An episode that quiet has nothing to mark.
    if (fy >= 2) {
      ctx.fillStyle = c.floor;
      ctx.fillRect(0, Math.round(mid - fy), cssW, 1);
      ctx.fillRect(0, Math.round(mid + fy), cssW, 1);
    }
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

  // 2px, not 1: the playhead is a persistent cursor now rather than something
  // visible only while audio is running, and at 1px over the selection fill it
  // reads as a rendering artefact instead of a position you can trust.
  if (playhead != null && playhead >= from && playhead <= to) {
    const px = ((playhead - from) / span) * cssW;
    ctx.fillStyle = c.playhead;
    ctx.fillRect(Math.round(px) - 1, 0, 2, cssH);
  }
}

/* ----------------------------------------------------------- ruler */

/* A ladder of steps that read naturally as time. Anything computed from a
   round decimal — 2.5s, 7s — makes you do arithmetic to place a mark, which
   is the opposite of what a ruler is for. */
const TICKS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

/** Coarsest-to-finest: the smallest step that doesn't crowd the axis. Pure. */
export function niceTick(span, maxTicks) {
  for (const t of TICKS) if (span / t <= maxTicks) return t;
  return TICKS[TICKS.length - 1];
}

/**
 * Label for a tick, at a precision matched to the step.
 * Showing tenths on a five-minute ruler is noise; hiding them on a
 * two-second one makes every tick read the same. Pure.
 */
export function tickLabel(sec, step) {
  // Hours only once there are hours to show. Every episode in this archive is
  // under an hour, so this never fires today — but "72:00" for an hour and a
  // quarter is the kind of thing that ships and then quietly misleads someone
  // reading a timecode off the screen.
  const h = Math.floor(sec / 3600);
  const m = Math.floor(sec / 60) - h * 60;
  const s = sec - Math.floor(sec / 60) * 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  const head = h ? `${h}:${mm}` : mm;
  return step < 1
    ? `${head}:${s.toFixed(1).padStart(4, "0")}`
    : `${head}:${String(Math.round(s)).padStart(2, "0")}`;
}

/**
 * Draw a time axis for the range `from`–`to`.
 *
 * Shared by both waveforms so they can't drift apart in style or in the rule
 * that picks the spacing — the two views differ only in the span handed in.
 */
export function drawRuler(canvas, { from, to, colors = {} } = {}) {
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth || canvas.width;
  const cssH = canvas.clientHeight || canvas.height;
  if (!cssW || !cssH) return;
  if (canvas.width !== cssW * dpr || canvas.height !== cssH * dpr) {
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const c = { tick: "#6d6961", text: "#6d6961", ...colors };
  const span = Math.max(1e-6, to - from);
  // ~78px per label leaves room for "12:30.5" plus breathing space.
  const step = niceTick(span, Math.max(2, Math.floor(cssW / 78)));

  ctx.font = "10px ui-monospace, Consolas, monospace";
  ctx.textBaseline = "top";

  const first = Math.ceil(from / step) * step;
  const n = Math.floor((to - first) / step + 1e-9);
  for (let i = 0; i <= n; i++) {
    // Indexed rather than accumulated: adding a 0.05 step three thousand times
    // drifts far enough to show up as a wandering tick.
    const t = first + i * step;
    const x = Math.round(((t - from) / span) * cssW);
    ctx.fillStyle = c.tick;
    ctx.fillRect(x, cssH - 4, 1, 4);
    const label = tickLabel(t, step);
    // Drop a label rather than let it run off the edge half-drawn.
    if (x + 3 + ctx.measureText(label).width < cssW) {
      ctx.fillStyle = c.text;
      ctx.fillText(label, x + 3, 0);
    }
  }
}

/* --------------------------------------------- silence navigation */

/**
 * The middle of the next quiet stretch from `sec`, searching in `dir`.
 *
 * Snap tidies a mark you have already placed; this is for finding one. At 10 ms
 * resolution the pauses in speech are real features of the data, so the gaps
 * can be jumped between the way a text editor jumps between words — which beats
 * scrubbing and squinting for the place a sentence ends.
 *
 * Works on the RMS array against the episode's own floor. Returns null when
 * there is no further gap, so the caller can leave the playhead alone rather
 * than sliding it to the end of the file. Pure.
 */
export function nextSilence(rms, duration, sec, dir = 1, floor = 0) {
  const n = rms.length;
  if (!n || !duration) return null;
  const perSec = n / duration;
  const step = dir >= 0 ? 1 : -1;
  const quiet = j => rms[j] <= floor;
  let i = Math.max(0, Math.min(n - 1, Math.round(sec * perSec)));

  // Leave whatever gap we are already standing in, or repeated presses would
  // land on the same one for ever.
  while (i >= 0 && i < n && quiet(i)) i += step;
  while (i >= 0 && i < n && !quiet(i)) i += step;
  if (i < 0 || i >= n) return null;

  // Aim for the middle of the gap, not its edge: the middle is where a cut has
  // the most room either side of it.
  let a = i, b = i;
  while (a > 0 && quiet(a - 1)) a--;
  while (b < n - 1 && quiet(b + 1)) b++;
  return ((a + b) / 2) / perSec;
}

/* ------------------------------------------------------ zoom window */

/**
 * The visible time range for the zoomed view.
 *
 * The window is `pad * 2` wide and clamped to the file: near either end it
 * slides inward rather than being squashed, which would silently change the
 * zoom level.
 *
 * **It is no longer forced to contain the whole selection.** The old rule —
 * span = selection + pad either side — kept both handles grabbable at every
 * zoom level, which sounds right and quietly made frame-level work impossible:
 * with a 30-second selection the tightest achievable view was 30.5 seconds, so
 * the zoom control bottomed out long before anything useful. Detail work
 * happens at one edge at a time, which the audition buttons already assume.
 *
 * So: while the selection fits, the view centres on it and behaves as before.
 * Once you zoom past that, it follows `anchor` — the edge you last touched —
 * and that edge stays on screen instead of both. `centre` overrides everything
 * and is what the drag code freezes the view with.
 *
 * Pure, so the clamping can be tested without a browser.
 */
export function clipWindow({ inSec, outSec, pad, duration, centre = null, anchor = null }) {
  const dur = duration || outSec + pad * 2;
  const span = Math.min(dur, Math.max(0.05, pad * 2));
  const selSpan = outSec - inSec;
  const mid = centre != null ? centre
    : span >= selSpan ? (inSec + outSec) / 2
    : anchor === "out" ? outSec : inSec;
  let from = mid - span / 2, to = mid + span / 2;
  if (from < 0) { to -= from; from = 0; }
  if (to > dur) { from -= to - dur; to = dur; }
  from = Math.max(0, from);
  return { from, to: Math.max(from + 0.05, to) };
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
