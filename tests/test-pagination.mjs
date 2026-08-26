/* Structural coverage for browser-safe archive search pagination.
 *
 *   node tests/test-pagination.mjs
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

console.log("\narchive search pagination");
check("the page exposes an accessible Load more control",
  /id="loadMore"[^>]*aria-describedby="pageStatus"/.test(html) &&
  /id="pageStatus"[^>]*aria-live="polite"/.test(html));
check("browser requests are fixed at 50 cards",
  /const SEARCH_PAGE_SIZE = 50/.test(html) &&
  /api\.set\("limit", SEARCH_PAGE_SIZE\)/.test(html));
check("later pages continue from the server's next offset",
  /api\.set\("offset", append \? nextSearchOffset : 0\)/.test(html) &&
  /nextSearchOffset = data\.next_offset/.test(html));
check("a debounced query change cannot append onto stale cards",
  /if \(append && searchKey !== loadedSearchKey\) return/.test(html) &&
  /loadedSearchKey = searchKey/.test(html));
check("a new query aborts obsolete network work",
  /searchController\?\.abort\(\)/.test(html) &&
  /new AbortController\(\)/.test(html) &&
  /signal: searchController\.signal/.test(html));
check("only newly inserted cards receive new handlers",
  /const newRows = \[\.\.\.template\.content\.querySelectorAll\("\.row"\)\]/.test(html) &&
  /newRows\.flatMap\(row => \[\.\.\.row\.querySelectorAll/.test(html));
check("automatic loading is progressive and preserves the real button",
  /"IntersectionObserver" in window/.test(html) &&
  /moreObserver\.observe\(\$\("#resultsMore"\)\)/.test(html));
check("episode notes fill the row without an empty action column",
  /\.row \.notes\s*\{[^}]*white-space:\s*pre-line/.test(html) &&
  !/\.row \.notes\s*\{[^}]*max-width:/.test(html) &&
  /\.notes-wrap\.is-clamped \.notes\.clamp\s*\{\s*padding-right:\s*3\.6rem/.test(html));
check("paging state is excluded from shareable URLs",
  /const api = new URLSearchParams\(p\);[\s\S]*api\.set\("limit"[\s\S]*history\.replaceState/.test(html) === false &&
  /history\.replaceState[\s\S]*const api = new URLSearchParams\(p\)/.test(html));

console.log(`\n${checks - failures} passed, ${failures} failed`);
if (failures) process.exit(1);
