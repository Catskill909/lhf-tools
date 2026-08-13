# LHF Digital Asset Manager — working notes

Read `HANDOFF.md` first. This file is only the things that are easy to break
without knowing them.

> **If this file disagrees with the code, the code is right — and this file is a
> bug.** It is loaded automatically and therefore trusted more than the other
> documents, which makes a stale line here more expensive than a stale line
> anywhere else. Six claims elsewhere in this repo were true when written and
> quietly stopped being true; assume the same rot applies here. Keep it to
> constraints and traps, which change slowly. Feature status belongs in
> `HANDOFF.md`.

## How to report work here

**These documents record reasoning, not tasks.** That is deliberate and worth
keeping — it is what makes them useful to someone arriving cold. It also means
that read end to end they look like a backlog of a hundred unfinished things.
They are not one. Parked ideas, rejected options, known trade-offs and
brainstorm seeds all sit in the same prose as real work.

So everything actionable goes in exactly **four buckets**, and nowhere else:

| | Means | Test for it |
|---|---|---|
| 🔥 **DO** | Something bad happens if it is ignored | Name the downside. If you can't, it isn't a DO. |
| 🐞 **FIX** | Genuinely broken, reproducible, not urgent | You can describe the steps to see it fail. |
| ❓ **ASK** | Blocked on someone else's decision | No amount of work here unblocks it. |
| 💭 **NOTE** | Observation, idea, trade-off | **Never a task.** Nobody has to do anything. |

**The rule that does the actual work: a NOTE must never appear in a list with
the other three.** Mixing them is what makes a finished project feel unfinished,
and it is the single most common way these documents mislead their reader.

- **One place holds the actionable ones:** the box at the top of `HANDOFF.md`.
  If it is not in that box, it is not a task. Everything else in these documents
  is thinking.
- **When reporting to the user**, lead with 🔥, then 🐞, then ❓. NOTEs go last,
  in their own section, marked as requiring nothing. **Do not tack caveats onto
  the end of good news** — "done, but worth knowing…" makes completed work read
  as incomplete. Say it is done, then start a separate section.
- **A gap is not a task.** "No automated tests for X" and "feature Y was
  designed but not built" are NOTEs. They become FIXes only when something
  actually breaks, and DOs only when there is a downside to name.

## Hard constraints

- **Stdlib only. No pip, no venv, no build step, no lockfile.** The image is the
  Python interpreter plus this repo, and the front end is one HTML file plus
  three ES modules. This is why a redeploy cannot break in six interesting ways.
  Adding a dependency is a decision, not a convenience.
- **Clip export is a byte copy of MP3 frames** — bit-identical to the broadcast
  audio, and a headline client guarantee. **Fades, normalise and gain are
  therefore impossible** without giving it up. Flag them; never quietly
  implement them.
- **Media never touches our server.** Audio goes from Podbean's CDN straight to
  the browser. A 12 GB archive through a small VPS is the one change that would
  break the lightweight property this project keeps deliberately.
- **`serve.py` is GET-only and has no authentication**, and the deployment is
  public. That is correct while everything served is already-published
  material. **The first write endpoint is a security decision**, not a feature
  increment — and it is the same decision the AI layer and a shared clip
  library are both waiting on.
- **The browser persists exactly two things, and both rebuild themselves**:
  `localStorage["lhf-theme"]` and the IndexedDB peaks cache. Nothing else — the
  update prompt's dismissal is an in-memory variable, not storage. **Anything
  new that persists is the first user data this application can actually lose**,
  so it has to say where it lives, in the interface, at the point the user forms
  the belief. `docs/clip-library.md` → *What lives where* is the boundary, and
  `docs/client-guide.md` states it to the client.

## Traps that have already bitten this project

- **Episode ids are not stable.** `INTEGER PRIMARY KEY` assigned in ingest
  order, so rebuilding from an empty volume can give a number to a different
  episode. Peaks cached under `ep-<id>` once served a returning visitor another
  show's waveform. **Key on `guid` or the audio URL.** Both known instances are
  fixed — the peaks cache keys on the audio URL, and `?ep=` links carry
  `g=sha1(guid)[:8]`, which the server believes over the id. **Anything new that
  names an episode by row id is a third instance**, so don't.
- **`waveform.js` hardcodes a dark palette** that the light theme never
  overrides. Anything new drawn on a canvas must be passed explicit colours or
  it will be invisible in one theme. This has caused a real defect once.
- **"Make it darker" does nothing on the light stock, and that is not a bug in
  the request.** `--ink-3`, `--ink-2` and `--ink` are 9 and 16 L* apart but all
  of them sit 57+ L* below the paper, so on light they all read as "a dark
  line" and stepping between them is invisible. On the dark ground the same
  three are spread 53 → 64 → 93 L*, which is why the identical change is
  obvious there. **Emphasis on paper is ink coverage — a surface, a full-ink
  edge, weight — not a darker hairline.** In running text, where you cannot go
  blacker than black, the answer inverts again: **the field recedes** rather
  than the current line rising. Both per-theme answers live in the palette —
  `--on-bg` / `--on-edge` / `--on-weight` for controls, `--field` for a body of
  text with one line current — so use those rather than deciding it at the call
  site. `tests/test-palette.mjs` enforces it, in L* rather than contrast ratio:
  a rule stated in contrast ratio alone passes every bug this class has
  produced. Its floors are per channel and calibrated against real failures —
  text needs a wider gap than an edge, because it has to be *found*.
