/**
 * Peak reduction and snap-to-silence, tested on a synthetic signal.
 *
 * No network and no browser: reducePeaks() and snapToSilence() are pure, which
 * is why they were written as separate exports rather than folded into the
 * drawing code.
 *
 *   node tests/test-waveform.mjs
 */

import { reducePeaks, snapToSilence } from "../static/waveform.js";

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

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
