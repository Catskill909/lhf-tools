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
  reduceRms, noiseFloor, nextSilence, edgeWindow, viewForPlayhead,
  dragSelection, resumeRange,
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

/* ---------------------------------------------------------------- edgeWindow
   The bug was a fixed ±2s window around a mark, which on any selection shorter
   than the window played audio the clip does not contain — and made the two
   buttons play nearly the same thing.

   So the test is the invariant, not the arithmetic: swept across selection
   lengths from far shorter than the window to far longer, at both edges, the
   range must never leave the selection. Checking one 20-second selection would
   pass on the broken version, which is how this shipped. */
{
  console.log("\nedgeWindow");
  const SECS = 3;
  let escaped = 0, collided = 0, worst = "";

  for (const len of [0.2, 0.5, 1, 1.5, 2, 2.9, 3, 3.1, 4, 10, 60, 600]) {
    for (const inSec of [0, 0.7, 12, 3600]) {
      const outSec = inSec + len;
      const a = edgeWindow({ inSec, outSec, secs: SECS, edge: "in" });
      const b = edgeWindow({ inSec, outSec, secs: SECS, edge: "out" });
      for (const w of [a, b]) {
        if (w.from < inSec - 1e-9 || w.to > outSec + 1e-9) {
          escaped++;
          worst = `len ${len}s at ${inSec}s -> ${w.from.toFixed(2)}–${w.to.toFixed(2)}`;
        }
        if (w.to < w.from) escaped++;
      }
      // Once the selection is longer than the window the two ends must be
      // telling you different things, or there is no reason for two buttons.
      if (len > SECS * 2 && Math.abs(a.from - b.from) < 1e-9) collided++;
    }
  }
  check("neither end ever plays outside the selection", escaped === 0, worst);
  check("the two ends stay distinct on clips longer than the window",
        collided === 0);

  const long = edgeWindow({ inSec: 100, outSec: 160, secs: 3, edge: "in" });
  check("start plays the clip's own first seconds",
        long.from === 100 && long.to === 103, `${long.from}–${long.to}`);
  const lastly = edgeWindow({ inSec: 100, outSec: 160, secs: 3, edge: "out" });
  check("end plays the clip's own last seconds",
        lastly.from === 157 && lastly.to === 160, `${lastly.from}–${lastly.to}`);

  // A clip shorter than the window degrades to "play the whole thing" from
  // either button — honest, where overshooting was not.
  const tiny = { inSec: 40, outSec: 41.2, secs: 3 };
  const ti = edgeWindow({ ...tiny, edge: "in" }), to = edgeWindow({ ...tiny, edge: "out" });
  check("a clip shorter than the window plays whole from both ends",
        ti.from === 40 && ti.to === 41.2 && to.from === 40 && to.to === 41.2);

  // Reversed marks are not reachable through the UI, which enforces a minimum
  // gap — but a helper that returns to < from would play nothing at all and
  // look like a dead button, so it is pinned rather than left to chance.
  const rev = edgeWindow({ inSec: 9, outSec: 4, secs: 3, edge: "in" });
  check("survives reversed marks", rev.from === 4 && rev.to === 7);
}

