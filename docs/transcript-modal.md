# The transcript modal

**Status: built.** The first cut described at the bottom of this document is
now in the app — a **Transcript** button on every episode that has one (144 of
200 when this was written; **147 of 200 in production and 147 of 203 in the
local retained archive as at 14 Aug 2026**), opening the words with the tools
around them.
Counts elsewhere in this document are as at build time for the same reason. No
AI involved; this is
scraping, the existing index and the existing clip editor pushed as far as they
go.

What shipped:

| | |
|---|---|
| **Read** | Every line with its timing, click or tap any to play, follow-along highlight as the audio moves, timestamps toggle |
| **Find** | Search inside the episode using the archive's own syntax — `"phrases"`, `AND`/`OR`/`NOT`, `organiz*`, `NEAR()` — with a hit count, next/previous, and a **matches only** view that collapses a 55-minute show to just the lines that mention the thing |
| **Carried through** | Opens pre-loaded with the search that produced the result, so the words that brought you here are already marked |
| **Use** | On tablets/computers, **Edit** on any line opens the clip editor on that passage. Or select a longer stretch for its exact duration, in/out times and **out-cue**, then hand that to the editor. Copy the passage as text. |
| **Take away** | On tablets/computers, print (a stylesheet that drops everything but the words), and download as **Text**, **SRT** or **VTT** |
| **Phone** | A compact find/listen/read surface: full-height scrolling prose, contextual Matches only, no editing routes or large selection lesson |
| **Honest** | A provenance line saying the transcript is machine-made, and a real empty state for episodes without one |

Citations were deliberately **not** built — see `docs/ai-layer.md`. They need a
format decision (Chicago vs MLA vs the Library of Congress broadcast
conventions) that should come from the client, and they get much better once
speakers can be named. "Copy passage" covers the immediate need meanwhile.

The rest of this document is the original brainstorm, kept because most of it
is still unbuilt and still worth arguing about.

---

Today the transcript is a plain-text page at `/episode/<id>/transcript`. It
works and it's honest, but it's a dead end: you can read it, and that's all.
Everything the archive knows about that episode — the audio, the timings, the
clip editor, the rest of the archive — is somewhere else.

This is a brainstorm for what a proper transcript view could be: a button on
each episode that opens the words *with the tools around them*.

The framing that matters: **LHF's people don't want to read a transcript, they
want to do something with it.** Quote it, cite it, cut it, put it on air. The
text is the index, not the product.

---

## Who's opening this modal

Three hats, often on the same person (from `HANDOFF.md`):

| | What they came for |
|---|---|
| **Radio broadcasters** — the Power Hour airs on WPFW 89.3FM | Exact durations, clean in/out points, run sheets. *"I have a 4-minute hole on Thursday."* |
| **Labor history researchers** — their org includes Library of Congress people | Provenance and citation. *"When did she say that, and can I quote it?"* |
| **Podcast producers** — Descript workflow | Pull quotes, show notes, promo clips, chapter marks. |

Nothing on the market serves the first one. That's the interesting gap.

---

## What we already have to build on

This is why a lot of the list below is cheap — the hard parts are done:

- **14,937 timestamped segments** across 144 episodes, ~22 seconds and ~59
  words each. Every line already knows exactly when it was said.
- **`segments_fts`** — a passage-level full-text index, so search *inside* an
  episode is the same machinery as search across it.
- **A working clip editor** (`mp3cut.js`, `waveform.js`) — waveform, drag
  handles, snap-to-silence, audition, and **lossless MP3 export cut from the
  source**, entirely in the browser. It already accepts an in/out range.
- **Shareable moment URLs** — `?ep=123&from=522&to=549` already opens a single
  passage.
- **Inline audio playback** from any second, no Podbean cooperation needed.

So "select text → get a broadcast-ready MP3 of exactly those words" is mostly
wiring, not new engineering. That's the headline idea below.

---

## Constraints to design around (not wish away)

- **No speaker attribution.** All 14,937 segments have timestamps; **zero**
  have a speaker tag — the Descript SRT doesn't carry them. Anything shaped
  like "show me everything Kim Kelly said" needs the AI pass or a diarization
  step first. Worth knowing before it gets promised.
- **Names are mangled.** Machine transcripts; already flagged to the client as
  "fine for searching, not for quoting." Anything quotable needs either a
  correction pass or a visible caveat next to the quote.
- **56 of 200 episodes have no transcript at all.** The modal needs a real
  empty state, not an error — and ideally says *why* (the feed didn't publish
  one) rather than looking broken.
- **~22-second granularity.** Good for jumping, coarse for precise quoting. A
  passage boundary will usually need nudging, which the clip editor already
  does well.

---

## The utilities

Rough effort/value read. **Value** is my guess at how often it gets used by
someone who came here on purpose.

### A. Reading the words

| Idea | Effort | Value | Notes |
|---|---|---|---|
| **Timestamped lines, click to play** | Low | High | The baseline. Every line becomes an entry point to the audio. |
| **Follow-along highlight** | Low | High | Current line highlights as audio plays, auto-scrolls. We have the timings; it's a `timeupdate` handler. Makes the modal feel alive. |
| **Toggle timestamps off** | Low | Medium | Reading mode vs working mode. Researchers reading a long interview don't want a timecode every 22 seconds. |
| **Paragraph grouping** | Low | Medium | Merge adjacent segments into readable blocks instead of 22-second chunks. Purely cosmetic, big readability win. |
| **Copy line / copy selection** | Low | High | With and without the timestamp — both get asked for. |

