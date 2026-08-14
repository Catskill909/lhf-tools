/* clips.js — the saved-clip store.
 *
 * The whole point of this module is that it is the ONLY thing that knows where
 * clips are kept. Every part of the UI goes through list/add/update/remove, so
 * swapping localStorage for a server later touches this file and nothing else.
 * See docs/clip-library.md → "Four decisions that make later features cheap".
 *
 * Keyed on the audio URL, never the episode row id. Ids are INTEGER PRIMARY KEY
 * assigned in ingest order, so rebuilding the volume can hand the same number to
 * a different episode — the trap that once served a returning visitor another
 * show's waveform. The URL identifies the recording itself.
 */

const KEY = "lhf-clips";
const V = 1;

/* A stored record:
 *   { id, url, epId, title, show, date, in, out, createdAt, labels[] }
 * ~150 bytes plus labels. A thousand clips is under 200 KB against
 * localStorage's ~5 MB, which is why this isn't in IndexedDB.
 */

function read() {
  let raw;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    // Safari in private mode throws on localStorage access rather than
    // returning null. An empty library is the honest answer — the alternative
    // is the whole page failing to open over a feature nobody has used yet.
    return [];
  }
  if (!raw) return [];
  let box;
  try {
    box = JSON.parse(raw);
  } catch {
    // Hand-edited or truncated storage. Refusing to parse it is right; throwing
    // it away silently is not, so leave it in place and start empty. A later
    // write will replace it.
    return [];
  }
  // Version mismatch is a cache miss, not a migration. Same rule as the peaks
  // cache: old data read as new is a silently wrong result.
  if (!box || box.v !== V || !Array.isArray(box.clips)) return [];
  return box.clips;
}

function write(clips) {
  // Throws on quota exhaustion and in private-browsing modes. Callers must
  // catch and tell the user the clip was NOT saved — the one thing worse than
  // failing to save is reporting success and losing the work.
  localStorage.setItem(KEY, JSON.stringify({ v: V, clips }));
}

export function list() {
  return read();
}

export function count() {
  return read().length;
}

export function add(rec) {
  const clips = read();
  const saved = {
    id: "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    url: rec.url,
    epId: rec.epId ?? null,
    title: rec.title || "",
    show: rec.show || "",
    date: rec.date || "",
    in: rec.in,
    out: rec.out,
    createdAt: Date.now(),
    labels: Array.isArray(rec.labels) ? rec.labels.slice() : [],
  };
  clips.unshift(saved);
  write(clips);
  return saved;
}

export function update(id, patch) {
  const clips = read();
  const i = clips.findIndex(c => c.id === id);
  if (i < 0) return null;
  clips[i] = { ...clips[i], ...patch };
  write(clips);
  return clips[i];
}

export function remove(id) {
  const clips = read();
  const i = clips.findIndex(c => c.id === id);
  if (i < 0) return null;
  const [gone] = clips.splice(i, 1);
  write(clips);
  return gone;
}

/* Undo restores at the original position rather than the top, so a removal you
 * take back doesn't quietly reorder the list. */
export function restore(rec, index) {
  const clips = read();
  clips.splice(Math.min(index, clips.length), 0, rec);
  write(clips);
  return rec;
}

export function indexOf(id) {
  return read().findIndex(c => c.id === id);
}

/* ---------------------------------------------------------------- labels */

/* There is no label registry, deliberately — the set of labels that exists is
 * whatever the clips currently carry. Nothing to create, rename or garbage
 * collect, and removing the last use removes the label by construction. */
export function labelCounts(clips = read()) {
  const m = new Map();
  for (const c of clips) for (const l of c.labels || []) m.set(l, (m.get(l) || 0) + 1);
  return [...m.entries()].map(([label, n]) => ({ label, n }))
    .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label));
}

export function labelNames(clips = read()) {
  return labelCounts(clips).map(l => l.label);
}

/* "promo" must resolve to an existing "Promo" rather than becoming a second
 * label beside it. A library where the same word exists twice in different
 * cases stops being usable within a fortnight, and no later tidy-up fixes the
 * muscle memory. First spelling wins and stays canonical. */
export function canonicalLabel(input, clips = read()) {
  const want = String(input || "").trim();
  if (!want) return null;
  const found = labelNames(clips).find(l => l.toLowerCase() === want.toLowerCase());
  return found || want;
}

/* --------------------------------------------------------------- search */

/* The archive search lives in SQLite FTS5; saved clips live only in this
 * browser, so they cannot use that index. This small evaluator deliberately
 * keeps the same everyday language: bare words are ANDed, the last word is a
 * prefix while it is being typed, and expert syntax adds phrases, boolean
 * operators, parentheses and explicit `*` prefixes. Clip-specific fields are
 * title:, show:, label: and date:.
 *
 * It returns a score as well as a clip. That lets the UI offer Best match
 * without teaching the storage module anything about presentation or sort
 * menus. Title matches carry the most weight, then labels, show and date.
 */
