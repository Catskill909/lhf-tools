/**
 * Hiding has to actually hide.
 *
 * `el.hidden = true` is the only way this app hides anything, and it works by
 * the browser's own `[hidden] { display: none }` rule — which lives in the user
 * agent stylesheet and therefore loses to *any* author rule that sets `display`
 * on the same element. So a component styled `display: flex` and then hidden
 * stays fully on screen, with no error, no warning, and JS that reports it as
 * hidden.
 *
 * It shipped twice. The export dialogue kept offering a scope choice it had
 * just decided not to offer, and the clip library's tools row ignored the
 * "fewer than six clips is furniture" rule entirely. Both were `.hidden = true`
 * against a class carrying `display`.
 *
 * The old defence was a companion `.foo[hidden] { display: none }` beside each
 * component — sixteen of them, and the failure was always a forgotten
 * seventeenth. The defence now is one global rule, and this file exists to stop
 * that rule being deleted while anything still depends on it.
 *
 * Nothing is copied: both the stylesheet and the toggles are read out of
 * static/index.html at run time.
 *
 *   node tests/test-hidden.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");
const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));

let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}

console.log("\nhidden actually hides\n");

/* ---------- the rule itself ---------- */

/* !important is not decoration here. Without it the global rule ties with any
   author class on specificity and loses to an id rule outright, which is the
   same defeat in a different costume. */
const GLOBAL = /\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important/.test(css);
check("a global [hidden] rule exists, and is !important", GLOBAL,
      GLOBAL ? "" : "add  [hidden] { display: none !important; }  to the stylesheet");

/* ---------- what depends on it ---------- */

/** Every rule block whose selector list mentions this exact class or id. */
function rulesFor(sel) {
  const esc = sel.replace(/[.#]/, m => "\\" + m);
  return [...css.matchAll(new RegExp(`([^{}]*${esc}(?![-\\w])[^{}]*)\\{([^}]*)\\}`, "g"))]
    .map(m => ({ selector: m[1].trim(), body: m[2] }));
}

/** Does an author rule set `display` on the element itself (not a descendant)? */
function setsOwnDisplay(sel) {
  return rulesFor(sel).some(r => {
    if (!/display\s*:/.test(r.body)) return false;
    if (/\[hidden\]/.test(r.selector)) return false;      // that IS the guard
    // ".pkg-opts label" styles a child; only the element's own rules can beat
    // [hidden] on the element.
    return r.selector.split(",").some(one => {
      const t = one.trim();
      return t.endsWith(sel) || new RegExp(`${sel.replace(/[.#]/, m => "\\" + m)}(?![-\\w])[^\\s>+~]*$`).test(t);
    });
  });
}

/** The class list of the element carrying this id. */
function classesOf(id) {
  const tag = new RegExp(`<[a-z]+[^>]*\\bid="${id}"[^>]*>`).exec(html);
  if (!tag) return null;
  return (/class="([^"]+)"/.exec(tag[0]) || [, ""])[1].split(/\s+/).filter(Boolean);
}

// Everything the code hides at run time, plus everything that starts hidden in
// the markup — both rely on the same mechanism.
const toggled = new Set([...html.matchAll(/\$\("#([A-Za-z0-9_-]+)"\)\.hidden\s*=/g)].map(m => m[1]));
for (const m of html.matchAll(/<[a-z]+[^>]*\bid="([A-Za-z0-9_-]+)"[^>]*\shidden[\s>]/g)) toggled.add(m[1]);

check("the app does hide things this way", toggled.size > 0, `${toggled.size} elements`);

const dependents = [];
for (const id of toggled) {
  const classes = classesOf(id);
  if (classes === null) continue;                 // built in JS, not in markup
  const sels = [`#${id}`, ...classes.map(c => `.${c}`)];
  const styled = sels.filter(setsOwnDisplay);
  if (!styled.length) continue;                   // nothing to beat [hidden]
  const guarded = rulesFor(`#${id}`).some(r => /\[hidden\]/.test(r.selector)) ||
                  classes.some(c => rulesFor(`.${c}`).some(r => /\[hidden\]/.test(r.selector)));
  dependents.push({ id, styled, guarded });
}

/* The two known instances, named. If either stops depending on the global rule
   the test has stopped watching the thing it was written for. */
const known = ["scopeList", "libToolsRow"];
for (const id of known) {
  const d = dependents.find(x => x.id === id);
  check(`#${id} still sets display and is still hidden by attribute`, !!d,
        d ? d.styled.join(" ") : "gone or restyled — check this test still covers the class");
}

// The global rule is what makes all of these work. Every one of them is a
// regression waiting for the day someone deletes it as redundant.
const unguarded = dependents.filter(d => !d.guarded);
check("every display-styled element that gets hidden is covered", GLOBAL || !unguarded.length,
      unguarded.length
        ? `${unguarded.length} rely on the global rule alone: ` +
          unguarded.map(d => "#" + d.id).join(", ")
        : "");

console.log(`\n${failures ? `${failures} failed` : "all passed"} — ` +
            `${dependents.length} element${dependents.length === 1 ? "" : "s"} depend on the global rule\n`);
process.exit(failures ? 1 : 0);