- **Emphasis has a direction, and gold points the wrong way on paper.**
  `--gold` is *lighter* than the copy around it, which on the dark ground means
  it advances and on paper means it recedes — the same token doing opposite
  jobs. "RAN 3 TIMES" sat 16 L* toward the stock from its own copy, which is
  what "washed out" always turns out to mean. A label may never lie closer to
  its ground than the copy it emphasises. Gold as small text is `--gold-text`
  (deep bronze on paper), and the gold *identity* moves to the rule and
  `--gold-wash` behind the notice, where an area of it can actually be seen.
- **Hue does not carry at small sizes — lightness does.** The encore badge
  shipped as a gold outline that measured 40 ΔE from the metadata beside it and
  was still invisible on paper, because only 6 L* of that was lightness. At
  0.63rem, uppercase and letterspaced, the glance is luminance first. On the
  dark ground the same gold is also 19 L* brighter than its neighbours, which
  is why it works there and only there. The badge is now `--gold-bg` /
  `--gold-ink`: an outline in dark, an inverted stamp on paper. The test scores
  every channel on ΔE **and** L*, and takes the weaker — so a colour that moves
  in hue alone cannot pass.
- **`--rule` and `--rule-hard` are hairlines, never surfaces.** Their alpha is
  set so a 1px line prints, which on the light stock means 0.42 against dark's
  0.11 — so the same token behind a line of text is a whisper in one theme and
  a grey slab in the other. It shipped once, on the clip title's hover. Use
  **`--wash`** for a tint over an area; it is tuned as a surface and lands ~11
  L* off the stock in both themes. `test-palette.mjs` enforces this
  structurally: a rule token may fill a box only if that box declares a
  `height` of 4px or less.
- **`el.hidden = true` loses to any class that sets `display`.** The browser's
  `[hidden]` rule is a user-agent rule, so `display: flex` on the component
  beats it and the element stays fully visible while JS reports it hidden. It
  shipped twice — the export dialogue drew a scope choice it had just decided
  not to offer, and the clip library's tools row ignored its own "fewer than
  six clips" rule. One global `[hidden] { display: none !important; }` now
  covers everything; `tests/test-hidden.mjs` exists to stop it being deleted as
  redundant. The per-component `.foo[hidden]` rules further down the stylesheet
  predate it — **don't add more of them.**
- **The peaks cache is versioned (`v: 2`).** Change the format without bumping
  it and returning users get old data read as new — a silently wrong waveform.
- **`schema.sql` is all `CREATE TABLE IF NOT EXISTS`**, so it does nothing to a
  database that already exists — which every deployed one does. New columns
  need a `PRAGMA table_info` guarded migration in `ingest/ingest.py`.
- **The archive is no longer disposable.** Both shows sit at Podbean's
  100-episode feed cap, so the database is becoming the only reachable copy of
  anything that rotates out. "Just re-scrape it" stopped being true in August
  2026.

## The recurring bug class

**State captured at press time, then invalidated by a later edit.** Four have
shipped from the audio editor alone — Repeat, play-after-moving-the-lead-handle,
the 2s lead-in, and `[` / `]` moving the playhead while leaving the resume range
behind it. Two of the four were found only by deliberately sweeping for the
shape, which is the argument for sweeping.

**Every hand-driven playhead move now goes through `movePlayhead`**, which
carries the range along via `resumeRange` in `waveform.js`. A new control that
moves the playhead must use it rather than assigning `clip.playhead` — that
assignment is what the fourth instance looked like.

Anything the transport remembers needs a test that **changes the selection
underneath it**. A test that only exercises the static case will pass and prove
nothing — the shipped `[` / `]` bug passes any test that moves the playhead
*inside* the selection, because the stale range was usually the selection.

## Tests

```bash
node tests/test-waveform.mjs        # pure: peaks, snap-to-silence, rulers
node tests/test-update-prompt.mjs   # pure: the new-version reload prompt
node tests/test-zip.mjs             # pure: the archive packager
node tests/test-clips.mjs           # pure: the saved-clip store + labels
node tests/test-palette.mjs         # pure: both themes' colour laws, in L*
node tests/test-hidden.mjs          # pure: `hidden` actually hides
node tests/verify-clips.mjs 8000    # live: needs the server running + network
```

`test-clips.mjs` shims `localStorage` onto `globalThis` and imports the real
module. **Adding a front-end module means adding it to `names` in `serve.py`'s
`/api/version`** — nothing derives that tuple, and a module missing from it can
never trigger the reload prompt. `zip.js` was missing from the day it shipped.

`verify-clips.mjs` is the one that checks the exported bytes are still the
broadcast audio. Run it before any commit that goes near `mp3cut.js` — and if
it ever fails during unrelated work, something has reached into the cutting
code that should not have.

The browser suites for the audio editor are **not committed** — they need
Chrome, a server and the network. Their coverage is listed at the end of
`docs/audio-editor-dev.md` so it can be rebuilt.

## Where the thinking lives

| | |
|---|---|
| `HANDOFF.md` | Everything: state, deployment, backups, open threads |
| `docs/audio-editor-dev.md` | The editor rebuild — opens with a status summary |
| `docs/export-dev.md` | Export as the client's full archive package |
| `docs/clip-library.md` | Saving clips — designed, not built |
| `docs/ai-layer.md` | Written, never run, blocked on key + admin + auth |

These documents record **reasoning, not just decisions** — including the ideas
that were rejected and why. Keep that when editing them, and mark historical
sections as historical rather than deleting them.
