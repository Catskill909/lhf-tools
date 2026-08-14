/* Pure tests for the saved-clip store. No browser, no network.
 *
 * `clips.js` is written against localStorage, which doesn't exist in Node, so
 * a minimal one is installed on globalThis before importing. That is the whole
 * shim — everything else under test is the real module.
 *
 *   node tests/test-clips.mjs
 */

let store = Object.create(null);
globalThis.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
  clear: () => { store = Object.create(null); },
};

const Clips = await import("../static/clips.js");

let pass = 0, fail = 0;
const check = (name, ok) => {
  if (ok) { pass++; console.log("  PASS  " + name); }
  else    { fail++; console.log("  FAIL  " + name); }
};
const reset = () => { store = Object.create(null); };
const add = (over = {}) => Clips.add({
  url: "https://cdn.example/ep1.mp3", title: "a quote", show: "LHT",
  date: "2026-03-14", in: 10, out: 20, ...over,
});

console.log("\nstore basics");
reset();
check("an empty store lists nothing", Clips.list().length === 0);
const a = add();
check("add returns the saved record", a && a.id && a.createdAt > 0);
check("count reflects the add", Clips.count() === 1);
check("newest is first", add({ title: "second" })[0] === undefined && Clips.list()[0].title === "second");
check("update patches in place", Clips.update(a.id, { title: "renamed" }).title === "renamed");
check("update leaves other fields alone", Clips.list().find(c => c.id === a.id).show === "LHT");
check("update of a missing id returns null", Clips.update("nope", { title: "x" }) === null);
check("remove takes it out", Clips.remove(a.id) && Clips.count() === 1);
check("remove of a missing id returns null", Clips.remove("nope") === null);

console.log("\nidentity");
reset();
const k1 = add(), k2 = add();
check("ids are unique", k1.id !== k2.id);
check("the record keys on the audio url", k1.url === "https://cdn.example/ep1.mp3");
// Episode ids are assigned in ingest order and can be reassigned by a rebuild;
// the row must survive one being wrong, so nothing may look it up by epId.
check("epId is optional and does not identify the clip", add({ epId: null }).epId === null);

console.log("\nundo restores position, not order");
reset();
const r1 = add({ title: "one" }), r2 = add({ title: "two" }), r3 = add({ title: "three" });
// unshift means the list reads three, two, one
const at = Clips.indexOf(r2.id);
check("indexOf finds the middle record", at === 1);
Clips.remove(r2.id);
check("removed leaves two", Clips.count() === 2);
Clips.restore(r2, at);
check("restore puts it back in the middle, not on top",
  Clips.list().map(c => c.title).join(",") === "three,two,one");
check("restore past the end still lands", (() => {
  const gone = Clips.remove(r1.id);
  Clips.restore(gone, 99);
  return Clips.list().at(-1).title === "one";
})());

console.log("\nlabels are derived, never registered");
reset();
add({ title: "p1", labels: ["Promo", "Intro"] });
add({ title: "p2", labels: ["Promo"] });
add({ title: "p3", labels: ["Atmos"] });
const counts = Clips.labelCounts();
check("counts are highest-use first", counts[0].label === "Promo" && counts[0].n === 2);
check("ties break alphabetically so the bar doesn't reshuffle",
  counts.slice(1).map(c => c.label).join(",") === "Atmos,Intro");
check("labelNames is the same order", Clips.labelNames()[0] === "Promo");
// The class of bug this guards: a label surviving its last use would leave a
// filter chip that matches nothing, and there is no registry to prune.
const promos = Clips.list().filter(c => (c.labels || []).includes("Promo"));
for (const c of promos) Clips.update(c.id, { labels: c.labels.filter(l => l !== "Promo") });
check("dropping the last use removes the label entirely",
  !Clips.labelNames().includes("Promo"));

console.log("\ncase folding on entry");
reset();
add({ labels: ["Promo"] });
check("an existing label wins whatever the casing", Clips.canonicalLabel("promo") === "Promo");
check("upper case folds too", Clips.canonicalLabel("PROMO") === "Promo");
check("surrounding space is trimmed", Clips.canonicalLabel("  promo  ") === "Promo");
check("a genuinely new label keeps its own spelling", Clips.canonicalLabel("Out-cue") === "Out-cue");
check("empty input is not a label", Clips.canonicalLabel("   ") === null);
check("null input is not a label", Clips.canonicalLabel(null) === null);

