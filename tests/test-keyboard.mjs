/**
 * The keyboard has to reach what the user is looking at.
 *
 * Two rules, one bug. Space in the clip editor closed the dialogue and threw
 * the selection away, and it took both halves to do it:
 *
 *   1. `openClip` focused the close ×, and the Space binding exempted the
 *      close × — so the browser's own "Space activates a button" was live for
 *      every user from the moment the editor opened. The exemption was written
 *      for Download, where the user *tabs* to the control deliberately. It was
 *      never true of a control the app focused on their behalf.
 *
 *   2. Nothing took the focus off it. Every timeline surface calls
 *      preventDefault on pointerdown — it must, or a drag paints a text
 *      selection across the dialogue — and preventDefault on pointerdown also
 *      cancels the browser's *focus transfer*. So clicking the waveform moved
 *      the playhead and left the keyboard on the ×.
 *
 * The second half is the general one, and it had a quieter victim: the in/out
 * handles are buttons whose arrow keys nudge them, and clicking one never
 * focused it, so the nudge had never worked at all.
 *
 * This file tests the class in both directions — no dialogue may open focused
 * on its close button, and no press handler may prevent the default
 * without taking the focus that default would have moved.
 *
 * Nothing is copied: static/index.html is read and parsed at run time.
 *
 *   node tests/test-keyboard.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");
const SCRIPT = html.indexOf("<script type=\"module\">");
const js = html.slice(SCRIPT);
/** Line number in index.html of an offset into `js`, so a failure is findable. */
const lineOf = i => html.slice(0, SCRIPT + i).split("\n").length;

let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}

console.log("\nthe keyboard reaches what you are looking at\n");

/* ---------- 1. opening focus is never a close button ---------- */

/* Stated as "no close button is ever a focus target", not "openClip focuses
   the dialogue", because the failure is not specific to one dialogue: help,
   the transcript and the library all did it too, and in those three Space is
   the ordinary way to scroll a page of text. Any new dialogue that copies the
   old pattern trips this without anyone thinking to add a case. */
