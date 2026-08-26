# Filling the transcript gap — options and sizing

**Written 26 August 2026**, after the complete-archive backfill and the audit
that proved the gap is real rather than a scraping failure.

**Nothing here is decided or built.** It exists so the next conversation with
the client starts from measured numbers rather than a guess.

---

## The gap, measured

Audited against Podbean directly on 26 August 2026 — all 785 episode pages
re-fetched, not merely counted in our own database. Podbean offers 175
transcripts; we hold 174. The one exception is *MLK in Memphis*, whose
advertised `.srt` returns 404 from Podbean.

**No transcript exists anywhere before 2022.** The 611 without one are not
transcripts we failed to collect — they were never made.

| Scope | Episodes | Audio | Average | Over 60 min |
|---|---|---|---|---|
| **All 611 missing** | 611 | **25,661 min** (427.7 h) | 42 min | 38 |
| 2022–2024 | 352 | 13,748 min (229.1 h) | 39 min | 9 |
| Before 2022 | 259 | 11,914 min (198.6 h) | 46 min | 29 |

**Minutes are the unit that matters**, because transcription is priced per
minute of audio. Multiply by whatever rate applies and the quote falls out.

---

## Route 1 — Podbean's own transcription (check this first)

**Podbean auto-generates transcripts on its paid plans** and has an AI Content
Assistant that does the same on the Unlimited Audio plan and above. LHF may
already be paying for it.

**This is the cheapest route by a distance, and it needs nothing from us.**
Anything that lands on Podbean flows into the archive on its own — `ingest.py`
reads `<podcast:transcript>` from the feed, which is exactly how the current 174
arrived. The same is true of anything re-exported from Descript.

**So the first question is not "what would we charge" but "what does your plan
already cover".** That is what `docs/reply-backlog.md` asks.

---

## Route 2 — Gemini 3.5 Transcribe

Announced by Google on 26 August 2026. Worth recording because three of its
features line up unusually well with problems this project already has.

### Why it fits here specifically

**Custom vocabulary, up to 1,000 terms — the strongest reason.**
`docs/client-guide.md` admits in writing that *"names take some damage… good
enough to find things, not proofread documents"*, with Elise rendering as
"Lisa". We already hold **224 producer-hyperlinked entities** in the `mentions`
table — people, bands, museums, books, curated by the producers themselves.
That is a ready-made vocabulary list, and it targets the exact failure the
client has already been told about.

**Word-level timestamps.** Non-negotiable: `segments` needs `start_sec` and
`end_sec` or jump-to-moment does not work.

**Speaker diarization, up to 3 speakers.** Both programmes are two-host shows
plus a guest, which fits. This also touches open thread 2 in `HANDOFF.md` —
whether speakers were ever named — by making attribution obtainable without
the client answering.

**85+ languages** is irrelevant here. Noted only so nobody counts it as a
reason.

### Four things to decide before spending anything

**1. Use verbatim mode, not "smart".** Smart mode filters filler and resolves
spoken self-corrections. Lovely to read, wrong for a **search** archive: if
someone searches a phrase as it was actually said and the transcript has been
tidied, it will not match. The existing 174 are Descript-style verbatim, so a
smart-mode backfill would make search behave differently depending on which era
an episode came from — the worst kind of inconsistency, because it looks like a
search bug.

**2. The 1-hour request cap bites 38 episodes**, nearly all pre-2022. Splitting
audio and re-joining timestamps is real work, though not hard work. Budget for
it rather than discovering it.

**3. Audio logistics are the cost nobody quotes.** The Files API expects an
upload, and our audio lives on Podbean's CDN — deliberately, since **media never
touches our server** (`CLAUDE.md`). 611 episodes at roughly 50 MB each is about
**30 GB down and back up again**. Check whether a URI is accepted before
budgeting time for the transfer. If it is not, this is the one job that would
temporarily break the never-touch-the-media property, and that is worth doing
knowingly.

**4. The SDK is a pip package, and this project is stdlib-only.** A direct REST
call over `urllib` keeps the constraint intact. This is also a **one-time
script**, not part of the deployed app — so it can live outside `ingest/` and
never ship in the image. Decide that deliberately rather than
`pip install`-ing into the project.

### The test worth running before any quote

**One episode.** Pick a pre-2022 show carrying a name the current transcripts
mangle — an Elise, a César — feed the 224 tags as custom vocabulary, and read
what comes back.

That single run answers the only question that decides whether this is worth
doing: **does the custom vocabulary actually fix the names?** Everything else is
arithmetic. It costs about forty minutes of audio.

---

## What happens after transcripts arrive, whichever route

Nothing new needs building. `segments` is source-agnostic and
`episodes.transcript_source` already exists precisely so Descript, Podbean and
machine transcripts can coexist. Search, jump-to-moment, the transcript modal
and the clip editor all read from the same place.

**The one visible change would be in the interface:** the *Edit audio* button
now on every card is the fallback path for an episode with no transcript. Fill
the gap and the fast path — search a phrase, read to the moment, click —
replaces it everywhere. That framing is the argument for spending the money, and
it is how `docs/reply-backlog.md` puts it to the client.

---

## Costs previously quoted, and why they no longer apply

| Figure | Where it came from | Status |
|---|---|---|
| **"about $9 for all 53"** | 53 missing episodes, 200-episode archive | **Void.** The same job is 611 episodes / 25,661 minutes |
| **"$4.35 for the archive"** (topic extraction, a different job) | 200 episodes of text | **Understated ~4×** — the archive is now 785 |
| ~2¢ per new episode | per-episode, not per-archive | **Still valid** — depends on publishing rate, not history |

Both stale figures are corrected in `docs/client-guide.md`, which deliberately
quotes **no replacement number** for transcription: the total depends on a scope
decision only the client can make.
