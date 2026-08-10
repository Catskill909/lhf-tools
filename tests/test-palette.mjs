/**
 * The palette: the laws a colour change has to obey in *both* themes.
 *
 * This exists because of a recurring, expensive failure — a colour change is
 * requested, made, deployed, and is invisible. It happened repeatedly on the
 * light stock and every time it was diagnosed by eye, badly.
 *
 * The mechanism is always the same. Contrast against the ground is not what
 * makes a change *visible*; separation from the thing next to it is. On a dark
 * ground the ink ramp is spread wide (a resting hairline sits at 1.9:1, so a
 * step up to 4.5:1 shouts). On paper the same tokens are compressed into the
 * dark end — --ink-3, --ink-2 and --ink are all 57+ L* below the stock — so
 * "make it darker" moves a value that no eye can separate from where it was.
 * That is why the answer on paper is ink coverage: a surface, an edge, weight.
 *
 * So the numbers here are in L* (CIE lightness), which is perceptually even,
 * as well as WCAG contrast, which is not. A rule stated in contrast ratio
 * alone would pass every one of the bugs this file exists to catch.
 *
 * Nothing is copied: the palette is lifted out of static/index.html at run
 * time, so this cannot pass while the shipped stylesheet says otherwise.
 *
 *   node tests/test-palette.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "static", "index.html"), "utf8");

let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}

/* ---------- lifting the palette out of the stylesheet ---------- */

/** The declarations of one `:root…{ }` block. No nesting inside these. */
function blockOf(selector) {
  const at = html.indexOf(selector);
  if (at < 0) {
    console.error(`Could not find "${selector}" in static/index.html.\n` +
                  "If the palette moved or was renamed, update the selectors here.");
    process.exit(1);
  }
  const open = html.indexOf("{", at);
  const close = html.indexOf("}", open);
  const out = new Map();
  for (const m of html.slice(open + 1, close).matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    out.set(`--${m[1]}`, m[2].trim());
  }
  return out;
}

const DARK = blockOf(":root {");
const LIGHT_ATTR = blockOf(':root[data-theme="light"] {');
const LIGHT_OS = blockOf(':root:not([data-theme="dark"]) {');

/** One level of var() indirection, resolved inside its own block. */
function value(block, token) {
  const raw = block.get(token);
  if (raw === undefined) return undefined;
  const ref = raw.match(/^var\(\s*(--[a-z0-9-]+)\s*\)$/);
  return ref ? block.get(ref[1]) : raw;
}

/* ---------- colour ---------- */

function parse(css) {
  const s = String(css).trim();
  if (s === "transparent" || s === "none") return [0, 0, 0, 0];
  let m = s.match(/^#([0-9a-f]{6})$/i);
  if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16),
                 parseInt(m[1].slice(4, 6), 16), 1];
  m = s.match(/^#([0-9a-f]{3})$/i);
  if (m) return [...m[1]].map(c => parseInt(c + c, 16)).concat(1);
  m = s.match(/^rgba?\(([^)]+)\)$/i);
  if (m) {
    const p = m[1].split(",").map(v => parseFloat(v.trim()));
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  }
  return null; // not a colour — --on-weight and friends
}

/** Alpha tokens are hairlines drawn *on* the stock, so flatten them onto it. */
function flatten(css, ground) {
  const c = parse(css);
  if (!c) return null;
  const g = parse(ground);
  return [0, 1, 2].map(i => c[3] * c[i] + (1 - c[3]) * g[i]);
}

const srgb = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
const Y = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);

function contrast(a, b) {
  const [hi, lo] = Y(a) >= Y(b) ? [Y(a), Y(b)] : [Y(b), Y(a)];
  return (hi + 0.05) / (lo + 0.05);
}

/** CIE lightness. Perceptually even, which contrast ratio is not. */
function lstar(rgb) {
  const y = Y(rgb);
  return y > 0.008856 ? 116 * Math.cbrt(y) - 16 : 903.3 * y;
}

const themes = [
  { name: "dark ", block: DARK },
  { name: "light", block: LIGHT_ATTR },
];
const ground = t => value(t.block, "--paper");
const flat = (t, token) => flatten(value(t.block, token), ground(t));

/* ---------- 1. the three blocks have to agree ---------- */
/* A token defined in one theme and not the other resolves to nothing at all:
   `background: var(--on-bg)` with --on-bg missing is not a fallback, it is a
   dropped declaration. Silent, and only in the theme nobody screenshotted. */

console.log("palette blocks");

const attrKeys = [...LIGHT_ATTR.keys()].sort();
const osKeys = [...LIGHT_OS.keys()].sort();
const darkKeys = [...DARK.keys()].sort();

check("every dark token has a light counterpart",
      darkKeys.every(k => LIGHT_ATTR.has(k)),
      darkKeys.filter(k => !LIGHT_ATTR.has(k)).join(", ") || `${darkKeys.length} tokens`);