const closeFocus = [...js.matchAll(/\$\(\s*["']#(\w*[Cc]lose)["']\s*\)\s*\.focus\(\)/g)]
  .map(m => m[1]);
check("no dialogue opens with the focus on its close button",
      closeFocus.length === 0,
      closeFocus.length ? `focused: ${[...new Set(closeFocus)].join(", ")} — ` +
        `use focusDialog(<backdrop>) instead` : "");

/* ---------- 2. the dialogues that are focused can hold focus ---------- */

/* focusDialog calls .focus() on a plain <div>, which silently does nothing
   unless the div is focusable. A dialogue that fails this looks fixed and
   isn't: focus stays wherever it was, which is the whole bug again. */
const focused = [...js.matchAll(/focusDialog\(\s*([\w$]+)\s*\)/g)].map(m => m[1]);
check("focusDialog is used at all", focused.length > 0,
      focused.length ? "" : "nothing calls focusDialog — has the helper been removed?");

/* The backdrop consts are named for the element they hold: `const clipModal =
   $("#clipModal")`. Resolve each back to an id so the markup can be checked. */
for (const name of [...new Set(focused)]) {
  const decl = new RegExp(`const\\s+${name}\\s*=\\s*\\$\\(\\s*["']#([\\w-]+)["']`).exec(js);
  if (!decl) { check(`${name} resolves to an element id`, false, "cannot find its declaration"); continue; }
  const id = decl[1];
  // The dialogue itself is the .modal inside the backdrop.
  const open = new RegExp(`id="${id}"[^>]*>\\s*<div class="modal"([^>]*)>`).exec(html);
  if (!open) { check(`#${id} contains a .modal`, false, "no .modal found inside the backdrop"); continue; }
  check(`#${id}'s dialogue can hold focus`, /tabindex="-1"/.test(open[1]),
        /tabindex="-1"/.test(open[1]) ? "" : `add tabindex="-1" to the .modal inside #${id}`);
}

/* A focus target is not a control and must not draw a ring on the first
   keypress after opening — the ring on a box that already fills the screen
   reads as "everything is selected". */
const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));
const NORING = /\.modal:focus[^{]*\{[^}]*outline\s*:\s*none/.test(css);
check("the dialogue focus target draws no ring", NORING,
      NORING ? "" : "add  .modal:focus, .modal:focus-visible { outline: none; }");

/** The whole `if (...)` condition starting at `from`, parens balanced. */
function condAt(src, from) {
  let i = src.indexOf("(", from), depth = 0;
  const start = i;
  for (; i < src.length; i++) {
    if (src[i] === "(") depth++;
    else if (src[i] === ")" && --depth === 0) return src.slice(start, i + 1);
  }
  return src.slice(start);
}

/* ---------- 3. Space belongs to the transport ---------- */

/* The exemption list is allowed to name controls the user tabs to on purpose.
   It may not name a close control, because nothing about a close × says "the
   user chose to stand here" — the app puts the focus there. */
/* The editor's binding is the one that reaches togglePlay — the episode list
   binds Space too, and matching the first `e.key === " "` in the file found
   that one instead, which is how the first draft of this test passed against
   the shipped bug. */
let spaceGuard = null;
for (const m of js.matchAll(/if\s*\(\s*e\.key === " "/g)) {
  const cond = condAt(js, m.index);
  if (/togglePlay\(/.test(js.slice(m.index, m.index + cond.length + 120))) { spaceGuard = cond; break; }
}
check("the editor binds Space", !!spaceGuard,
      spaceGuard ? "" : "no Space binding reaching togglePlay was found");
if (spaceGuard) {
  /* An id, not the bare word: `closest` contains "close", and matching that
     made the check unfailable. */
  const named = spaceGuard.match(/#\w*[Cc]lose\w*/g);
  check("Space is not exempted for a close control", !named,
        named ? `guard exempts ${named.join(", ")}: ${spaceGuard.trim()}` : "");
}

/** The markup of the <div> opening at `from`, nested divs included. */
function blockAt(src, from) {
  const start = src.indexOf(">", from) + 1;
  let i = start, depth = 1;
  const tag = /<\/?div\b/g;
  tag.lastIndex = start;
  for (let m; (m = tag.exec(src)); ) {
    depth += m[0][1] === "/" ? -1 : 1;
    if (depth === 0) return src.slice(start, m.index);
    i = m.index;
  }
  return src.slice(start, i);
}

/* ---------- 4. nothing hands focus to an exempted control ---------- */

/* The exemption is only ever true of a control the user's own Tab or click put
   them on. Focus *restoration* is neither: `closeSave` handed the keyboard back
   to "＋ Add to library", which is inside `.modal-actions`, so the next Space
   reopened the save dialogue instead of playing — the reported bug one control
   along. Restoring to it is still right for a keyboard user, so the rule is not
   "never focus it" but "never focus it unconditionally".
   The exempt controls are read out of the guard and the markup, so a button
   added to the action row is covered without anyone remembering to add it. */
if (spaceGuard) {
  const clipMarkup = (() => {
    const i = html.indexOf('id="clipModal"');
    const j = html.indexOf('class="backdrop"', i + 1);
    return html.slice(i, j < 0 ? html.length : j);
  })();
  const exemptIds = new Set();
  for (const cls of spaceGuard.match(/\.[\w-]+/g) || []) {
    const open = new RegExp(`<div class="${cls.slice(1)}"[^>]*>`).exec(clipMarkup);
    if (!open) continue;
    /* Depth-counted, not a non-greedy `</div>`: the action row holds a nested
       status div, and the lazy match stopped at *its* close — so the first
       draft of this check read four ids that were never the point and passed
       while the bug it was written for sat two lines below them. */
    for (const m of blockAt(clipMarkup, open.index).matchAll(/id="([\w-]+)"/g)) exemptIds.add(m[1]);
  }
  check("the exempt controls were identified", exemptIds.size > 0,
        exemptIds.size ? [...exemptIds].join(", ") : "no ids found in the exempted markup");

  const unguarded = [];
  for (const id of exemptIds) {
    for (const m of js.matchAll(new RegExp(`\\$\\(\\s*["']#${id}["']\\s*\\)\\.focus\\(\\)`, "g"))) {
      /* The discriminator has to be in view of the call — `detail` on the
         activating event, or the flag derived from it. */
      const near = js.slice(Math.max(0, m.index - 400), m.index);
      if (!/\bdetail\b|ByPointer\b/.test(near)) unguarded.push(`${id} @ index.html:${lineOf(m.index)}`);
    }
  }
  check("no unconditional focus onto a Space-exempt control", unguarded.length === 0,
        unguarded.length ? `${unguarded.join(", ")} — restore there only when the ` +
          `user arrived by keyboard (e.detail === 0)` : "");
}

/* ---------- 5. a prevented default owes the focus move ---------- */

/** The body of the block starting at the `{` at or after `from`. */
function bodyAt(src, from) {
  let i = src.indexOf("{", from);
  if (i < 0) return "";
  const start = i, n = src.length;
  let depth = 0;
  while (i < n) {
    const c = src[i];
    if (c === "/" && src[i + 1] === "/") { i = src.indexOf("\n", i); if (i < 0) break; continue; }
    if (c === "/" && src[i + 1] === "*") { i = src.indexOf("*/", i); if (i < 0) break; i += 2; continue; }
    if (c === '"' || c === "'" || c === "`") {
      const q = c;
      for (i++; i < n; i++) {
        if (src[i] === "\\") { i++; continue; }
        if (src[i] === q) break;
      }
      i++; continue;
    }
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) return src.slice(start, i + 1); }
    i++;
  }
  return "";
}

/* Every mousedown or pointerdown listener in the file, whether written inline
   or handed a named function. Deliberately not a hand-kept list of the editor's surfaces:
   a list is what a newly added surface is missing from. */
const handlers = [];
for (const m of js.matchAll(/addEventListener\(\s*["'](?:mouse|pointer)down["']\s*,\s*/g)) {
  const after = js.slice(m.index + m[0].length, m.index + m[0].length + 80);
  const named = /^([\w$]+)\s*\)/.exec(after);      // ..., zoomDrag)
  if (named) {
    const fn = new RegExp(`function\\s+${named[1]}\\s*\\(`).exec(js);
    handlers.push({ what: named[1], body: fn ? bodyAt(js, fn.index) : "" });
  } else {
    // An inline arrow or function expression: its body is the next block.
    handlers.push({ what: `index.html:${lineOf(m.index)}`, body: bodyAt(js, m.index) });
  }
}
check("press handlers were found and parsed", handlers.length > 0 && handlers.every(h => h.body),
      handlers.filter(h => !h.body).map(h => h.what).join(", "));

/* The rule. preventDefault on pointerdown/mousedown cancels the focus transfer the browser
   would have done, so the handler has to do it — either by focusing the control
   pressed, or by parking focus on the dialogue when the surface cannot hold it.
   Anything else leaves the keyboard on whatever was focused a click ago. */
const offenders = handlers.filter(h =>
  /preventDefault\s*\(/.test(h.body) && !/\.focus\(|focusAfterPress\s*\(/.test(h.body));
check("a press that prevents the default also takes the focus",
      offenders.length === 0,
      offenders.length ? `${offenders.map(h => h.what).join(", ")} — ` +
        `call focusAfterPress() (the dialogue) or focusAfterPress(el) (the control)` : "");

/* And the handles specifically, because this one was invisible: they are
   buttons with arrow-key nudge, and the nudge is dead unless the press that
   started the drag focuses them. */
const dh = bodyAt(js, js.indexOf("function dragHandle"));
check("dragging a handle focuses it, so the arrows can nudge it",
      /focusAfterPress\s*\(\s*el\s*\)|el\.focus\(/.test(dh),
      dh ? "" : "dragHandle not found");

console.log(`\n${failures ? `${failures} FAILED` : "all passed"}\n`);
process.exit(failures ? 1 : 0);