console.log("\nclip search");
const searchable = [
  { id: "woody", title: "Woody Guthrie’s American Song", show: "Labor Heritage Power Hour",
    date: "2026-08-13", labels: ["Promo", "Music"], in: 10, out: 35, createdAt: 30 },
  { id: "zinn", title: "The People's Historian", show: "Labor History Today",
    date: "2026-08-09", labels: ["Interview"], in: 20, out: 50, createdAt: 20 },
  { id: "strike", title: "Organizing a General Strike", show: "Labor History Today",
    date: "2025-12-08", labels: ["Encore", "Promo"], in: 5, out: 70, createdAt: 10 },
  { id: "label", title: "A saved excerpt", show: "Labor Heritage Power Hour",
    date: "2025-01-01", labels: ["Woody"], in: 0, out: 8, createdAt: 5 },
];
const hits = q => Clips.search(searchable, q).map(row => row.clip.id);
check("plain words are implicitly ANDed and the last is a prefix",
  hits("people hist").join() === "zinn");
check("plain search handles apostrophes like the archive tokenizer",
  hits("people's hist").join() === "zinn");
check("quoted phrases stay together", hits('"american song"').join() === "woody");
check("OR finds either side",
  hits("historian OR strike").sort().join() === "strike,zinn");
check("NOT excludes a matching clip", hits("promo NOT encore").join() === "woody");
check("parentheses combine with boolean operators",
  hits("(historian OR strike) NOT encore").join() === "zinn");
check("an explicit star prefix expands a word", hits("organiz*").join() === "strike");
check("title fields stay in the title", hits("title:woody").join() === "woody");
check("show fields accept a phrase", hits('show:"Labor History Today"').sort().join() === "strike,zinn");
check("label and date fields search clip metadata",
  hits("label:promo date:2026").join() === "woody");
const scored = Clips.search(searchable, "woody");
check("title matches outrank the same word in a label",
  scored.find(row => row.clip.id === "woody").score > scored.find(row => row.clip.id === "label").score);
check("an empty search returns every clip", hits("").length === searchable.length);

console.log("\nstorage is versioned, like the peaks cache");
reset();
add();
const raw = JSON.parse(store["lhf-clips"]);
check("the record carries a version", raw.v === 1);
store["lhf-clips"] = JSON.stringify({ v: 0, clips: [{ id: "old" }] });
check("a wrong version reads as empty, not as current data", Clips.list().length === 0);
store["lhf-clips"] = JSON.stringify({ clips: [{ id: "old" }] });
check("a missing version reads as empty", Clips.list().length === 0);
store["lhf-clips"] = "{ this is not json";
check("unparseable storage reads as empty rather than throwing", Clips.list().length === 0);
store["lhf-clips"] = JSON.stringify({ v: 1, clips: "not an array" });
check("a wrong shape reads as empty", Clips.list().length === 0);

console.log("\na browser that refuses storage");
reset();
const good = globalThis.localStorage;
globalThis.localStorage = {
  getItem() { throw new Error("SecurityError"); },
  setItem() { throw new Error("QuotaExceededError"); },
};
check("reading through a refusal gives an empty library, not a crash", Clips.list().length === 0);
let threw = false;
try { add(); } catch { threw = true; }
// It must throw so the caller can tell the user the clip was NOT saved.
// Swallowing it would report success and lose the work.
check("writing through a refusal throws so the caller can say so", threw === true);
globalThis.localStorage = good;

console.log("\ndate grouping");
const now = new Date(2026, 7, 9, 14, 0, 0).getTime();   // 9 Aug 2026, 2pm
const day = 864e5;
check("this morning is Today", Clips.groupOf(now - 3600e3, now) === "Today");
check("just after midnight is still Today",
  Clips.groupOf(new Date(2026, 7, 9, 0, 30).getTime(), now) === "Today");
check("last night is Yesterday",
  Clips.groupOf(new Date(2026, 7, 8, 23, 0).getTime(), now) === "Yesterday");
check("three days back is Last week", Clips.groupOf(now - 3 * day, now) === "Last week");
check("six days back is still Last week", Clips.groupOf(now - 6 * day, now) === "Last week");
check("eight days back is not", Clips.groupOf(now - 8 * day, now) !== "Last week");
check("long ago names the month", /2026/.test(Clips.groupOf(now - 60 * day, now)));
// Grouping is computed from createdAt every render, never stored — so a clip
// saved today reads as Yesterday tomorrow without anything rewriting it.
check("the same timestamp regroups as the clock moves",
  Clips.groupOf(now, now) === "Today" && Clips.groupOf(now, now + day) === "Yesterday");

console.log(`\n${fail ? "FAILED" : "all passed"} — ${pass} checks, ${fail} failures\n`);
process.exit(fail ? 1 : 0);
