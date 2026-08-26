# Which document to read, and when

**This file is injected into context at the start of every session.** It exists
because on 13 August 2026 a session answered a client-facing question about
episodes dropping off the feed without reading `client-guide.md`, which already
answered it — and got the framing wrong in a way that would have misled the
client. The documents were fine. Nothing routed to them.

---

## The rule

**Before answering anything about status, behaviour, history, or what to tell
the client: find the row below that matches and read that document first.**

The code tells you what the software *does*. It does not tell you what was
decided, what was promised, what was already measured, or what is deliberately
not built. Every one of those has been got wrong by reading the code alone.

**A question that sounds simple is not an exemption.** "Do we have the latest
episodes?" is a status question, and the answer was already written down.

---

## Routing table

| If the conversation touches… | Read first |
|---|---|
| **Anything the client sees, is told, or was promised** | `docs/client-guide.md` — the client-facing description, written for them. Check here **before** framing any client conversation. |
| **What was actually said to Harold, in his words and ours** | `docs/reply-descript.md` and `docs/reply-with-site.md` — real correspondence, not drafts. These are the promises of record; the guide describes the product, these describe the commitment. `docs/reply-backlog.md` is a **draft, not sent** — the back-catalogue announcement and the new URL. |
| **What's done, what's open, what's blocked, current status** | `HANDOFF.md` — the task box at the top, then *Open threads*. The four buckets are 🔥 DO / 🐞 FIX / ❓ ASK / 💭 NOTE. |
| **Feeds, ingest, the update loop, episodes leaving the feed, retention** | `HANDOFF.md` → *Keeping the archive current* and *Backups*; then `docs/feed-update-audit.md` for the measured update state. For the complete pre-feed backlog, read `docs/feed-backfill-investigation.md`. |
| **AI, topics, guests, interviewers, what it would cost** | `docs/ai-layer.md`. Nothing AI has ever been run. Costs are measured, not guessed. |
| **The controlled vocabulary / 34 terms / tag names** | `docs/ask-vocabulary.md` and `docs/ai-layer.md` → *A shared vocabulary*. Blocked on the client. |
| **Saved clips, the clip library, labels** | `docs/clip-library.md`. |
| **The audio editor, waveform, transport, marking, keyboard** | `docs/audio-editor-dev.md` — opens with a status summary. `docs/audio-editor-spec.md` is the spec it was built against (Phases 1–5, verified). |
| **Touchscreens, tablet editor support, phone warning, phone transcript** | `docs/touch-dev.md` — implementation status, support boundary and real-device acceptance. |
| **Export, the archive package, the zip** | `docs/export-dev.md`; `docs/export-spec.md` is the spec (built). |
| **Transcripts, segments, passages** | `docs/transcripts-plan.md`, `docs/transcript-modal.md`. |
| **Colour, theme, contrast, "make it darker", legibility** | `CLAUDE.md` → the palette traps. They are counter-intuitive and enforced by `tests/test-palette.mjs`. |
| **Deployment, Docker, Coolify, the volume, health checks** | `README.md` → *Coolify settings that matter*; `HANDOFF.md` → *Keeping the archive current*. |
| **Deployment storage configuration** | `cooify-volume-fix.md` — **deliberately not in git** (this repository is public). It lives in the working copy only. **Read it before changing anything under Coolify → Persistent Storage, and never summarise it into a tracked file.** |
| **Backups and recovery-source status** | `HANDOFF.md` → *Backups*; then `docs/feed-backfill-investigation.md`. |

---

## Things that are true and easy to get wrong

Stated here because each has already caused a wrong answer:

- **The archive keeps everything except the recordings.** Description,
  transcript, timestamps, tags, re-airs are permanent once read. Audio streams
  from Podbean and is never stored.
- **Falling off the feed does not delete the audio.** Measured 13 August 2026 on
  all three rotated-off episodes: still served, range requests still work, clips
  can still be cut. Deletion is a different event and remains unknown.
- **`episodes` rows are never deleted.** There is no `DELETE FROM episodes`
  anywhere. If production shows exactly 100 per show after a deploy, the volume
  is not holding — that is the standing check.
- **The update loop needs no environment variable.** It defaults to on.
- **Nothing in this project uses AI.** Everything is scraped or computed.

---

## Keeping this file honest

It is loaded every session, which makes a stale line here more expensive than a
stale line anywhere else — the same warning `CLAUDE.md` carries about itself.

Keep it to **routing and hard facts**, not status. Anything that changes weekly
belongs in `HANDOFF.md`. If a row here disagrees with the document it points at,
**the document wins and this row is a bug.**
