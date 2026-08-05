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

**It cuts clips.** Press the scissors on the player and you get the waveform
with that passage already selected. Drag the handles, zoom in, snap the cut to
the gap between words, listen back, download the MP3. It's copied out of the
original file rather than re-recorded, so it's identical to what went out, and
the filename carries the show, date and timecode.

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
- **Help** explains the rest, with examples you can click to run

---

## Two things to know

**The transcripts are machine-made** — good enough to find things, but names
take some damage. Fine for searching, not for quoting.

**The feed only gives out the most recent 100 episodes per show**, so this
covers roughly the last two years. Older ones need pulling from the Podbean
back-end — worth doing sooner rather than later, because as new episodes publish
the oldest drop out of the feed and get harder to reach.

---

## Where it could go

1. **Topics** — the one part of the original list still missing. Show notes
   don't state them outright, so it needs a pass over the descriptions and
   transcripts to work them out. The one genuinely useful job for AI here, and a
   small one. The same pass picks up guests who weren't hyperlinked, and who was
   interviewing.
2. **The rest of the archive** — everything older than the feed reaches.
3. **The search box** on laborheritage.org.
4. **Producer tools**, if they'd help: a "not aired since" list for scheduling,
   a run-sheet that totals durations against a target slot, one-click citations.

Happy to talk any of it through — or leave it as is. It's working and looking
after itself either way.