/* ----------------------------------------------------------- viewForPlayhead
   The bug was that nothing moved the view, so a playhead outside the window was
   simply not drawn — audio running, lower waveform frozen. The test is the
   round trip: take the returned centre, rebuild the window through the real
   clipWindow, and require the playhead to actually be inside it. Asserting the
   returned number alone would not have caught a centre that clamping then
   pushed back off screen at the ends of the episode. */
{
  console.log("\nviewForPlayhead");
  check("stays out of the way while the playhead is visible",
        viewForPlayhead({ playhead: 50, from: 40, to: 60 }) === null);
  check("and at the very edges of the window",
        viewForPlayhead({ playhead: 40, from: 40, to: 60 }) === null &&
        viewForPlayhead({ playhead: 60, from: 40, to: 60 }) === null);
  check("does nothing without a playhead",
        viewForPlayhead({ playhead: null, from: 0, to: 10 }) === null);

  const DURATION = 3000, pad = 16;
  let missed = 0, worst = "";
  // Both directions, and both ends of the episode, where clipWindow clamps.
  for (const playhead of [0, 0.5, 12, 900, 1800.25, DURATION - 0.5, DURATION]) {
    for (const [inSec, outSec] of [[71, 94], [0, 4], [1500, 1530], [DURATION - 8, DURATION]]) {
      const before = clipWindow({ inSec, outSec, pad, duration: DURATION });
      const v = viewForPlayhead({ playhead, from: before.from, to: before.to });
      if (v == null) continue;                  // already visible — nothing to do
      const after = clipWindow({ inSec, outSec, pad, duration: DURATION, centre: v });
      if (playhead < after.from - 1e-6 || playhead > after.to + 1e-6) {
        missed++;
        worst = `playhead ${playhead}s -> window ${after.from.toFixed(1)}–${after.to.toFixed(1)}`;
      }
    }
  }
  check("always brings the playhead into the window it returns", missed === 0, worst);

  // Runway: landing the playhead a quarter in rather than centred is what keeps
  // a forward play from re-centring every half window.
  const v = viewForPlayhead({ playhead: 1000, from: 0, to: 40 });
  const w = clipWindow({ inSec: 990, outSec: 1010, pad: 20, duration: DURATION, centre: v });
  check("leaves most of the window ahead of a forward play",
        1000 - w.from < (w.to - w.from) * 0.3,
        `${(1000 - w.from).toFixed(1)}s behind of ${(w.to - w.from).toFixed(1)}s`);
}

/* -------------------------------------------------------------- dragSelection
   The two things a hand-rolled `in = where I pressed, out = where I am` gets
   wrong are dragging right-to-left and dragging a distance shorter than the
   handles can be separated by. Both are swept rather than sampled, and the
   episode's two ends are included because that is where the clamp folds back. */
{
  console.log("\ndragSelection");
  const DUR = 600, MIN = 0.2;
  let asym = 0, tooShort = 0, escaped = 0, worst = "";

  const spans = [0, 0.001, 0.05, 0.2, 0.3, 1, 7, 120, 599, 600, 900];
  const starts = [0, 0.05, 3, 299, 599.9, 600];
  for (const anchor of starts) {
    for (const span of spans) {
      for (const dir of [1, -1]) {
        const at = anchor + span * dir;
        const s = dragSelection({ anchor, at, duration: DUR, minLen: MIN });

        // Dragging away from a point and back to it across the same span must
        // describe the same selection — but only once the span is wide enough
        // to be a selection at all. Below the minimum the two are genuinely
        // different gestures: the marks grow in the direction the hand moved,
        // which is asserted separately below.
        if (Math.abs(span) >= MIN) {
          const mirror = dragSelection({ anchor: at, at: anchor, duration: DUR, minLen: MIN });
          if (Math.abs(s.inSec - mirror.inSec) > 1e-9 ||
              Math.abs(s.outSec - mirror.outSec) > 1e-9) asym++;
        }

        if (s.outSec - s.inSec < MIN - 1e-9) {
          tooShort++;
          if (!worst) worst = `anchor ${anchor} span ${span} dir ${dir} -> ${s.inSec}–${s.outSec}`;
        }
        if (s.inSec < -1e-9 || s.outSec > DUR + 1e-9 || s.outSec < s.inSec) escaped++;
      }
    }
  }
  check("dragging right-to-left gives the same selection as left-to-right", asym === 0);
  check("never returns a selection shorter than the handles can be separated",
        tooShort === 0, worst);
  check("never leaves the episode", escaped === 0);

  const plain = dragSelection({ anchor: 40, at: 52, duration: DUR });
  check("an ordinary drag is just the span covered",
        plain.inSec === 40 && plain.outSec === 52, `${plain.inSec}–${plain.outSec}`);
  const back = dragSelection({ anchor: 52, at: 40, duration: DUR });
  check("and the same drag backwards", back.inSec === 40 && back.outSec === 52);

  // A tiny drag at the very end has no room to expand forwards, so it has to
  // fold back off the end rather than run past it.
  const end = dragSelection({ anchor: DUR, at: DUR, duration: DUR, minLen: MIN });
  check("a drag at the very end folds back inside the episode",
        end.outSec === DUR && Math.abs(end.inSec - (DUR - MIN)) < 1e-9,
        `${end.inSec}–${end.outSec}`);
  const start0 = dragSelection({ anchor: 0, at: 0, duration: DUR, minLen: MIN });
  check("and one at the very start expands forwards",
        start0.inSec === 0 && Math.abs(start0.outSec - MIN) < 1e-9);

  // A drag too short to be a selection still has a direction, and the mark you
  // pressed on should stay put while the other one moves away from it — press
  // and flick right sets an in-point, flick left sets an out-point. Getting
  // this backwards would make a short drag jump the selection behind the
  // pointer, which reads as the editor fighting you.
  const flickR = dragSelection({ anchor: 100, at: 100.02, duration: DUR, minLen: MIN });
  check("a flick right keeps the press point as the in-point",
        flickR.inSec === 100 && Math.abs(flickR.outSec - 100.2) < 1e-9,
        `${flickR.inSec}–${flickR.outSec}`);
  const flickL = dragSelection({ anchor: 100, at: 99.98, duration: DUR, minLen: MIN });
  check("a flick left keeps the press point as the out-point",
        flickL.outSec === 100 && Math.abs(flickL.inSec - 99.8) < 1e-9,
        `${flickL.inSec}–${flickL.outSec}`);
}