check("and no light token is missing from dark",
      attrKeys.every(k => DARK.has(k)),
      attrKeys.filter(k => !DARK.has(k)).join(", ") || `${attrKeys.length} tokens`);
check("the OS-light block lists exactly the same tokens",
      attrKeys.join() === osKeys.join(),
      attrKeys.filter(k => !LIGHT_OS.has(k)).concat(osKeys.filter(k => !LIGHT_ATTR.has(k))).join(", ") || "same set");
check("the two light blocks agree value for value",
      attrKeys.every(k => LIGHT_ATTR.get(k) === LIGHT_OS.get(k)),
      attrKeys.filter(k => LIGHT_ATTR.get(k) !== LIGHT_OS.get(k)).join(", ") || "identical");

/* ---------- 2. text stays legible in both themes ---------- */

console.log("\nlegibility against the stock");

const TEXT_FLOOR = { "--ink": 7, "--ink-2": 4.5, "--ink-3": 4.5, "--spot-ink": 4.5,
                     "--field": 4.5 };
for (const t of themes) {
  for (const [token, floor] of Object.entries(TEXT_FLOOR)) {
    const r = contrast(flat(t, token), parse(ground(t)));
    check(`${t.name}  ${token} carries text`, r >= floor,
          `${r.toFixed(2)}:1, floor ${floor}:1`);
  }
}

/* ---------- 3. the ink ramp has to be a ramp ---------- */
/* Adjacent steps that no eye can separate are the reason "darken it one step"
   comes back looking like nothing happened. */

console.log("\nink ramp separation");

const RAMP = ["--ink-3", "--ink-2", "--ink"];
const RAMP_MIN = 6; // L*
for (const t of themes) {
  const steps = RAMP.map(k => lstar(flat(t, k)));
  for (let i = 1; i < steps.length; i++) {
    const d = Math.abs(steps[i] - steps[i - 1]);
    check(`${t.name}  ${RAMP[i - 1]} → ${RAMP[i]} is a visible step`, d >= RAMP_MIN,
          `${d.toFixed(1)} L*, floor ${RAMP_MIN}`);
  }
  const away = steps.every((v, i) => i === 0 ||
    Math.sign(v - steps[i - 1]) === Math.sign(steps[1] - steps[0]));
  check(`${t.name}  the ramp runs one way`, away,
        steps.map(v => v.toFixed(0)).join(" → ") + " L*");
}

/* ---------- 4. "on" has to look different from "off" — in both themes ------ */
/* This is the law the reported bug broke. A state that announces itself by
   stepping the border up the ink ramp works on a dark ground and cannot work
   on paper, because paper has no headroom above a resting hairline. The
   measure is deliberately max(edge, fill): a theme is free to answer with
   whichever it has, and light answers with the surface. */

console.log("\nselected vs resting");

/* Floors in L*, per channel, because the channels are not equally readable.
   A step across a filled block or a 2px edge is compared against a neighbour
   an inch away; a step in running text has to be *found*, among many lines
   that look almost the same, in thin strokes. So text is held to a wider gap.

   These numbers are calibrated against what has actually failed here, not
   chosen: the transcript shipped at 15.8 L* of text separation and could not
   be seen, while 25.4 and 29.7 can be. A single floor loose enough to admit
   an edge at 12 admits the transcript bug too — which this file's own
   regression section proved, on the first run, by passing when it should have
   failed. */
const EMPHASIS_MIN = { text: 20, edge: 12, fill: 12 };
const EMPHASIS_BALANCE = 0.6; // weakest theme, as a fraction of the strongest

/* Each state a user has to be able to *see*, as the pair of tokens that
   carries it. A theme may answer on any channel it likes — the ink of the
   text, the edge, or the surface behind it — so the score is the widest of
   them. That is the whole point: dark answers with luminance, paper answers
   with coverage, and neither is asked to imitate the other. */
const STATES = [
  { name: "a selected filter",
    rest: { edge: "--rule-hard", fill: "--paper" },
    on:   { edge: "--on-edge",   fill: "--on-bg" } },
  { name: "the transcript line being played",
    rest: { text: "--field" },
    on:   { text: "--ink" } },
];

/** How far apart the resting and active forms look, per channel. A state is
 *  carried by whichever channel does best against *its own* floor. */
function emphasis(t, state) {
  const gaps = {};
  for (const channel of ["text", "edge", "fill"]) {
    const a = state.rest[channel], b = state.on[channel];
    if (!a || !b) continue;
    gaps[channel] = Math.abs(lstar(flat(t, a)) - lstar(flat(t, b)));
  }
  let carried = null, score = 0;
  for (const [channel, gap] of Object.entries(gaps)) {
    if (gap / EMPHASIS_MIN[channel] > score) {
      score = gap / EMPHASIS_MIN[channel];
      carried = channel;
    }
  }
  return { gaps, carried, score };
}

const detail = e => Object.entries(e.gaps).map(([k, v]) =>
  `${k} ${v.toFixed(1)}/${EMPHASIS_MIN[k]}`).join(" ");

