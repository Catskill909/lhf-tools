# Export — specification

**Status:** specced, not built.

## The principle

**Export whatever is on screen.** Not a separate reporting area with its own
filters to learn — a button beside Sort that exports the current result set,
with the search and filters already applied. One endpoint, one control.

If Chris has filtered to "Power Hour, 2025, encores only, sorted by length,"
the export is exactly those rows in that order. What you see is what you get,
which is the only rule that doesn't need explaining.

---

## The Google Sheets question

You asked for a Sheets-style export. There are three ways, and the obvious one
is the worst:

| Approach | Reality |
|---|---|
| **Google Sheets API** | Needs a Google Cloud project, OAuth consent screen, a service account, and per-user authorisation. Weeks of faff and a permanent credential to maintain — for a feature that saves one paste. |
| **Download CSV → File ▸ Import** | Works, universally understood, but it's four steps and lands in a *new* sheet rather than where they're working. |
| **✅ "Copy for Sheets" — TSV to clipboard** | One click. Paste into any open sheet and it lands in columns correctly, because Sheets and Excel both parse tab-separated clipboard content natively. Zero auth, zero config, zero dependencies, works in Excel and Numbers too. |

**Recommendation: build the clipboard TSV option and label it "Copy for Google
Sheets."** It is genuinely the better product, not just the cheaper one — it
drops data into the sheet they already have open, which is what people actually
want. Offer CSV download alongside for anyone who wants a file.

The Sheets API only becomes worth it if they later want a *live* sheet that
stays in sync. That's a different feature and should be judged on its own.

---

## Formats

Ordered by expected demand. All are stdlib — `csv`, `json`, `xml.etree`,
`zipfile`. **No packages needed**, which keeps the zero-install property that
has been quietly valuable throughout.

| Format | For | Effort |
|---|---|---|
| **Copy for Sheets** (TSV → clipboard) | The default. Paste straight into a sheet. | small |
| **CSV** | A file for Excel, or for anyone who prefers files | trivial |
| **JSON** | Machine use; already the API shape | trivial |
| **Transcript bundle** (`.zip` of `.srt`) | Selected episodes' transcripts as files | small |
| **Dublin Core XML** | The library-standard metadata answer. The LC people will ask. | ~20 lines |
| **Citations** (plain text / BibTeX) | Quoting an episode, with timestamp | small |

---

## Columns

Default set, matching what the interface shows:

```
show · title · published · duration_min · episode_url · audio_url
is_encore · tags · reair_dates · transcript_url · has_transcript
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
| **`transcript_url` column** *(default)* | Always | Points at our own transcript view, not Podbean's CDN — ours is stable and readable in a browser. |
| **`.zip` of `.srt` files** | Checkbox in the modal | `zipfile` is stdlib. Named `YYYY-MM-DD_show_title.srt`. Warn when the selection is large. |
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

1. **Copy for Sheets + CSV** — covers most real demand in a couple of hours
2. **Transcript view route** (`/episode/<id>/transcript`) — needed for links,
   and valuable on its own
3. **Column picker**
4. **`.zip` bundle**
5. **Dublin Core + citations** — do these before showing the LC people

Steps 1–2 are the ones worth doing before the client sees the app. The rest can
follow their feedback, which will probably tell you which columns they actually
want.
