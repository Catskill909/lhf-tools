/**
 * Peak reduction and snap-to-silence, tested on a synthetic signal.
 *
 * No network and no browser: reducePeaks() and snapToSilence() are pure, which
 * is why they were written as separate exports rather than folded into the
 * drawing code.
 *
 *   node tests/test-waveform.mjs
 */

import {
  reducePeaks, snapToSilence, clipWindow, niceTick, tickLabel,
  reduceRms, noiseFloor, nextSilence,
} from "../static/waveform.js";

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
  const CASES = [[0, 20], [10, 12], [1600, 1640], [3280, 3300],
                 [0, 3300], [3299, 3300], [5, 400]];
  const PADS = [0.25, 1, 6, 40, 300];

  // The window must always be a real range inside the file. This part never
  // changed and is the one thing the drawing code cannot survive without.
  {
    let ok = true, widest = 0;
    for (const [inSec, outSec] of CASES) {
      for (const pad of PADS) {
        for (const anchor of [null, "in", "out"]) {
          const w = clipWindow({ inSec, outSec, pad, duration: DURATION, anchor });
          if (!(w.from >= 0 && w.to <= DURATION + 1e-9 && w.to > w.from)) {
            ok = false;
            console.log(`      broke at [${inSec},${outSec}] pad ${pad} anchor ${anchor}`,
                        w.from.toFixed(2), w.to.toFixed(2));
          }
          widest = Math.max(widest, w.to - w.from);
        }
      }
    }
    check("window is always a real range inside the file", ok,
          `widest span ${widest.toFixed(0)}s of ${DURATION}s`);
  }

  // The replaced invariant. Both handles used to be forced on screen at every
  // zoom level, which made a 30-second selection impossible to zoom into past
  // 30.5 seconds. Now: the selection is framed while it fits, and past that
  // the anchored edge is what stays visible.
  {
    let fits = true, anchored = true;
    for (const [inSec, outSec] of CASES) {
      for (const pad of PADS) {
        const span = Math.min(DURATION, pad * 2);
        if (span >= outSec - inSec) {
          const w = clipWindow({ inSec, outSec, pad, duration: DURATION });
          if (!(w.from <= inSec + 1e-9 && w.to >= outSec - 1e-9)) fits = false;
        } else {
          for (const [anchor, edge] of [["in", inSec], ["out", outSec]]) {
            const w = clipWindow({ inSec, outSec, pad, duration: DURATION, anchor });
            if (!(w.from <= edge + 1e-9 && w.to >= edge - 1e-9)) {
              anchored = false;
              console.log(`      lost the ${anchor} edge at [${inSec},${outSec}] pad ${pad}`);
            }
          }
        }
      }
    }
    check("while the selection fits, the whole selection is visible", fits);
    check("once zoomed past it, the anchored edge stays visible", anchored);
  }

  // The point of the change, stated as a number.
  {
    const tight = clipWindow({ inSec: 600, outSec: 630, pad: 0.25,
                               duration: DURATION, anchor: "out" });
    check("a 30-second selection can now be inspected at half a second",
          (tight.to - tight.from) < 0.6, `${(tight.to - tight.from).toFixed(2)}s window`);
    check("and that window is on the edge being worked",
          tight.from <= 630 && tight.to >= 630,
          `${tight.from.toFixed(2)}–${tight.to.toFixed(2)}s around out=630`);
  }

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
  check("an explicit centre still overrides everything (the drag freeze)",
        Math.abs((() => {
          const w = clipWindow({ inSec: 600, outSec: 630, pad: 5,
                                 duration: DURATION, centre: 900, anchor: "out" });
          return (w.from + w.to) / 2;
        })() - 900) < 0.01);
  check("survives a missing duration", (() => {
    const w = clipWindow({ inSec: 10, outSec: 30, pad: 6, duration: 0 });
    return isFinite(w.from) && isFinite(w.to) && w.to > w.from;
  })(), "no NaN when the feed omitted duration_sec");
}

