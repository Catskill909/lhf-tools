/**
 * Nothing made of data may be wider than the phone.
 *
 * `.ents` lays its tags out with `display: flex; flex-wrap: wrap`, and `.ent`
 * carried `white-space: nowrap`. A flex item's `min-width` defaults to `auto`,
 * which floors it at its min-content width — and with `nowrap` the min-content
 * width of a chip is the entire unbroken tag. The chip therefore could not
 * shrink and could not wrap, so it set the width of the card, the card set the
 * width of the document, and the document became wider than the viewport.
 *
 * The tag "The People's Historian: The Outsized Life of Howard Zinn" measures
 * 434px. On a 402px iPhone the document came out 450px wide, and iOS answered
 * that the way it always does — it shrank the whole site to fit, so the app
 * rendered at ~60% scale in the top-left corner with dead space beside it.
 * Nothing looked wrong in any desktop window, because there the chip fits.
 *
 * The bug is not the tag, and it is not flex either: an unshrinkable element
 * overflows a block parent just as happily, and grows the document just the
 * same. The bug is `white-space: nowrap` on an element whose text comes from
 * the database or from the user — text whose length is not ours to assume.
 * Three classes had that shape: `.ent` (tags), `.chip` (show names from the
 * feed) and `.lblmini` (clip labels, which the user types).
 *
 * So the test derives its subjects rather than listing them: it reads the
 * templates for elements whose content is interpolated, and checks that each
 * one can break. A fourth chip built the same way is caught without anyone
 * remembering to add it here.
 *
 * Some pinned text really is bounded — a mm:ss timestamp, a menu label written
 * in the source. Those opt out by saying so in the stylesheet, next to the
 * declaration, rather than in a list kept over here where it would drift away
 * from the decision it describes. The marker is the word `bounded` in a comment
 * inside the same rule.
 *
 * `overflow-wrap: anywhere` is the escape that counts. `break-word` looks like
 * it should work and does not — it breaks lines during layout but leaves the
 * min-content width alone, which is the exact number this bug is about.
 *
 *   node tests/test-overflow.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");
const clips = readFileSync(join(ROOT, "static", "clips.js"), "utf8");

/* `@media` blocks are flattened rather than dropped, so a `nowrap` that a
   narrow breakpoint already overrides is correctly read as safe. */
