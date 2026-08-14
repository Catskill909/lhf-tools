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
check("transcript hover disclosure is limited to real hover devices",
  /@media \(hover: hover\)\s*\{\s*\.tx-line:hover \.tx-edit/.test(html));
check("transcript Edit is visible and finger-sized on touch devices",
  /@media \(hover: none\), \(any-pointer: coarse\)[\s\S]*\.tx-edit\s*\{[^}]*opacity:\s*1;\s*pointer-events:\s*auto[^}]*min-width:\s*44px;\s*min-height:\s*44px/.test(html));

console.log("\nphone transcript reading surface");
const txPhoneStart = html.indexOf("@media (max-width: 767px)", html.indexOf("A phone transcript has three jobs"));
const txPhoneEnd = html.indexOf("/* Printing a transcript", txPhoneStart);
const txPhoneCss = html.slice(txPhoneStart, txPhoneEnd);
check("the phone transcript is an edge-to-edge dynamic-height surface",
  /@media \(max-width: 767px\), \(pointer: coarse\) and \(max-height: 500px\)/.test(txPhoneCss) &&
  /#txModal\s*\{[^}]*padding:\s*0;[^}]*overflow:\s*hidden/.test(txPhoneCss) &&
  /#txModal \.modal\s*\{[^}]*height:\s*100dvh;\s*max-height:\s*none/.test(txPhoneCss));
check("the phone title is compact and its close control remains 44px",
  /#txModal \.modal-head h2\s*\{[^}]*-webkit-line-clamp:\s*2/.test(txPhoneCss) &&
  /#txModal \.modal-head > button\s*\{\s*width:\s*44px;\s*height:\s*44px/.test(txPhoneCss));
check("phone transcript search and navigation controls reach 44px",
  /#txModal \.tx-find input\s*\{[^}]*min-height:\s*44px/.test(txPhoneCss) &&
  /#txModal \.tx-nav\s*\{\s*width:\s*44px;\s*height:\s*44px/.test(txPhoneCss));
check("phone transcript options stay contextual rather than filling the opening view",
  /#txModal \.tx-opt\s*\{\s*display:\s*none/.test(txPhoneCss) &&
  /#txModal \.tx-tools\.has-query \.tx-opt:first-of-type/.test(txPhoneCss));
check("phone transcript rows reserve width only for timestamp and prose",
  /#txModal \.tx-line\s*\{[^}]*grid-template-columns:\s*44px minmax\(0, 1fr\)/.test(txPhoneCss));
check("phone transcript omits every route into unavailable audio editing",
  /#txModal \.tx-player \.pl-edit\s*\{\s*display:\s*none/.test(txPhoneCss) &&
  /#txModal \.tx-edit,[\s\S]*#txModal \.tx-sel,[\s\S]*#txModal \.tx-actions\s*\{\s*display:\s*none !important/.test(txPhoneCss));
check("clearing transcript search also clears Matches only",
  /if \(!q\) \$\("#txOnly"\)\.checked = false;/.test(html) &&
  /classList\.toggle\("has-query", !!q\)/.test(html));

console.log("\ntap-safe hover disclosure");
const clipHoverStart = html.indexOf("@media (hover: hover)", html.indexOf("Hover can disclose secondary"));
const clipTouchEnd = html.indexOf("/* The scope of a bulk download", clipHoverStart);
const clipDisclosureCss = html.slice(clipHoverStart, clipTouchEnd);
check("the player knob hover reveal is limited to real hover devices",
  /@media \(hover: hover\)\s*\{\s*\.pl-track:hover \.pl-knob/.test(html));
check("the player knob stays visible on touch and coarse pointers",
  /@media \(hover: none\), \(any-pointer: coarse\)[\s\S]*\.pl-knob\s*\{\s*opacity:\s*1/.test(html));
check("the audio Edit tooltip cannot consume a touch device's first tap",
  /@media \(hover: hover\)\s*\{\s*\.pl-edit:hover \.pl-tip/.test(html) &&
  /\.pl-edit:focus-visible \.pl-tip/.test(html) &&
  /@media \(hover: none\), \(any-pointer: coarse\)[\s\S]*\.pl-edit:hover \.pl-tip\s*\{\s*opacity:\s*0/.test(html));
check("clip label actions use hover disclosure only on real hover devices",
  /^@media \(hover: hover\)/.test(clipDisclosureCss.trim()) &&
  /\.cliprow:hover \.lblmini \.x\s*\{\s*opacity:\s*1/.test(clipDisclosureCss) &&
  /\.cliprow:hover \.lbladd\s*\{\s*opacity:\s*1/.test(clipDisclosureCss) &&
  /\.cliprow:hover \.cr-more, \.cliprow:hover \.cr-dl/.test(clipDisclosureCss));
check("clip label and row actions are visible and finger-sized on touch",
  /@media \(hover: none\), \(any-pointer: coarse\)/.test(clipDisclosureCss) &&
  /\.lblmini \.x\s*\{\s*opacity:\s*1/.test(clipDisclosureCss) &&
  /\.lbladd\s*\{[^}]*opacity:\s*1;\s*min-height:\s*44px/.test(clipDisclosureCss) &&
  /\.cliprow \.cr-more, \.cliprow \.cr-dl\s*\{\s*width:\s*44px;\s*height:\s*44px/.test(clipDisclosureCss));

console.log(`\n${checks - failures} passed, ${failures} failed`);
if (failures) process.exit(1);