/* ------------------------------------------------------------ ruler
   The tick chooser and the label formatter are the only parts of the ruler
   that can be wrong in a way you'd argue about, so they're the parts that got
   pulled out as pure functions. */
console.log("ruler ticks");
{
  // 1400px is roughly the editor's width on a laptop.
  const maxTicks = Math.floor(1400 / 78);
  check("a 55-minute episode gets round minute ticks",
        [60, 120, 300, 600].includes(niceTick(3300, maxTicks)),
        `${niceTick(3300, maxTicks)}s`);
  check("a 22-second window gets seconds",
        niceTick(22, maxTicks) >= 1 && niceTick(22, maxTicks) <= 5,
        `${niceTick(22, maxTicks)}s`);
  check("a 3-second window gets sub-second ticks",
        niceTick(3, maxTicks) < 1, `${niceTick(3, maxTicks)}s`);

  // The point of the ladder: never a step you'd have to do arithmetic on.
  const ok = [3300, 600, 120, 22, 3, 1].every(span => {
    const t = niceTick(span, maxTicks);
    return [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600].includes(t);
  });
  check("every step comes off the ladder", ok);

  check("never crowds the axis past the label budget",
        [3300, 600, 120, 22, 3].every(span => span / niceTick(span, maxTicks) <= maxTicks));

  check("degrades rather than dividing by zero on a narrow canvas",
        isFinite(niceTick(3300, 2)) && niceTick(3300, 2) > 0, `${niceTick(3300, 2)}s`);
}

console.log("ruler labels");
{
  check("whole seconds above a 1s step", tickLabel(750, 30) === "12:30", tickLabel(750, 30));
  check("pads the seconds", tickLabel(605, 5) === "10:05", tickLabel(605, 5));
  check("tenths below a 1s step", tickLabel(30.2, 0.2) === "0:30.2", tickLabel(30.2, 0.2));
  check("pads tenths under ten seconds", tickLabel(5.5, 0.5) === "0:05.5", tickLabel(5.5, 0.5));
  check("zero reads as zero", tickLabel(0, 60) === "0:00", tickLabel(0, 60));
  // No episode in this archive reaches an hour, so this is guarding the day
  // one does rather than anything visible now.
  check("past an hour, hours appear", tickLabel(4500, 60) === "1:15:00", tickLabel(4500, 60));
  check("minutes are padded once hours show", tickLabel(3660, 60) === "1:01:00", tickLabel(3660, 60));
  check("hours survive sub-second steps", tickLabel(3600.5, 0.5) === "1:00:00.5",
        tickLabel(3600.5, 0.5));
}

/* ----------------------------------------------------- detail tier
   The whole point of Phase 3: at the overview's resolution a real episode's
   inter-word gaps are shorter than one bucket, so they cannot be found. These
   tests use a realistic episode length rather than the 10-second fixture
   above, because that is where the old resolution actually failed. */
