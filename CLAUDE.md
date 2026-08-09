# LHF Digital Asset Manager — working notes

Read `HANDOFF.md` first. This file is only the things that are easy to break
without knowing them.

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

## Traps that have already bitten this project

- **Episode ids are not stable.** `INTEGER PRIMARY KEY` assigned in ingest
  order, so rebuilding from an empty volume can give a number to a different
  episode. Peaks cached under `ep-<id>` once served a returning visitor another
  show's waveform. **Key on `guid` or the audio URL.** The `?ep=` share link
  still has this bug; see `docs/clip-library.md`.
- **`waveform.js` hardcodes a dark palette** that the light theme never
  overrides. Anything new drawn on a canvas must be passed explicit colours or
  it will be invisible in one theme. This has caused a real defect once.
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

**State captured at press time, then invalidated by a later edit.** Three
shipped from the audio editor alone — Repeat, play-after-moving-the-lead-handle,
and the 2s lead-in — and the third was only found by deliberately sweeping for
the shape.

Anything the transport remembers needs a test that **changes the selection
underneath it**. A test that only exercises the static case will pass and prove
nothing.

## Tests

```bash
node tests/test-waveform.mjs        # pure: peaks, snap-to-silence, rulers
node tests/test-update-prompt.mjs   # pure: the new-version reload prompt
node tests/test-zip.mjs             # pure: the archive packager
node tests/verify-clips.mjs 8000    # live: needs the server running + network
```

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
