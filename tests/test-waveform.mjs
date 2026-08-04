/**
 * Peak reduction and snap-to-silence, tested on a synthetic signal.
 *
 * No network and no browser: reducePeaks() and snapToSilence() are pure, which
 * is why they were written as separate exports rather than folded into the
 * drawing code.
 *
 *   node tests/test-waveform.mjs
 */

import { reducePeaks, snapToSilence, clipWindow } from "../static/waveform.js";

let failures = 0;
function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  — " + detail : ""}`);
  if (!ok) failures++;
}

/* A 10-second signal at 8 kHz with known structure:
   loud 0-2s, silence 2-2.5s, medium 2.5-4s, silence 4-4.5s, loud 4.5-10s.
   The silences are where a cut should land. */
const RATE = 8000, DUR = 10;
const samples = new Float32Array(RATE * DUR);
for (let i = 0; i < samples.length; i++) {
  const t = i / RATE;
  const quiet = (t >= 2 && t < 2.5) || (t >= 4 && t < 4.5);
  const amp = quiet ? 0.002 : (t >= 2.5 && t < 4 ? 0.4 : 0.9);
  samples[i] = Math.sin(t * 440 * 2 * Math.PI) * amp;
}

console.log("reducePeaks");
const peaks = reducePeaks(samples, 1000);
check("returns 2 values per bucket", peaks.length === 2000, `${peaks.length}`);

const envAt = sec => {
  const b = Math.floor((sec / DUR) * 1000);
  return Math.abs(peaks[b * 2]) + Math.abs(peaks[b * 2 + 1]);
};
const loud = envAt(1), medium = envAt(3), silent = envAt(2.2);
check("orders loud > medium > silent", loud > medium && medium > silent,
      `${loud.toFixed(3)} > ${medium.toFixed(3)} > ${silent.toFixed(3)}`);
check("silence is near zero", silent < 0.01, silent.toFixed(4));

console.log("snapToSilence");
// Each case starts at a LOUD point, so a passing result proves the function
// actually moved. Testing from a point that is already quiet proves nothing.
for (const [from, lo, hi] of [[1.2, 1.9, 2.55], [1.7, 1.9, 2.55], [1.95, 1.9, 2.55],
                              [3.6, 3.9, 4.55], [5.0, 3.9, 4.55]]) {
  const to = snapToSilence(peaks, DUR, from);
  check(`${from}s lands in a silent gap`, to >= lo && to <= hi, `${to.toFixed(2)}s`);
}

// With no silence within reach it must stay put rather than jump somewhere odd.
const held = snapToSilence(peaks, DUR, 8.0);
check("stays local when no silence is in range", Math.abs(held - 8.0) < 0.5,
      `${held.toFixed(2)}s`);

console.log("clipWindow");
{
  const DURATION = 3300;
  // The invariant the zoom UI depends on: whatever the zoom level or position,
  // both handles must be inside the visible window, or you cannot grab them.
  let ok = true, widest = 0;
  for (const [inSec, outSec] of [[0, 20], [10, 12], [1600, 1640], [3280, 3300],
                                 [0, 3300], [3299, 3300], [5, 400]]) {
    for (const pad of [0.25, 1, 6, 40, 300]) {
      const w = clipWindow({ inSec, outSec, pad, duration: DURATION });
      const holds = w.from <= inSec + 1e-9 && w.to >= outSec - 1e-9
                 && w.from >= 0 && w.to <= DURATION + 1e-9 && w.to > w.from;
      if (!holds) { ok = false; console.log(`      broke at [${inSec},${outSec}] pad ${pad}`,
                                            w.from.toFixed(2), w.to.toFixed(2)); }
      widest = Math.max(widest, w.to - w.from);
    }
  }
  check("selection always inside the window, window always inside the file", ok,
        `widest span ${widest.toFixed(0)}s of ${DURATION}s`);

  // Clamping at the edges must slide the window, not shrink it — shrinking
  // would change the zoom level without the user asking.
  const mid = clipWindow({ inSec: 1600, outSec: 1620, pad: 30, duration: DURATION });
  const head = clipWindow({ inSec: 0, outSec: 20, pad: 30, duration: DURATION });
  const tail = clipWindow({ inSec: 3280, outSec: 3300, pad: 30, duration: DURATION });
  check("same zoom keeps the same span at the start of the file",
        Math.abs((head.to - head.from) - (mid.to - mid.from)) < 0.01,
        `${(head.to - head.from).toFixed(1)}s vs ${(mid.to - mid.from).toFixed(1)}s`);
  check("same zoom keeps the same span at the end of the file",
        Math.abs((tail.to - tail.from) - (mid.to - mid.from)) < 0.01,
        `${(tail.to - tail.from).toFixed(1)}s vs ${(mid.to - mid.from).toFixed(1)}s`);
  check("selection is centred away from the edges",
        Math.abs((mid.from + mid.to) / 2 - 1610) < 0.01,
        `centre ${((mid.from + mid.to) / 2).toFixed(1)}s`);
  check("survives a missing duration", (() => {
    const w = clipWindow({ inSec: 10, outSec: 30, pad: 6, duration: 0 });
    return isFinite(w.from) && isFinite(w.to) && w.to > w.from;
  })(), "no NaN when the feed omitted duration_sec");
}

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