console.log("detail resolution");
{
  const RATE2 = 8000, DUR2 = 2040;          // a 34-minute episode
  const OVERVIEW = 4000, DETAIL = DUR2 * 100;

  // Speech that pauses the way speech does: 2s of talk, then a 0.3s gap. That
  // puts ~13% of the episode below the floor, which is what makes a percentile
  // floor meaningful — see the note on noiseFloor(). A signal with no pauses
  // at all has no silence to find, and neither the line nor the snap can
  // invent one.
  const GAP = 0.3, PERIOD = 2.3;
  const inGapAt = t => (t % PERIOD) >= PERIOD - GAP;
  const GAP_AT = Math.floor(1000 / PERIOD) * PERIOD + PERIOD - GAP;  // a real gap near 1000s
  const n = RATE2 * DUR2;
  const sig = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / RATE2;
    sig[i] = Math.sin(t * 300 * 2 * Math.PI) * (inGapAt(t) ? 0.001 : 0.7);
  }

  check("one overview bucket is wider than the gap it must find",
        DUR2 / OVERVIEW > GAP, `${(DUR2 / OVERVIEW).toFixed(2)}s bucket vs ${GAP}s gap`);
  check("one detail bucket is far narrower than the gap",
        DUR2 / DETAIL < GAP / 10, `${(DUR2 / DETAIL * 1000).toFixed(0)}ms bucket`);

  const coarse = reducePeaks(sig, OVERVIEW);
  const fine = reducePeaks(sig, DETAIL);

  // The regression this phase exists to fix. At overview resolution the snap
  // can only land on a 0.51s grid, so it cannot reach the middle of a 0.3s
  // gap; at 10ms it lands inside it.
  const gapMid = GAP_AT + GAP / 2;
  const coarseSnap = snapToSilence(coarse, DUR2, GAP_AT - 0.4);
  const fineSnap = snapToSilence(fine, DUR2, GAP_AT - 0.4);
  check("overview peaks CANNOT place a cut inside the gap",
        !(coarseSnap >= GAP_AT && coarseSnap <= GAP_AT + GAP),
        `landed at ${coarseSnap.toFixed(3)}s, gap is ${GAP_AT}–${(GAP_AT + GAP).toFixed(2)}s`);
  check("detail peaks DO place the cut inside the gap",
        fineSnap >= GAP_AT && fineSnap <= GAP_AT + GAP,
        `landed at ${fineSnap.toFixed(3)}s`);

  console.log("rms and noise floor");
  const rms = reduceRms(sig, DETAIL);
  check("one rms value per bucket", rms.length === DETAIL, `${rms.length}`);
  const bAt = sec => Math.floor((sec / DUR2) * DETAIL);
  check("rms is high in speech and low in the gap",
        rms[bAt(500)] > 0.3 && rms[bAt(gapMid)] < 0.01,
        `speech ${rms[bAt(500)].toFixed(3)}, gap ${rms[bAt(gapMid)].toFixed(4)}`);
  check("rms of a sine is below its peak",
        rms[bAt(500)] < 0.7, `${rms[bAt(500)].toFixed(3)} < 0.7`);

  const floor = noiseFloor(rms);

  console.log("silence navigation");
  {
    const f = noiseFloor(rms);
    // Gaps sit at the end of every PERIOD, so their centres are predictable.
    const gapCentre = k => k * PERIOD + PERIOD - GAP / 2;
    const fwd = nextSilence(rms, DUR2, gapCentre(100) - PERIOD / 2, 1, f);
    check("finds the next gap forward",
          Math.abs(fwd - gapCentre(100)) < 0.05, `${fwd.toFixed(2)}s vs ${gapCentre(100).toFixed(2)}s`);

    // The point of stepping out of the current gap: pressing again must move on.
    const again = nextSilence(rms, DUR2, fwd, 1, f);
    check("pressing again advances rather than sticking",
          again > fwd + PERIOD / 2, `${fwd.toFixed(2)}s -> ${again.toFixed(2)}s`);
    check("and lands on the following gap",
          Math.abs(again - gapCentre(101)) < 0.05, `${again.toFixed(2)}s`);

    const back = nextSilence(rms, DUR2, gapCentre(100) + PERIOD / 2, -1, f);
    check("finds the previous gap backward",
          Math.abs(back - gapCentre(100)) < 0.05, `${back.toFixed(2)}s`);
    check("stepping back out of a gap works too",
          nextSilence(rms, DUR2, back, -1, f) < back - PERIOD / 2);

    check("returns null past the last gap rather than sliding to the end",
          nextSilence(rms, DUR2, DUR2 - 0.01, 1, f) === null);
    check("returns null before the first gap",
          nextSilence(rms, DUR2, 0, -1, f) === null);
    check("survives an empty array", nextSilence(new Float32Array(0), DUR2, 10, 1, 0) === null);
    check("survives a zero duration", nextSilence(rms, 0, 10, 1, f) === null);
  }

  check("noise floor sits above true silence and below speech",
        floor > 0 && floor < rms[bAt(500)], `${floor.toFixed(4)}`);
  check("noise floor is not thrown by an all-silent signal",
        noiseFloor(new Float32Array(1000)) === 0);
  check("noise floor survives an empty array", noiseFloor(new Float32Array(0)) === 0);
}

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
