# Transcripts — phased plan

> **Status: Phases 1–4 shipped.** 144 transcripts, 14,937 passages, 882,346
> words, with jump-to-timestamp playback. Phases 5–6 remain: the 55-episode
> gap (~$9.52) and AI enrichment over the transcripts (~$7).

**The finding that reframes this:** 145 of 200 episodes (72%) already publish
full `.srt` transcripts in their RSS feeds, via the Podcast 2.0
`<podcast:transcript>` tag. Free, timestamped to the millisecond, no
credentials, no Descript API, no vendor relationship.

Only 55 episodes (39.7 hrs) need machine transcription — about **$9.52** at
Google's batch rate, down from ~$102.

**Architectural stance (adopted):** Descript is a *source*, never a dependency.
The pipeline is `RSS → .srt → our database`. Descript is invisible to our code;
if LHF switches editors tomorrow nothing breaks, as long as their host keeps
emitting the tag. We store the parsed text locally rather than reading their
URLs at query time, so we survive link rot and host changes too.

---

## What already exists

The schema was built for this, so most phases are additive rather than
structural:

| Already there | Status |
|---|---|
| `segments` table (episode_id, start_sec, end_sec, speaker_tag, text) | Empty, source-agnostic, ready |
| `episodes.transcript_text` / `transcript_status` / `transcript_source` | Ready |
| `episodes_fts` includes a `transcript_text` column | Ready |
| FTS triggers already carry `transcript_text` on insert/update | Verified |

Nothing built so far has to be rewritten.

---

## Phase 1 — Capture the transcript URLs ✅ DONE

**Effort: ~30 min. Risk: none.**

Add `transcript_url` and `transcript_type` to `episodes`; read the
`<podcast:transcript>` tag during feed ingest. No fetching yet.

Immediately makes coverage visible and queryable ("which episodes still need
transcribing?") without touching anything else.

- `ingest/schema.sql` — two columns
- `ingest/ingest.py` — register the `podcast` namespace, read the tag

---

## Phase 2 — Fetch and parse the SRT ✅ DONE

**Effort: half a day. Risk: low.**

New `ingest/transcripts.py`: for each episode with a `transcript_url` and no
transcript yet, fetch → parse cues → write `segments` + a concatenated
`transcript_text` → set `transcript_source = 'feed'`, `transcript_status = 'done'`.

Gotchas found while testing:

- **URLs 302-redirect** — follow redirects; a naive fetch gets 0 bytes.
- **Store the text, don't lean on the URL.** Podbean CDN paths are opaque and
  will rot. Once parsed, we never need the URL again.
- **Merge cues into passages before indexing.** A cue averages ~5 words
  (1,970 cues for a 55-minute episode). Phrase searches would break across cue
  boundaries and snippets would be useless. Merge into ~20–30 second passages,
  keeping the first cue's `start_sec` — roughly 100–150 passages per episode,
  ~20k rows across the archive instead of ~285k.
- **Rate-limit the fetch** — one at a time with a pause. Same reasoning as the
  audio backfill: the box shares an uplink with 20 other services.
- Idempotent, like everything else: re-running skips episodes already done.

---

## Phase 3 — Make transcripts searchable ✅ DONE

**Effort: ~half a day. Risk: medium — this is the one with a real design decision.**

`episodes_fts` already has the column, so episode-level transcript search
starts working the moment Phase 2 lands. Two things need attention:

**a) The snippet bug.** `serve.py` calls
`snippet(episodes_fts, 1, ...)` — column 1 is hard-coded to `description_text`.
Once transcripts are populated, a query matching a transcript would return a
snippet of the *description* instead of the matching passage. Either detect the
matching column or show both.

**b) Episode-level vs passage-level index.** These answer different questions:

- **Episode-level** (`episodes_fts`, exists) — *which episodes discuss this?*
  Good for ranking. Cannot tell you where in the episode.
- **Passage-level** (new FTS over `segments`) — *where exactly was this said?*
  Required for jump-to-moment.

Build both. Rank episodes with the first, locate moments with the second. This
is the standard arrangement and it's why the `segments` table exists.

---

## Phase 4 — Jump to the moment ✅ DONE

**Effort: ~half a day. Risk: low once Phase 3 is done.**

With passage-level hits carrying `start_sec`, a result can link into the
Podbean player at the timestamp, and the result card can show the actual spoken
line rather than the show-note blurb.

This is the feature that makes the archive feel like a different product —
searching what was *said* rather than what was *written about* an episode.

---

## Phase 5 — Fill the 55-episode gap

**Effort: ~half a day + runtime. Cost: ~$9.52.**

Google STT batch for episodes with no feed transcript, writing into the same
`segments` table with `transcript_source = 'google'`. Nothing downstream
changes — that's the point of the source-agnostic design.

Follow the Google Cloud walkthrough in `docs/build-plan.html`. Worth doing
*after* Phases 1–4 prove the pipeline on free data, so the only new variable is
the transcription source.

---

## Phase 6 — Enrichment over transcripts

**Effort: ~1 day. Cost: ~$7 batched.**

Re-run the AI extraction with transcripts in context: guests never mentioned in
show notes, topics, interviewer attribution, per-episode summaries. This is the
Tier 2 pass described in the client memo, now with far better input.

---

## Known limitations (tell the client)

**Quality is good, not perfect.** A sample transcript renders Elise Bryant as
"Lisa." These are machine transcripts that survived an edit, not proofread
documents — proper nouns still take damage, which matters because proper nouns
are what this archive is for. Worth a spot-check pass on the most-searched
names.

**No speaker labels.** The `.srt` export carries plain cues; Descript's speaker
names don't survive into the format. So no automatic guest-vs-host attribution
from this source. Google's diarization could supply it for the gap episodes,
which would leave the archive inconsistent — probably better to skip speaker
labels entirely for now than to have them on 28% of episodes.

**The 100-episode feed cap still applies.** Transcripts are only exposed for
episodes the feed exposes. Older episodes need the Podbean API or dashboard
export regardless — and their transcripts likely exist there too, which is one
more reason to sort that out.

**Coverage will drift.** 72% today. New episodes appear to include transcripts
consistently, so the ratio should improve, but the ingest must handle both
cases indefinitely rather than assuming a transcript is present.

---

## Suggested order

Phases 1–2 in one sitting gets real transcripts into the database. Phase 3–4
turn that into the feature people notice. Phase 5 is cheap cleanup. Phase 6 is
where the original "catalogue the guests and topics" ask finally gets answered
properly.
