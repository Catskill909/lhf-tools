# Export — specification

**Status: BUILT** (4 Aug 2026). CSV / TSV / JSON export of the current result
set, plus the `/episode/<id>/transcript` route. Verified: 78 results on screen,
78 rows exported.

Still outstanding from this spec: column picker, `.zip` transcript bundle,
passage-level CSV, Dublin Core XML, citations, and storing the raw `.srt`.

**All of those are now folded into a larger plan.** `docs/export-dev.md` treats
the export as the client's complete backup of their Podbean archive — catalogue,
transcripts, artwork and audio — and works out why that has to be two exports
rather than one: the text weighs 5 MB and the audio 8–12 GB. Read it before
picking up any item in that list.

## The principle

**Export whatever is on screen.** Not a separate reporting area with its own
filters to learn — a button beside Sort that exports the current result set,
with the search and filters already applied. One endpoint, one control.

If Chris has filtered to "Power Hour, 2025, encores only, sorted by length,"
the export is exactly those rows in that order. What you see is what you get,
which is the only rule that doesn't need explaining.

---

## Spreadsheet format

No direct Google Sheets integration — no API, no OAuth, no credential to
maintain. Just a file that imports cleanly.

**CSV is that file.** Google Sheets imports it natively (File ▸ Import, or drag
it onto a sheet), as do Excel and Numbers. One format, universally understood,
nothing to configure.

What separates a CSV that imports *well* from one that imports badly is
entirely in the details:

| Detail | Why it matters here |
|---|---|
| **UTF-8 with BOM** | Titles contain "No Pasarán", "Workers' Revolt" with smart quotes. Without the BOM, Excel renders these as mojibake. Sheets is fine either way; Excel is not. |
| **ISO dates** (`2026-07-30`) | Parsed as real dates, so they sort and filter properly. `Jul 30 2026` imports as text and sorts alphabetically. |
| **Durations as plain numbers** (`54`, not `54 min`) | Sortable, and you can sum a column to total a run of segments. Header carries the unit: `duration_min`. |
| **RFC 4180 quoting** | Descriptions contain commas and quotes. Python's `csv` module handles this correctly by default — just don't hand-roll it. |
| **Booleans as `TRUE`/`FALSE`** | Sheets recognises these as booleans and gives you checkbox filtering. `1`/`0` imports as numbers. |
| **One row per episode** | Keeps it pivotable. Tags go in one semicolon-joined cell. |

Get those right and it drops into a sheet ready to filter and pivot, with no
cleanup. Get them wrong and someone spends twenty minutes fixing columns every
time they export.

**Optional convenience:** a "Copy for Sheets" button that puts TSV on the
clipboard, so a paste lands in columns without downloading anything. Nice to
have, same data, ~10 lines. Not a substitute for the file.

---

## Formats

Ordered by expected demand. All are stdlib — `csv`, `json`, `xml.etree`,
`zipfile`. **No packages needed**, which keeps the zero-install property that
has been quietly valuable throughout.

| Format | For | Effort |
|---|---|---|
| **CSV** | The default. Imports into Sheets, Excel, Numbers. | trivial |
| **Copy for Sheets** (TSV → clipboard) | Convenience — paste without downloading | small |
| **JSON** | Machine use; already the API shape | trivial |
| **Transcript bundle** (`.zip` of `.srt`) | Selected episodes' transcripts as files | small |
| **Dublin Core XML** | The library-standard metadata answer. The LC people will ask. | ~20 lines |
| **Citations** (plain text / BibTeX) | Quoting an episode, with timestamp | small |

---

## What we actually hold (verified)

Worth stating precisely, because it determines what an export can contain:

| | Stored? | Detail |
|---|---|---|
| Full transcript text | ✅ | ~49k chars for a 55-min episode; 882k words total |
| Timing markers | ✅ | Per passage — `start_sec` / `end_sec` |
| Cue-level precision | ❌ | ~1,970 source cues merged into ~140 passages (~25s each) for search quality |
| Speaker labels | ❌ | Not present in the source `.srt` |
| Audio | ❌ | Deliberate — URL only |

**This is why two URLs, not one.** They aren't redundant; they point at
different fidelities:

- **`source_url`** — Podbean's original `.srt`, full cue-level precision. What
  you'd want to regenerate subtitles or re-process from scratch.
- **`archive_url`** — our transcript view: cleaned, passage-timed, searchable,
  stable. What you'd want to read or cite.

Plus **`episode_url`** for the human-facing Podbean page.