/* ---------------------------------------------------------------- resumeRange
   The bug this exists to stop is a playhead moved without the range it is
   measured against: togglePlay then resumes from somewhere other than the place
   just chosen. It had shipped in the [ / ] silence jump.

   So the test is the property togglePlay actually depends on — the returned
   range contains the playhead — asserted over playheads inside, outside, and
   exactly on both marks. A test that only moved the playhead inside the
   selection passes the broken version, since the stale range was usually the
   selection. */
{
  console.log("\nresumeRange");
  let missed = 0, worst = "";
  const sel = [[71, 94], [0, 5], [300, 300.2], [1000, 2400]];
  const heads = [0, 12, 70.999, 71, 82, 94, 94.001, 300.1, 1200, 5000];

  for (const [inSec, outSec] of sel) {
    for (const playhead of heads) {
      const r = resumeRange({ playhead, inSec, outSec });
      const end = r.to ?? Infinity;
      if (playhead < r.from - 1e-9 || playhead > end + 1e-9) {
        missed++;
        worst = `head ${playhead} sel ${inSec}–${outSec} -> ${r.from}–${r.to}`;
      }
    }
  }
  check("the range always contains the playhead", missed === 0, worst);

  const inside = resumeRange({ playhead: 82, inSec: 71, outSec: 94 });
  check("inside the selection it stays bounded by the selection",
        inside.from === 71 && inside.to === 94 && inside.follow === "sel");

  const outside = resumeRange({ playhead: 300, inSec: 71, outSec: 94 });
  check("outside it becomes an open play from the playhead",
        outside.from === 300 && outside.to === null && outside.follow === false);

  // Exactly on a mark counts as inside — a click that lands on the in-point
  // should repeat the clip, not start an open play that happens to begin there.
  for (const [h, label] of [[71, "in-point"], [94, "out-point"]]) {
    const r = resumeRange({ playhead: h, inSec: 71, outSec: 94 });
    check(`landing exactly on the ${label} counts as inside`, r.follow === "sel");
  }
}

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
