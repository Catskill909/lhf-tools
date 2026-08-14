/* The audio editor is deliberately tablet-and-up. A phone must get an honest boundary instead of
 * the clipped editor: the 390px audit hid the close control, zoom, Repeat,
 * length and part of Download off-screen.
 *
 * This is structural rather than a browser simulation. Real touch behavior
 * remains a hardware test, but the support message and the CSS gate should not
 * disappear during unrelated editor work.
 *
 *   node tests/test-touch.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");

let failures = 0;
let checks = 0;
function check(label, ok) {
  checks++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}`);
  if (!ok) failures++;
}

console.log("\nphone audio-editor boundary");
check("the document keeps a device-width viewport",
  /<meta\s+name="viewport"\s+content="width=device-width, initial-scale=1">/.test(html));
check("the editor explains that audio editing needs a larger screen",
  /class="clip-phone-warning"[\s\S]*Audio editing needs a larger screen/.test(html));
check("the full editor starts at 768 CSS px",
  /@media\s*\(max-width:\s*767px\)/.test(html));
check("short coarse-pointer landscape screens are also guarded",
  /\(pointer:\s*coarse\)\s+and\s+\(max-height:\s*500px\)/.test(html));
check("the warning becomes visible inside the compact-screen rule",
  /#clipModal \.clip-phone-warning\s*\{\s*display:\s*block;\s*\}/.test(html));
check("the editor body and action footer are withheld on a phone",
  /#clipModal \.modal-body,\s*#clipModal \.modal-actions\s*\{\s*display:\s*none;\s*\}/.test(html));
check("the compact modal fits its available width",
  /#clipModal \.modal\s*\{[^}]*right:\s*max\(1rem,[^}]*left:\s*max\(1rem,[^}]*width:\s*auto;[^}]*100dvh/.test(html));
check("the phone close control is 44px",
  /#clipModal \.modal-head > button\s*\{\s*width:\s*44px;\s*height:\s*44px;\s*\}/.test(html));

console.log("\ntablet pointer editor");
const editorJs = html.slice(html.indexOf("function dragHandle"), html.indexOf("/* ---------- transport", html.indexOf("function dragHandle")));
check("editor gestures no longer bind mouse-only events",
  !/addEventListener\(\s*["'](?:mousedown|mousemove|mouseup)["']/.test(editorJs));
check("handles, overview and zoom bind Pointer Events",
  /dragHandle[\s\S]*pointerdown/.test(editorJs) &&
  /bindOverviewPointer[\s\S]*pointerdown/.test(editorJs) &&
  /#waveZoom"\)\.addEventListener\("pointerdown"/.test(html));
check("a drag captures its pointer",
  /setPointerCapture\s*\(/.test(html));
check("pointer cancellation and lost capture share cleanup",
  /addEventListener\("pointercancel"/.test(html) &&
  /addEventListener\("lostpointercapture"/.test(html));
check("closing the editor cancels any live pointer",
  /function closeClip\(\)\s*\{\s*cancelActiveClipPointer\(\)/.test(html));
check("waveforms retain vertical scrolling while owning horizontal gestures",
  /\.wave-box canvas\s*\{[^}]*touch-action:\s*pan-y/.test(html) &&
  /\.ruler\s*\{[^}]*touch-action:\s*pan-y/.test(html));
check("vertical drag arbitration is touch-only and preserves mouse/pen drags",
  /if \(e\.pointerType !== "touch"\) return "horizontal";/.test(html));
check("handles fully own their drag gesture",
  /\.handle\s*\{[^}]*touch-action:\s*none/.test(html));
check("touch handles have a 44px hit area without thickening the mark",
  /@media \(any-pointer: coarse\)[\s\S]*\.handle\s*\{\s*width:\s*44px/.test(html) &&
  /\.handle::before\s*\{[^}]*width:\s*3px/.test(html));
check("touch controls and footer actions reach 44px",
  /\.zoom-ctl button\s*\{\s*width:\s*44px;\s*height:\s*44px/.test(html) &&
  /#clipModal \.modal-actions > button\s*\{\s*min-height:\s*44px/.test(html));
check("coarse pointers get tap-specific editor guidance",
  /pointer-coarse[^>]*>Whole episode — tap to listen/.test(html));
check("the inline player scrubber is touch-operable too",
  /track\.addEventListener\("pointerdown"/.test(html) &&
  !/track\.addEventListener\("mousedown"/.test(html) &&
  /\.pl-track\s*\{[^}]*touch-action:\s*pan-y/.test(html));

console.log(`\n${checks - failures} passed, ${failures} failed`);
if (failures) process.exit(1);