for (const state of STATES) {
  const seen = [];
  for (const t of themes) {
    const e = emphasis(t, state);
    seen.push(e.score);
    check(`${t.name}  ${state.name} reads as active`, e.score >= 1,
          `${detail(e)} L*` + (e.carried ? `, carried by the ${e.carried}` : ""));
  }
  check("       neither theme is the poor relation",
        Math.min(...seen) >= EMPHASIS_BALANCE * Math.max(...seen),
        `${Math.min(...seen).toFixed(2)}x vs ${Math.max(...seen).toFixed(2)}x its floor`);
}

check("weight is declared per theme, not assumed",
      Number(value(LIGHT_ATTR, "--on-weight")) >= Number(value(DARK, "--on-weight")),
      `dark ${value(DARK, "--on-weight")}, light ${value(LIGHT_ATTR, "--on-weight")}`);

/* ---------- 5. hairline tokens are not surfaces ---------- */
/* --rule and --rule-hard carry an alpha chosen so that a 1px line prints, and
   on the light stock that alpha has to be much higher — 0.42 against 0.11 —
   for the line to be visible at all. Behind a line of text the same token is
   therefore a grey slab in one theme and a whisper in the other. It shipped
   once, on the clip title's hover.
   The rule is structural rather than numeric: a hairline token may fill a box
   only when that box says it is a line. --wash exists for everything else. */

console.log("\nhairline tokens vs surfaces");

const styleStart = html.indexOf("<style>");
const styleEnd = html.indexOf("</style>", styleStart);
const css = html.slice(styleStart, styleEnd);

const LINE_MAX = 4; // px — above this it is an area, not a rule

function hairlineFills(stylesheet) {
  const found = [];
  for (const m of stylesheet.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const [, selector, body] = m;
    if (!/background(-color)?:\s*var\(\s*--rule(-hard)?\s*\)/.test(body)) continue;
    const h = body.match(/height:\s*([\d.]+)px/);
    if (!h || parseFloat(h[1]) > LINE_MAX) found.push(selector.trim().split("\n").pop().trim());
  }
  return found;
}

const offenders = hairlineFills(css);
check("no hairline token fills an area", offenders.length === 0,
      offenders.join(" | ") || `all uses declare height <= ${LINE_MAX}px`);

check("--wash is a surface in both themes, and the same one",
      (() => {
        const d = themes.map(t => Math.abs(lstar(flat(t, "--wash")) - lstar(parse(ground(t)))));
        return Math.min(...d) >= 4 && Math.min(...d) >= 0.6 * Math.max(...d);
      })(),
      themes.map(t =>
        `${t.name.trim()} ${Math.abs(lstar(flat(t, "--wash")) - lstar(parse(ground(t)))).toFixed(1)}`
      ).join(" / ") + " L* off the stock");

/* ---------- 6. the law has teeth ---------- */
/* The shipped bug, reconstructed: on paper, "on" was the border stepping from
   --rule-hard to --ink-3 with no surface. If this law cannot see that, it is
   decoration — so assert that it fails, rather than trusting that it would. */

console.log("\nthe law catches the bug that prompted it");

/* Bug one: the selected filter chip, whose "on" was the border stepping from
   --rule-hard to --ink-3 with no surface behind it. */
const chipAsShipped = new Map(LIGHT_ATTR);
chipAsShipped.set("--on-edge", LIGHT_ATTR.get("--ink-3"));
chipAsShipped.set("--on-bg", "transparent");
const bug1 = emphasis({ block: chipAsShipped }, STATES[0]);
check("the old selected-chip treatment is rejected on paper", bug1.score < 1,
      `${detail(bug1)} L*`);
check("and the same treatment on the dark ground is not",
      emphasis(themes[0], STATES[0]).score >= 1,
      `${detail(emphasis(themes[0], STATES[0]))} L*`);

/* Bug two: the transcript, whose field was --ink-2 in both themes, so the
   playing line rose 29.7 L* on the dark ground and 15.8 on paper — between
   two inks that both read as black. */
const txAsShipped = new Map(LIGHT_ATTR);
txAsShipped.set("--field", LIGHT_ATTR.get("--ink-2"));
const bug2 = emphasis({ block: txAsShipped }, STATES[1]);
check("the old transcript field is rejected on paper", bug2.score < 1,
      `${detail(bug2)} L*`);
check("and the same field on the dark ground is not",
      emphasis(themes[0], STATES[1]).score >= 1,
      `${detail(emphasis(themes[0], STATES[1]))} L*`);

/* Bug three: the clip title's hover, which filled the whole title box with
   --rule — 0.11 white on the dark ground, 0.42 black on paper. */
const asShippedCss = css.replace(
  /(\.cliprow \.cr-title:hover \{[^{}]*background:\s*var\()--wash(\))/,
  "$1--rule$2");
const bug3 = hairlineFills(asShippedCss);
check("the old clip-title hover is caught", bug3.length === 1,
      bug3.join(" | ") || "not caught — the substitution missed, so this proves nothing");

console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
