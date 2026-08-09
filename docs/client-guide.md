# LHF Digital Asset Manager

**https://lhf-tools.supersoul.top**

Harold's email asked for a catalogue of the guests, topics and interviewers
across both shows — pulled from what you've already published as well as what's
coming — searchable, so you can find an older show worth replaying, check
whether something is already in the can, and eventually put a search box on
laborheritage.org.

That's what this is. One discovery along the way changed the plan.

---

## What changed

My original suggestion was to pay for AI transcription: run both shows through
speech-to-text to get the words *and* the timings, so search could reach inside
the audio and jump you to the moment something was said. That was the expensive
part of the estimate.

Then I looked properly at your feed. **It already publishes transcripts, timings
and all** — your editing software writes them, Podbean carries them, and they've
been sitting there in public the whole time.

That's exactly what the AI step was going to produce. So it isn't needed:
**144 of 200 episodes came with a full transcript, free.** No transcription
bill, no new vendor, nothing extra for you to do, and new episodes arrive the
same way.

---

## What it does

**200 episodes · 143 hours · both shows**, updating itself daily.

![The archive — 200 episodes, both shows, filters and sorting](screenshots/01-search.png)

**It searches what was said, not just the show notes.** Searching the phrase
*"picket line"* finds 59 episodes — only **2** mention it in the written
description. The other 57 turned up because someone said it out loud. Click a
timestamp and the episode plays from that second.

![Searching the phrase "picket line" — matches found in the spoken audio, with timestamps](screenshots/02-heard.png)

![A player opened at the spoken moment, cued to 10:21, with the scissors alongside it](screenshots/audio-position-play.png)

**It spots repeats.** The archive works out when a programme has aired more than
once and says so under the episode: **8 repeated on the same show, 5 that ran on
both** — including *Striking At Kings* and *MLK in Memphis*.

![An episode flagged as having run three times, with the dates](screenshots/03-also-ran.png)

**It opens the transcript.** Every episode that has one — 144 of the 200 — has
a **Transcript** button. It opens the whole thing, already marked up with
whatever you just searched for.

![The transcript modal — timestamped lines, find-in-transcript, the player, and print and download controls](screenshots/transcript.png)

**Two gestures do most of the work.** Everything else is a refinement of them:

- **Click a line to hear it.** Anywhere on the line, or its timestamp. Tick
  **Follow audio** and the transcript scrolls along as it plays, so the words
  keep pace with the sound.
- **Drag across the text to select a passage.** The bar along the bottom tells
  you exactly how long it runs, where it starts and ends, and its **out-cue** —
  the last few words before it ends, so whoever's on the desk knows when to
  come back. **Edit audio** opens that selection in the clip editor; **Copy
  passage** takes the words.

![A passage selected in the transcript, with its timing, duration, out-cue, and editing controls](screenshots/audio-select.png)

Beyond those:

- **Edit** on a single line does the same for just that line, and is always
  showing on lines that matched your search
- **Search within the episode**, using the same shortcuts as the main search
  box, with a running count and arrows to step between hits
- **Matches only** — collapse a 55-minute show down to just the lines that
  mention the thing you're after
- **Print it**, or download it as plain text, or as subtitles (SRT / VTT)

The two together are the bit worth dwelling on. Finding the moment is the hard
part of making radio, and you find it by reading, not by staring at a waveform.
So: search for the thing, tick **Matches only** to strip the episode down to
the lines that mention it, and press **Edit** on the one you want. You're in
the waveform, on that passage, without having scrubbed through anything.

Or drag across a longer stretch, and the archive tells you it runs 1 minute
6 seconds before you cut anything.

**It cuts clips.** Press the scissors on the player and you get the waveform
with that passage already selected. Drag the handles, zoom in, snap the cut to
the gap between words, listen back, download the MP3. It's copied out of the
original file rather than re-recorded, so it's identical to what went out, and
the filename carries the show, date and timecode.

The editor is built around listening, because that's how an edit is actually
judged:

- **Play, pause and stop**, with a timeline above each waveform so you always
  know where you are. <kbd>Space</kbd> plays and pauses from anywhere.
- **Repeat** keeps the selection going round while you move the handles, so you
  hear each adjustment come back without stopping and starting.
- **Click anywhere on the top waveform** to listen from that point — for
  finding a moment when you don't yet know where it is.
- **Audition in** and **Audition out** play two seconds either side of a single
  cut, because an edit is judged one edge at a time.
- **Mark as you listen** — press <kbd>I</kbd> where the clip should start and
  <kbd>O</kbd> where it should end, and the point lands exactly where you heard
  it. <kbd>[</kbd> and <kbd>]</kbd> jump the cursor between the pauses in
  speech, which is usually the fastest way to the edge you want.

**The lower waveform is drawn in detail** — solid through the middle for how
loud a moment really is, outlined for how far it peaked, with two faint lines
marking that episode's own silence. The gaps between words are visible, so you
can see the pause you're cutting into rather than guessing at it, and zoom right
down to a fraction of a second on one edge.