### B. Search inside the transcript

| Idea | Effort | Value | Notes |
|---|---|---|---|
| **Find in transcript** with match count and next/prev | Low | High | The single most obvious missing thing. `Ctrl-F` works but doesn't know about timestamps or scroll-to-audio. |
| **Same query syntax as the main search** | Low | High | `"exact phrase"`, `AND`/`OR`/`NOT`, `organiz*`, `NEAR(a b, 5)` already work — `segments_fts` is right there. Consistency is free and cataloguers will expect it. |
| **Filter to matching lines only** | Low | Medium | Collapse the transcript to just the hits. Turns a 55-minute show into "the four times they mentioned Starbucks." |
| **"Find this phrase everywhere else"** | Low | **High** | Select text → run it against the whole archive. Turns one episode into a thread through 200. This is the one that makes the archive feel like an archive. |
| **Per-episode word frequency / concordance** | Medium | Low–Med | Researcher catnip, narrow audience. Cheap-ish but easy to over-build. |

### C. Broadcast tools — the underserved hat

| Idea | Effort | Value | Notes |
|---|---|---|---|
| ~~**Select text → clip**~~ ✅ **built** | Medium | **Highest** | Two routes shipped: **Edit** per line (one click from a search hit to a waveform), and drag-select for a longer passage. The clip editor already existed; this gave it a *text* interface instead of a waveform one. Finding the moment is the hard part, and words are how people find it. |
| **Live duration of selection** | Low | High | "This passage is 3:42." Answers the fill-a-slot question directly, before any cutting. |
| **Snap selection to sentence + silence** | Low–Med | High | Clip editor already snaps to silence; snapping the *text* selection to sentence boundaries first gives clean starts and ends without hand-nudging. |
| **Out-cue readout** | Low | High | The last few words before the out point, plus the duration — standard radio paperwork so the operator knows when to come back. Trivial from the text, and nothing else does it. |
| **Add to run sheet** | Medium | High | Collect passages across episodes, see cumulative duration against a target. Already a seed in `HANDOFF.md`; the transcript is where you'd pick them. |
| **Export as a cue sheet** | Low–Med | Medium | Intro line, out-cue, duration, source. The paper that goes to the studio. |

### D. Researcher tools

| Idea | Effort | Value | Notes |
|---|---|---|---|
| **Copy citation** | Low | **High** | Show, episode title, broadcast date, timestamp, and the quoted line. LC people will care about the format — worth asking which one rather than guessing. |
| **Permalink to a line** | Low | High | `?ep=123&t=1042`. The infrastructure exists; this is the footnote-able URL. |
| **Download transcript** | Low | Medium | `.txt` today; `.srt` / `.vtt` are nearly free from the same rows and are what a video editor or captioner wants. |
| **Provenance note** | Low | High | "Machine transcript, not checked." Sitting next to the quote, not buried in help. Protects them from quoting a mangled name. |
| **Suggest a correction** | Medium | Medium | Fix a mangled name inline. **Needs the admin interface and auth** — see `docs/ai-layer.md`. But it's the thing that turns transcripts from searchable into quotable, and every correction is permanent value. |
| **Pull-quote card** | Medium | Low–Med | Quote + attribution + show branding as an image for social. Producer-ish more than researcher, and easy to gold-plate. |

### E. Things AI would unlock (not now)

Parked here so they're not forgotten, all downstream of `docs/ai-layer.md`:

- **Speaker labels** — who is talking, which is the single biggest upgrade to
  every other item on this page.
- **Name repair** — makes transcripts quotable rather than merely searchable.
- **Segment boundaries** — both shows are magazine format; knowing where each
  item starts turns "find the episode" into "find the eight-minute piece", and
  makes the clip and run-sheet tools dramatically better.
- **Chapter marks / auto show notes** from those boundaries.

---

## The first cut — ✅ built

1. ✅ Modal opens from a **Transcript** button on the card
2. ✅ Timestamped lines, click any to play, follow-along highlight
3. ✅ Find-in-transcript with count and next/prev, same syntax as the main search
4. ✅ Select a passage → **duration readout** + **Open in clip editor**
5. ⏸ ~~Copy citation~~ → moved to `docs/ai-layer.md` (needs a format decision);
   **Copy passage** shipped instead
6. ✅ Provenance line: machine transcript, unchecked
7. ✅ Honest empty state for the 56 episodes without one

Plus three that weren't on the list and turned out to be nearly free: **matches
only**, **print**, and **SRT/VTT download** rebuilt from the stored segment
timings.

It was mostly assembly of parts that already existed, and it serves all three
hats: read (researcher), cut (broadcaster), quote (producer).

### Still open from the lists above

The genuinely useful ones not yet built: **paragraph grouping** (readability),
**"find this phrase everywhere else"** (one click from a line into the whole
archive — probably the best remaining idea), **add to run sheet**, and
**suggest a correction** (which needs the admin interface and auth).

---

## Open questions

- **Which citation format?** Worth asking the LC people rather than picking.
- **Is the run sheet part of this modal, or its own thing?** It spans episodes,
  so probably its own — but the transcript is where passages get chosen.
- **Modal or page?** A page is linkable and printable and survives a refresh;
  a modal keeps your search results behind it. Possibly both: modal from a
  result, permalink opens the page.
- **How much does correction matter to them?** If quoting is a real workflow,
  the correction tool jumps up the list and drags the admin interface with it.
- **Do they want this public**, or is it internal? Changes the auth story and
  whether laborheritage.org links into it.
