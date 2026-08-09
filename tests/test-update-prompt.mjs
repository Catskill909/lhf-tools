/**
 * The new-version prompt: when it appears, and — more importantly — when it
 * does not.
 *
 * No network and no browser. The logic under test is lifted verbatim out of
 * static/index.html at run time rather than copied, so this cannot pass while
 * the shipped code says something different. Only `fetch`, the clock and the
 * one element it touches are stubbed.
 *
 * The behaviour worth protecting is the quiet part. A prompt that reappears
 * after being dismissed, or fires on a failed request, teaches people to
 * ignore it — at which point it is worse than not having one, because the
 * stale-tab problem it exists to solve is exactly the one nobody notices.
 *
 *   node tests/test-update-prompt.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");

const start = html.indexOf("let myVersion = null;");
const end = html.indexOf('addEventListener("visibilitychange"');
if (start < 0 || end < 0) {
  console.error("Could not find the update block in static/index.html.\n" +
                "If it was renamed or moved, update the markers here.");
  process.exit(1);
}
const source = html.slice(start, end);

/* ---------- harness ---------- */
const bar = { hidden: true };
const handlers = {};
let serverVersion = "v1";
let fetchCount = 0;
let failNext = false;
let now = 1_000_000;

const $ = sel => (sel === "#updateBar"
  ? bar
  : { addEventListener: (_ev, fn) => { handlers[sel] = fn; } });

const fetchStub = async () => {
  fetchCount++;
  if (failNext) { failNext = false; throw new Error("network"); }
  return { json: async () => ({ version: serverVersion }) };
};

const app = new Function("$", "fetch", "Date", "handlers", source + `
  return {
    checkVersion,
    dismiss: () => handlers["#updateLater"](),
    reloadWired: typeof handlers["#updateReload"] === "function",
  };
`)($, fetchStub, { now: () => now }, handlers);

let failures = 0;
function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  — " + detail : ""}`);
  if (!ok) failures++;
}
// Past the one-a-minute throttle, so each step is testing what it says it is.
const later = () => { now += 70_000; };

console.log("\nnew-version prompt");

await app.checkVersion();
check("the first check records the version and shows nothing", bar.hidden === true);

later();
await app.checkVersion();
check("an unchanged version stays quiet", bar.hidden === true);

later();
serverVersion = "v2";
await app.checkVersion();
check("a new version shows the prompt", bar.hidden === false);

app.dismiss();
check("dismissing hides it", bar.hidden === true);

later();
await app.checkVersion();
check("the dismissed version does not nag again", bar.hidden === true);

later();
serverVersion = "v3";
await app.checkVersion();
check("a further deploy is allowed to ask again", bar.hidden === false);

app.dismiss();
later();
const before = fetchCount;
await app.checkVersion();
await app.checkVersion();
check("checks are throttled to one a minute", fetchCount === before + 1,
      `${fetchCount - before} request(s)`);

later();
serverVersion = "v4";
failNext = true;
await app.checkVersion();
check("a failed check neither throws nor prompts", bar.hidden === true);

later();
await app.checkVersion();
check("it recovers on the next check", bar.hidden === false);

check("the reload button is wired", app.reloadWired);

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