> **Recommendation:** also store the raw `.srt` verbatim. At ~83 KB × 144 that's
> ~12 MB against a 33 MB database — trivial — and it removes the last dependency
> on Podbean's CDN. Right now, if those URLs rot we permanently lose cue-level
> precision. One column, a few lines in `transcripts.py`.

---

## Columns

Export carries **URLs and harvested metadata — not bulk text.** One row per
episode, so it behaves in a spreadsheet.

```
show · title · published · duration_min · is_encore
tags · reair_dates · has_transcript · transcript_words
episode_url    →  the Podbean page (for people)
source_url     →  the original .srt (full cue precision)
archive_url    →  our transcript view (cleaned, searchable)
audio_url      →  direct MP3
```

Two refinements worth building:

- **A column picker** — checkboxes, remembered in `localStorage`. Researchers
  and producers want different columns, and neither wants the other's.
- **`tags` as a single semicolon-joined cell.** One row per episode is what
  makes the export usable in a spreadsheet; one row per tag would explode 200
  rows into ~900 and break every pivot they'd want to build.

---

## Transcripts — the real decision

You're right that they're hard to manage inline. Concretely: 882,346 words. A
CSV with a transcript column would be ~5 MB, and Google Sheets caps a single
cell at **50,000 characters** — a 55-minute episode is roughly 50–55k, so the
longest episodes would be silently truncated. That's the worst outcome: it
looks like it worked.

**So: link by default, bundle on request, inline only when scoped.**

| Option | When | Note |
|---|---|---|
| **URL columns** *(default)* | Always | Both `source_url` and `archive_url` — different fidelities, both useful. |
| **`.zip` of `.srt` files** | Checkbox in the modal | `zipfile` is stdlib. Named `YYYY-MM-DD_show_title.srt`. Warn when the selection is large. |
| **Passage-level CSV** | Separate export | One row per passage: `episode, start_sec, end_sec, text`. The unit researchers actually want — it pivots. |
| **Inline transcript column** | Only when the result set is ≤ 20 episodes | Enable the option below that threshold and grey it out above, with the reason stated. Prevents the silent-truncation trap. |

A **transcript view route** (`/episode/<id>/transcript`) is a prerequisite for
the link option, and is worth having anyway — it's the page a researcher wants
when they've found a moment and need the surrounding context.

---

## The modal

Same construction as the help modal — that one already handles focus trapping,
`Esc`, and backdrop dismissal, so this is a second instance of a solved pattern
rather than new machinery.

```
┌─ Export ─────────────────────────────────────────┐
│ 107 episodes  ·  Power Hour · 2025               │
│ Matching what's on screen now.                   │
│                                                  │
│  ● Copy for Google Sheets      paste into a sheet│
│  ○ CSV file                                      │
│  ○ JSON                                          │
│  ○ Transcripts (.zip)                    144 files│
│  ○ Dublin Core XML                               │
│  ○ Citations                                     │
│                                                  │
│  Columns  [ Choose… ]                            │
│  ☐ Include transcript text   (≤20 episodes only) │
│                                                  │
│                        [ Cancel ]  [ Export ]    │
└──────────────────────────────────────────────────┘
```

Details that matter:

- **State the scope at the top.** "107 episodes · Power Hour · 2025" so nobody
  exports the whole archive thinking they'd filtered it.
- **Confirm after copying** — "107 rows copied. Paste into your sheet." A
  clipboard write with no feedback feels broken.
- **Name downloads properly** — `lhf-archive_2026-08-04_power-hour_2025.csv`.
  These end up in a shared Drive; `export(3).csv` helps nobody.
- **Cap it.** Above ~2,000 rows, warn before proceeding.

---

## API

One endpoint, taking the same query parameters as `/api/search` so there is no
second filtering path to keep in sync:

```
GET /api/export?format=tsv|csv|json|dc|cite&columns=…&transcripts=none|link|inline
                &q=&show=&year=&encore=&person=&sort=
```

Returns the file with an appropriate `Content-Type` and
`Content-Disposition: attachment`. The `.zip` bundle is a separate route since
it streams binary.

**Reuse `search()` directly** — do not reimplement the filtering. The whole
point is that export and screen can't drift apart.

---

## Build order

0. **Store the raw `.srt`** — ~12 MB, removes the last CDN dependency. Do this
   first; it's cheap and it's the only irreversible gap.
1. **CSV** — covers most real demand; an hour if the details above are respected
2. **Transcript view route** (`/episode/<id>/transcript`) — needed for links,
   and valuable on its own
3. **Column picker**
4. **`.zip` bundle**
5. **Dublin Core + citations** — do these before showing the LC people

Steps 1–2 are the ones worth doing before the client sees the app. The rest can
follow their feedback, which will probably tell you which columns they actually
want.