const SEARCH_FIELDS = ["title", "label", "show", "date"];
const SEARCH_WEIGHT = { title: 8, label: 5, show: 3, date: 1 };
const SEARCH_EXPERT = /(?:^|\s)(?:AND|OR|NOT)(?=\s|$)|[()"*]|\b(?:title|show|labels?|date)\s*:/;

const foldSearch = value => String(value || "")
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .replace(/[’‘]/g, "'")
  .replace(/[‐‑‒–—]/g, "-")
  .toLowerCase();

// Match SQLite's unicode61 shape: punctuation separates words. In particular,
// `people hist` must find `The People's Historian`, not treat `people's` as an
// indivisible token that no ordinary query would ever match.
const searchWords = value => foldSearch(value).match(/[\p{L}\p{N}_]+/gu) || [];

function searchDoc(clip) {
  return {
    title: foldSearch(clip.title),
    show: foldSearch(clip.show),
    date: foldSearch(clip.date),
    label: foldSearch((clip.labels || []).join(" ")),
  };
}

function searchTokens(raw) {
  const out = [];
  for (let i = 0; i < raw.length;) {
    if (/\s/.test(raw[i])) { i++; continue; }
    if (raw[i] === "(") { out.push({ type: "(" }); i++; continue; }
    if (raw[i] === ")") { out.push({ type: ")" }); i++; continue; }
    if (raw[i] === '"') {
      let j = ++i;
      while (j < raw.length && raw[j] !== '"') j++;
      out.push({ type: "term", value: raw.slice(i, j), phrase: true });
      i = j < raw.length ? j + 1 : j;
      continue;
    }
    let j = i;
    while (j < raw.length && !/[\s()"]/.test(raw[j])) j++;
    const value = raw.slice(i, j);
    out.push(/^(?:AND|OR|NOT)$/.test(value)
      ? { type: value }
      : { type: "term", value });
    i = j;
  }
  return out;
}

function searchTree(raw) {
  const query = String(raw || "").trim();
  if (!query) return null;

  // Plain typing follows the front page: earlier words are exact and the word
  // in progress is a prefix, so `people hist` finds `People's Historian`.
  if (!SEARCH_EXPERT.test(query)) {
    const words = searchWords(query);
    return words.map((value, i) => ({
      type: "term", value, prefix: i === words.length - 1,
    })).reduce((left, right) => left ? { type: "AND", left, right } : right, null);
  }

  const tokens = searchTokens(query);
  let at = 0;
  const peek = () => tokens[at];
  const take = () => tokens[at++];

  function primary() {
    if (!peek()) return null;
    if (peek().type === "(") {
      take();
      const node = orExpr();
      if (peek()?.type === ")") take();
      return node;
    }
    const token = take();
    if (token.type !== "term") return null;
    let { value, phrase = false } = token;
    let field = null;
    const scoped = value.match(/^(title|show|labels?|date):(.*)$/i);
    if (scoped) {
      field = scoped[1].toLowerCase().replace("labels", "label");
      value = scoped[2];
      if (!value && peek()?.type === "term") {
        const next = take();
        value = next.value;
        phrase = !!next.phrase;
      }
    }
    const prefix = !phrase && value.endsWith("*");
    if (prefix) value = value.slice(0, -1);
    return { type: "term", value, phrase, prefix, field };
  }

  function unary() {
    if (peek()?.type === "NOT") { take(); return { type: "NOT", child: unary() }; }
    return primary();
  }

  function andExpr() {
    let left = unary();
    while (peek() && peek().type !== "OR" && peek().type !== ")") {
      if (peek().type === "AND") take();
      const right = unary();
      if (!right) break;
      left = left ? { type: "AND", left, right } : right;
    }
    return left;
  }

  function orExpr() {
    let left = andExpr();
    while (peek()?.type === "OR") {
      take();
      const right = andExpr();
      if (right) left = left ? { type: "OR", left, right } : right;
    }
    return left;
  }

  return orExpr();
}

function scoreTerm(doc, node) {
  const needle = foldSearch(node.value);
  if (!needle) return { match: true, score: 0 };
  const fields = node.field && SEARCH_FIELDS.includes(node.field)
    ? [node.field]
    : SEARCH_FIELDS;
  let score = 0;
  for (const field of fields) {
    const hay = doc[field];
    const match = node.phrase
      ? hay.includes(needle)
      : searchWords(hay).some(word => node.prefix ? word.startsWith(needle) : word === needle);
    if (!match) continue;
    score += SEARCH_WEIGHT[field];
    if (field === "title" && hay === needle) score += 12;
  }
  return { match: score > 0, score };
}

function scoreTree(doc, node) {
  if (!node) return { match: true, score: 0 };
  if (node.type === "term") return scoreTerm(doc, node);
  if (node.type === "NOT") {
    const child = scoreTree(doc, node.child);
    return { match: !child.match, score: 0 };
  }
  const left = scoreTree(doc, node.left);
  const right = scoreTree(doc, node.right);
  if (node.type === "AND") {
    return { match: left.match && right.match, score: left.score + right.score };
  }
  return { match: left.match || right.match, score: Math.max(left.score, right.score) };
}

export function search(clips, query) {
  const tree = searchTree(query);
  return clips.map((clip, index) => {
    const hit = scoreTree(searchDoc(clip), tree);
    return { clip, score: hit.score, index, match: hit.match };
  }).filter(row => row.match);
}

/* ----------------------------------------------------------------- dates */

/* Grouping is derived from createdAt, never stored. "Last week" is the last
 * seven days rather than the previous calendar week — a producer thinking
 * "I saved that a few days ago" means elapsed days. */
export function groupOf(ts, now = Date.now()) {
  const d = new Date(ts);
  const t = new Date(now);
  const midnight = new Date(t.getFullYear(), t.getMonth(), t.getDate()).getTime();
  if (ts >= midnight) return "Today";
  if (ts >= midnight - 864e5) return "Yesterday";
  if (ts >= midnight - 7 * 864e5) return "Last week";
  return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}