![The clip editor — the passage selected on the waveform, in and out points, audition and snap controls, and the MP3 download](screenshots/audio-edit-modal.png)

**Tags** — 232 people, bands, museums and books, taken from the links in your
own show notes rather than guessed. Click one to see every episode featuring it.

**Export** — whatever's on screen downloads as a spreadsheet, with links back to
each episode, its transcript and the audio.

![The export panel — CSV, clipboard or JSON](screenshots/05-export.png)

**Links** — the address bar always matches what you're looking at, so any search
can be pasted to a colleague, or pointed at a single moment. That's also how a
search box on laborheritage.org would work.

---

## Using it

Just type — results narrow as you go. Beyond that:

- **"in quotes"** for an exact phrase
- **strike NOT encore** to exclude; `AND` and `OR` work too
- **organiz\*** catches organize, organized, organizing, organizers
- Filter by show, year or encores; sort by **longest / shortest** when you're
  filling a slot of a certain length
- **More** at the end of a description opens the rest of the show notes
- **Transcript** opens the full transcript, with the same search inside it
- **Help** explains the rest, with examples you can click to run

---

## Two things to know

**The transcripts are machine-made** — good enough to find things, but names
take some damage. Fine for searching, not for quoting.

**The feed only gives out the most recent 100 episodes per show**, so this
covers roughly the last two years — back to September 2024. Older episodes need
pulling from the Podbean back-end.

**And both shows are now sitting at exactly that limit.** Which means that from
the next episode each of you publishes, the oldest one drops out of the feed.
The archive keeps it — it doesn't forget anything it has already read — but
after that point *this* becomes the only place it can be reached from, because
the feed no longer offers it.

Nothing is lost today, and nothing needs deciding this week. Two things follow
from it, though, and they're worth knowing now rather than in a year:

- **The archive is worth backing up**, and there's now a tool that does it. It
  used to be rebuildable from the feeds in two minutes; that stops being true
  from here on.
- **The older backlog gets no easier to reach.** Everything before September
  2024 is already only in the Podbean back-end. If you want it in here, that's
  a one-time job whenever you're ready.

---

## Where it could go

Everything above was built by reading what's already published — the feed, the
show notes, the transcripts, the links you write yourself. **That approach has
now gone about as far as it can.** Nothing in the archive uses AI, and nothing
in it needs to.

The remaining items split into two kinds: things that are just more work, and
one that's a decision.

### The decision: topics, and the rest of the reading

**Topics are the one part of the original list still missing**, and they're
missing for a specific reason — show notes describe an episode but never
classify it. Neither do the hashtags: `#LaborHistory` is on 176 of the 200.
Nothing to scrape. The only way to get topics is to have something read the
episodes.

The same reading picks up **guests who weren't hyperlinked** and **who was
interviewing** — the last two gaps in Harold's list.

I've built and tested that pass, so the groundwork is done and the plumbing is
in place. **I haven't run it**, because that's your call and your money, and
because it should be run from a proper admin screen rather than a developer's
laptop (more on that below).

What it would cost, measured against your actual archive rather than guessed:

| | |
|---|---|
| Reading all 200 episodes, once | **about $4** |
| Each new episode from then on | **about 2 cents** |
| Which, at two shows a week, is | **about $2 a year** |

Those numbers are small enough that cost isn't really the question. The
question is whether you want the archive to make judgements at all, and how
much you want it to make.

Once something is reading the episodes, the same pass could also give you:

- **Consistent summaries** — one or two lines per episode in a house voice,
  which is what a search box on laborheritage.org would show
- **Names fixed in the transcripts** — the machine transcripts mangle names,
  which is why they're searchable but not quotable; this would change that
- **Segment boundaries** — both shows run several items per episode, so this
  turns "find the episode" into "find the eight-minute piece"
- **"More like this"** — useful when something falls through and you need to
  fill the hour
- **Suggested re-airs** — topic plus duration plus how long since it last ran,
  ranked. This is the scheduling question the whole archive was built to answer

None of it is decided, none of it is running, and it's all worth a conversation
rather than an email — the six things above differ a lot in usefulness and
hardly at all in price.

### The rest

1. **An admin screen.** Needed before any of the above, and honestly needed
   anyway. Something behind a login where you can start a job and see what it
   did — and, separately from AI, add a staff note, fix a wrong tag, or mark an
   episode as already re-aired. The archive can already store all three; there's
   just no way for a person to enter them.
2. **The rest of the archive** — everything older than the feed reaches.
3. **The search box** on laborheritage.org.
4. **Producer tools**, if they'd help: a "not aired since" list for scheduling,
   a run-sheet that totals durations against a target slot, one-click citations.

Happy to talk any of it through — or leave it as is. It's working and looking
after itself either way.
