/**
 * Clip cutting, verified against live episodes.
 *
 * Duration alone proves nothing — a clip can be the right length and come from
 * the wrong place. Because the cut is a byte copy, position can be checked
 * exactly: fetch a window of the source around where the clip should be and
 * search it for the clip's own bytes. An exact match proves both that the cut
 * landed where it was asked to *and* that it is genuinely lossless.
 *
 * Needs the network and a running server (for episode metadata):
 *
 *   python3 serve.py --port 8000 &
 *   node tests/verify-clips.mjs [port]
 *
 * Episodes are picked at random each run, so this covers the bitrate spread
 * (128/192/256 kbps) over time rather than pinning one fixture.
 */

import { cutClip, probeMp3, clipFilename } from "../static/mp3cut.js";

const PORT = process.argv[2] || 8000;
const TOLERANCE = 0.026;          // one MP3 frame at 44.1 kHz
const CASES = 4;

let failures = 0;
const check = (ok, label) => {
  console.log(`    ${ok ? "PASS" : "FAIL"}  ${label}`);
  if (!ok) failures++;
};

async function pickEpisodes() {
  // Any query with plenty of transcript hits gives us episodes with real
  // passage timings to cut against.
  const res = await fetch(`http://localhost:${PORT}/api/search?q=labor&limit=60`);
  if (!res.ok) throw new Error(`server not answering on :${PORT} (${res.status})`);
  const { results } = await res.json();
  const usable = results.filter(r => r.audio_url && (r.moments || []).some(m => m.end_sec));
  if (!usable.length) throw new Error("no episodes with audio and timed passages");
  return usable.sort(() => Math.random() - 0.5).slice(0, CASES);
}

for (const ep of await pickEpisodes()) {
  const m = ep.moments.find(x => x.end_sec);
  const inSec = m.start_sec, outSec = Math.min(m.end_sec, m.start_sec + 8);

  console.log(`\n${ep.title.slice(0, 58)}`);
  try {
    const probe = await probeMp3(ep.audio_url);
    const { blob, duration, frames } = await cutClip(ep.audio_url, inSec, outSec, {
      probe,
      meta: { title: ep.title, artist: ep.show_name, album: "LHF Digital Asset Manager" },
    });
    console.log(`    ${probe.bitrate} kbps, audio starts at byte ${probe.audioStart}, `
              + `${frames} frames, ${(blob.size / 1024).toFixed(0)} KB`);

    check(Math.abs(duration - (outSec - inSec)) <= TOLERANCE,
          `duration within one frame (asked ${(outSec - inSec).toFixed(2)}s, `
        + `got ${duration.toFixed(2)}s)`);

    // Strip our own ID3v2 header to recover the copied frames.
    const clip = new Uint8Array(await blob.arrayBuffer());
    const tag = ((clip[6] & 0x7f) << 21) | ((clip[7] & 0x7f) << 14)
              | ((clip[8] & 0x7f) << 7) | (clip[9] & 0x7f);
    const audio = clip.subarray(10 + tag, 10 + tag + 4000);

    const expect = probe.audioStart + inSec * probe.bytesPerSec;
    const lo = Math.max(0, Math.floor(expect - 200000));
    const src = new Uint8Array(await (await fetch(ep.audio_url, {
      headers: { Range: `bytes=${lo}-${Math.floor(expect + 200000)}` },
    })).arrayBuffer());

    let at = -1;
    outer: for (let i = 0; i <= src.length - audio.length; i++) {
      if (src[i] !== audio[0]) continue;
      for (let j = 1; j < audio.length; j++) if (src[i + j] !== audio[j]) continue outer;
      at = lo + i; break;
    }
    check(at >= 0, "clip bytes appear verbatim in the source (lossless)");
    if (at >= 0) {
      const landed = (at - probe.audioStart) / probe.bytesPerSec;
      check(Math.abs(landed - inSec) <= TOLERANCE,
            `landed within one frame (asked ${inSec.toFixed(2)}s, `
          + `landed ${landed.toFixed(2)}s, off ${Math.abs(landed - inSec).toFixed(3)}s)`);
    }

    check(/^[\w-]+_\d{4}-\d{2}-\d{2}_.+_\d{4}-\d{4}\.mp3$/.test(
            clipFilename(ep.show_name, ep.published_at, ep.title, inSec, outSec)),
          "filename carries show, date and timecode");
  } catch (e) {
    check(false, `threw: ${e.message}`);
  }
}

console.log(failures ? `\n${failures} checks failed` : "\nall checks passed");
process.exit(failures ? 1 : 0);