const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"))
  .replace(/@media[^{]*\{/g, "");

let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}

console.log("\nnothing made of data outgrows the viewport\n");

/* ---------- the stylesheet ---------- */

/**
 * Rule blocks, with comments dropped from selectors but kept inside bodies.
 *
 * A regex split cannot do this. The comments in this stylesheet are prose, and
 * prose has commas in it — left in the selector, the paragraph above `.ents` is
 * read as that rule's own selector and the rule disappears from the scan. An
 * earlier draft of this test passed for exactly that reason, while the bug it
 * was written for was still on screen.
 */
function parseRules(text) {
  const rules = [];
  let sel = "";
  let i = 0;
  while (i < text.length) {
    if (text.startsWith("/*", i)) {              // between rules — not a selector
      const end = text.indexOf("*/", i + 2);
      i = end === -1 ? text.length : end + 2;
      continue;
    }
    const ch = text[i];
    if (ch === "{") {
      let depth = 1;
      let j = i + 1;
      while (j < text.length && depth > 0) {
        if (text.startsWith("/*", j)) {          // kept: this is where `bounded` lives
          const e = text.indexOf("*/", j + 2);
          j = e === -1 ? text.length : e + 2;
          continue;
        }
        if (text[j] === "{") depth++;
        else if (text[j] === "}") depth--;
        j++;
      }
      rules.push({ selector: sel.trim(), body: text.slice(i + 1, j - 1) });
      sel = "";
      i = j;
      continue;
    }
    if (ch === "}") { sel = ""; i++; continue; }
    sel += ch;
    i++;
  }
  return rules;
}

const rules = parseRules(css).filter(r => r.selector && !r.selector.startsWith("@"));
check("the stylesheet parsed", rules.length > 50, `${rules.length} rules`);

/** Rules where this class is the subject — ".ents > .lbl" styles the label,
    not .ents, and must not be read as a rule about .ents. */
function rulesFor(cls) {
  const re = new RegExp(`\\.${cls}(?![-\\w])`);
  return rules.filter(r => r.selector.split(",").some(one => {
    const last = one.trim().split(/[\s>+~]+/).pop() || "";
    return re.test(last);
  }));
}

const strip = s => s.replace(/\/\*[\s\S]*?\*\//g, "");

/** The last value a property takes for this class, or "". */
function prop(cls, name) {
  const decls = rulesFor(cls).map(r => strip(r.body)).join(";");
  const hits = [...decls.matchAll(new RegExp(`(?:^|;)\\s*${name}\\s*:\\s*([^;!]+)`, "g"))];
  return hits.length ? hits[hits.length - 1][1].trim() : "";
}

/** Has someone stated, beside the declaration, that this text has a fixed length? */
function declaredBounded(cls) {
  return rulesFor(cls).some(r =>
    /white-space\s*:\s*nowrap/.test(strip(r.body)) &&
    [...r.body.matchAll(/\/\*[\s\S]*?\*\//g)].some(c => /\bbounded\b/i.test(c[0])));
}

/* ---------- the templates ---------- */

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input",
                      "link", "meta", "param", "source", "track", "wbr",
                      "path", "circle", "rect", "line", "polygon", "use", "stop"]);

/** Classes on an element whose own content is interpolated from a value. */
const interpolated = new Set();

for (const src of [html, clips]) {
  const stack = [];
  const tag = /<(\/?)([a-z][-a-z0-9]*)\b([^>]*)>/gi;
  let m;
  while ((m = tag.exec(src))) {
    const [whole, slash, name, attrs] = m;
    if (slash) {
      // Pop to the nearest matching open tag. Template literals are not always
      // balanced across string boundaries, so an unmatched close is ignored
      // rather than allowed to corrupt the stack.
      const at = stack.map(f => f.name).lastIndexOf(name.toLowerCase());
      if (at === -1) continue;
      const frame = stack[at];
      stack.length = at;
      if (src.slice(frame.end, m.index).includes("${")) {
        for (const c of frame.classes) interpolated.add(c);
      }
      continue;
    }
    if (VOID.has(name.toLowerCase()) || attrs.trim().endsWith("/")) continue;
    const cls = (/class\s*=\s*"([^"]*)"/.exec(attrs) || [, ""])[1];
    stack.push({
      name: name.toLowerCase(),
      classes: cls.split(/\s+/).filter(Boolean).filter(c => !c.includes("${")),
      end: m.index + whole.length
    });
  }
}

check("the scan found generated content", interpolated.size > 10,
      `${interpolated.size} classes render interpolated text`);

/* ---------- the rule ---------- */

/** Can an element with this class shrink below the width of its own text? */
function canShrink(cls) {
  if (!/nowrap/.test(prop(cls, "white-space"))) return true;     // it can wrap
  if (/anywhere/.test(prop(cls, "overflow-wrap"))) return true;
  if (/break-all/.test(prop(cls, "word-break"))) return true;
  // Clipping keeps the text inside the box, so it cannot push anything out.
  if (/hidden/.test(prop(cls, "overflow")) && prop(cls, "text-overflow")) return true;
  return false;
}

const subjects = [...interpolated].filter(c => rulesFor(c).length).sort();

/* The three known instances, named. If the derivation stops finding them it has
   stopped watching the thing it was written for, and would pass in silence. */
for (const cls of ["ent", "chip", "lblmini"]) {
  check(`.${cls} is still seen as an element filled with data`, subjects.includes(cls),
        subjects.includes(cls) ? "" : "renamed or restructured — check this test still covers the class");
}

const stuck = subjects.filter(c => !canShrink(c) && !declaredBounded(c));
check("every element filled with data can break its text", stuck.length === 0,
      stuck.length
        ? stuck.map(c => `.${c} is white-space:nowrap with no way to break — ` +
                         `add overflow-wrap:anywhere, or say why it is bounded`).join("; ")
        : `${subjects.length} checked`);

const exempt = subjects.filter(c => !canShrink(c) && declaredBounded(c));
console.log(`\n${failures ? `${failures} failed` : "all passed"} — ` +
            `${subjects.length} data-filled classes` +
            (exempt.length ? `, ${exempt.length} declared bounded (${exempt.map(c => "." + c).join(", ")})` : "") + "\n");
process.exit(failures ? 1 : 0);
