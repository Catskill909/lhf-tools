/* Structural coverage for saved-clip discovery controls. The pure query
 * semantics live in test-clips.mjs; this file protects their wiring, the sort
 * menu's keyboard contract, and the phone geometry around both controls.
 *
 *   node tests/test-clips-ui.mjs
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");
let checks = 0, failures = 0;
const check = (label, ok) => {
  checks++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}`);
  if (!ok) failures++;
};

console.log("\nclip-library search and sort");
check("the library exposes a real search field",
  /id="libFilter"[^>]*type="search"[^>]*placeholder="Search clips…"/.test(html));
check("search has an explicit clear control",
  /id="libFilterClear"[^>]*aria-label="Clear clip search"/.test(html));
check("the controls appear for every non-empty library",
  /#libToolsRow"\)\.hidden = !all\.length/.test(html));
check("the UI delegates query semantics to the clip module",
  /Clips\.search\(Clips\.list\(\), q\)/.test(html));
check("the sort menu uses the front-page listbox pattern",
  /id="libSortBtn"[^>]*aria-haspopup="listbox"[^>]*aria-expanded="false"/.test(html) &&
  /id="libSortMenu" role="listbox" aria-label="Sort saved clips"/.test(html));
check("search adds Best match and the archive's five browse orders",
  /\["relevance", "Best match"\][\s\S]*\["newest",\s+"Newest saved"\][\s\S]*\["oldest",\s+"Oldest saved"\][\s\S]*\["title",\s+"Title A–Z"\][\s\S]*\["longest",\s+"Longest first"\][\s\S]*\["shortest",\s+"Shortest first"\]/.test(html));
check("sort options support arrows, Home, End, Escape and Tab",
  /libSortMenu\.addEventListener\("keydown"[\s\S]*ArrowDown[\s\S]*ArrowUp[\s\S]*Home[\s\S]*End[\s\S]*Escape[\s\S]*Tab/.test(html));
check("slash belongs to the open library rather than the page behind it",
  /if \(libOpen\(\)\) return;\s*\/\/ and the saved-clips dialog/.test(html) &&
  /e\.key === "\/"[\s\S]*#libFilter/.test(html));
check("Escape clears a clip query before closing the dialogue",
  /e\.key === "Escape" && libFilterText[\s\S]*libFilterText = ""[\s\S]*#libFilter/.test(html));

console.log("\nclip-library phone geometry");
const phone = html.slice(html.indexOf("@media (max-width: 620px)"), html.indexOf("/* Tablet touch layout"));
check("search occupies its own phone row",
  /\.lib-tools\s*\{[^}]*display:\s*grid[^}]*grid-template-columns/.test(phone) &&
  /\.lib-search\s*\{\s*grid-column:\s*1 \/ -1/.test(phone));
check("phone search and sort controls reach 44px",
  /#libFilter\s*\{[^}]*min-height:\s*44px/.test(phone) &&
  /#libSortBtn\s*\{\s*min-height:\s*44px/.test(phone));
check("phone row actions are visible 44px targets",
  /\.cliprow \.cr-more, \.cliprow \.cr-dl\s*\{[^}]*width:\s*44px;\s*height:\s*44px[^}]*border-color/.test(phone));
check("the library modal uses dynamic viewport height",
  /#libModal \.modal\s*\{[^}]*max-height:\s*calc\(100dvh - 1rem\)/.test(phone));

console.log(`\n${checks - failures} passed, ${failures} failed`);
if (failures) process.exit(1);
