# The AI layer — what it would add, what it costs, what it needs first

**Status: groundwork only. Nothing in production uses AI, and no AI has run
against the archive.**

The app as deployed does no AI analysis of any kind. Everything it currently
knows — 200 episodes, 143 hours, 14,937 searchable passages, 232 tags, 14
detected re-airs — comes from scraping a public feed and reading structure the
producers already created. That approach has now been taken about as far as it
goes. What remains needs something to read the prose.

This document is the decision, not the plan: what an AI layer could do, what
each piece would cost, and what has to exist before any of it can be run
responsibly.

---

## Where scraping stopped

Three things from Harold's original brief cannot be scraped, because nobody
ever wrote them down in a machine-readable place:

| Wanted | Why scraping can't get it |
|---|---|
| **Topics** | Show notes *describe* an episode; they never classify it. Hashtags were tested and are useless — `#LaborHistory` appears on 176 of 200 episodes. |
| **Guests who weren't hyperlinked** | The producers link most guests, and those 232 links are the current Tags list. The ones they didn't link are invisible. |
| **Who was interviewing** | Never stated anywhere. It's a two-host show, so it's a small question — but an unanswerable one without reading the transcript. |

Everything else in the brief is built and working without AI.

---

## A shared vocabulary — the option worth raising first

**Added 9 August 2026. Nothing here is built, and nothing should be built before
the client has been asked. This is a consideration, recorded so the conversation
starts from facts.**

### The thing that already exists

LHF has a second system: the **Labor Arts & Culture Database**
(<https://labor-database.supersoul.top>, source at
<https://github.com/Catskill909/labor-database>). It carries a controlled
vocabulary that is live, in use, and classifying **~5,950 entries** — roughly
2,190 films, 1,915 quotes, 1,410 history records and 435 music, measured
9 August 2026 and growing.

**34 canonical tags in three facets**, from `server/tags.ts`. Note **34, not the
35 its own `tags-dev.md` claims** — that document says "35 canonical tags" and
then lists 13 + 13 + 8. Verified against the live `/api/tags`.

| Facet | n | Examples |
|---|---|---|
| Theme | 13 | Strikes & Lockouts, Organizing, Collective Bargaining, Child Labor, Labor Culture & Arts |
| Industry | 13 | Mining, Steel & Manufacturing, Textiles & Garment, Maritime & Dockworkers, Domestic Workers |
| Social Dimension | 8 | Civil Rights & Race, Women & Gender, Immigration, Socialism & Left Politics, Working Class |

The taxonomy is the smaller half of that file. It also carries:

| | |
|---|---|
| `TAG_RULES` | **145 regex patterns** mapping text → canonical tag |
| `TAG_NORMALIZATION` | 175 legacy-term mappings → canonical |
| `PEOPLE_TAGS` / `EVENT_TAGS` / `ORG_TAGS` | 42 / 31 / 28 named entities → tags |

`GET /api/tags` is public and unauthenticated, returning the canonical list with
per-tag counts and facet groups.

### Why this reframes the topics question

The client's question is expected to be **"do we tag by hand, or let AI do it?"**
Both options as posed are weak, and the vocabulary makes a third one available
that is better than either.

- **By hand** is ~7 hours for the 200-episode backlog, plus two episodes a week
  forever. It is nobody's job, which is why archives go untagged.
- **Free-form AI** is already rejected above, and correctly.
- **Against a fixed list of 34**, the work splits three ways, cheapest first.

**1 — Rules first, with no AI at all.** The 145 patterns run against 882,346
words of transcript for free, deterministically, and re-runnably. This archive
has far more text per item than the film database does — a 32-minute episode is
roughly 5,000 spoken words against a one-paragraph synopsis — so the rules should
land harder here than where they were written. **How much of the archive the
rules alone can tag is a measurable number and nobody has measured it.** Do that
before anything else; it may make most of the AI question moot, and it costs an
afternoon and no money.

**2 — AI only for what the rules miss, as classification rather than
generation.** Choosing from 34 known terms is a much easier task than inventing
topics, and — the real argument — it is **verifiable**: any output not in the
list of 34 is a bug that can be caught automatically. Free-form output can only
be judged by a human reading it. It is also cheaper than the $4.35 costed below,
because the response is a few tokens rather than prose.

**3 — A human approves**, in the admin screen that four other features already
need. Machine proposes, archivist disposes. This is ordinary cataloguing
practice and the workflow the Library of Congress people in their organisation
would expect to see.

### Why it matters beyond this archive

LHF runs at least three systems — this podcast archive, the Labor Arts & Culture
Database, and Labor Landmarks (`labor-landmarks.supersoul.top`, referenced from
the database's own UI). **If each invents its own topics they will never join
up.** One vocabulary across all three means "everything on Mining" spans
episodes, films, quotes, music and landmarks in one answer. Nothing else in this
space does that.

It is also the cheap ask. Tagging 200 episodes costs the client seven hours;
approving 34 terms costs them one meeting. And approving a labor-history
vocabulary is a contribution their **former Library of Congress historians** are
uniquely placed to make — it spends their expertise rather than their afternoons.

### Be precise about the LCSH claim

`server/tags.ts` describes its taxonomy as *"informed by Library of Congress
labor subject headings, Tamiment/Wagner Labor Archives, and the Labor Film
Database."* That is honest, and it is **not** the same as being LCSH. Real LCSH
is `Strikes and lockouts` with the URI
`http://id.loc.gov/authorities/subjects/sh85128472`; the canonical term here is
`Strikes & Lockouts`.

**In a room with actual LC people, claiming the stronger version will be
noticed.** Say "informed by", which is true and still impressive.

The gap is also an opportunity worth putting on the table: **mapping each of the
34 terms to its real `id.loc.gov` URI is a one-time job of 34 lookups**, and it
is what would make this data genuinely citable and interoperable in a library
context. Display name stays `Mining`; the authority URI rides alongside it. That
is the version an archivist can hand to another institution.

### If it is ever built: two mechanics

1. **Copy the vocabulary; do not fetch it live.** The API sends
   `access-control-allow-origin: https://labor-database.supersoul.top`, so a
   browser on this origin cannot read it regardless — but the better reason is
   that an authority list which can change without warning is not controlled.
   Vendor the 34 terms with a recorded source and version, and treat an update as
   a deliberate act. That is how libraries handle authority files, and it
   respects this project's stdlib-only, no-dependency rule.
2. **Subjects and names are different axes, and both should exist.** The 232 tags
   this archive already has are *entities* — people, bands, museums, books,
   lifted from producer hyperlinks — which correspond to name authorities
   (≈LCNAF). The 34 are *subjects* (≈LCSH). They are not rivals and libraries
   deliberately carry both. **But "tag" now has three claimants in this product**
   — entities, subjects, and the personal clip labels in
   `docs/clip-library.md`. That naming needs resolving before any of it ships;
   see that document's open questions.

### What to actually ask the client

1. Do you want the archive classified by topic at all?
2. If so — **should it use the same vocabulary as the Labor Arts & Culture
   Database**, so the two can eventually be searched together?
3. Would your Library of Congress people review and approve the 34 terms, and
   should we map them to real LCSH authority URIs while they are looking?
4. Only then: rules, AI, or hand — which is a much smaller question once 1–3 are
   answered.

---

## What an AI layer could do

Roughly in order of value-per-pound. Only the first is built.

### 1. Topics, un-hyperlinked guests, interviewers — *code written, never run*

One pass over each episode's show notes and transcript returning what it's
about, who was on, and who was asking. This is the piece that closes the
original brief.

It is written (`ingest/extract.py`) and its whole output path is tested, but it
has **never been run against the live API** — see [Running it](#running-it).

Two design choices worth knowing, because they're what make the output a
catalogue rather than a pile of strings:

- **A seeded vocabulary.** Asked for free-form topics across 200 episodes, any
  model returns "unions", "labor unions" and "unionization" as three separate
  topics. The pass carries a ~50-term labor-history taxonomy it must prefer,
  and may coin at most two new terms per episode when nothing fits.
  **That taxonomy is a placeholder written for this file, and it should be
  replaced** — see [A shared vocabulary](#a-shared-vocabulary--the-option-worth-raising-first)
  below. LHF already owns a better one, in production, on six thousand records.
- **Raw output is kept.** Every response is stored verbatim. Changing the
  *prompt* means paying again; changing how the output is *parsed* is free and
  takes a second. That matters over a decade of archive.

Producer hyperlinks stay ground truth throughout — they're fed to the model as
spelling hints, and where the two disagree about how a name is written, the
producers win.

### 2. Episode summaries

A consistent one- or two-line summary per episode, in a house voice, for
listings and the eventual laborheritage.org search results. Show notes vary
enormously in length and format; summaries would not. Cheap, because it's the
same pass.

### 3. Name repair in transcripts

The transcripts are machine-made and good enough to search, but names take
damage — this is already flagged to the client as "fine for searching, not for
quoting." A pass that corrects names against the known guest list would make
transcripts quotable, which is a different and more valuable thing than
searchable.

### 4. Segment boundaries

Both shows are magazine-format: several distinct items per episode. Knowing
where each segment starts and ends would turn "find the episode" into "find the
eight-minute piece", which is what a producer filling a slot actually wants.
It would also make the clip editor land on the right passage automatically.

### 5. Similarity and "more like this"

Once topics exist, "find me something like this one" is nearly free — useful
when a scheduled programme falls through and something has to fill the hour.

### 6. Formatted citations

Copy a reference to a moment — show, episode, broadcast date, timestamp and the
spoken line — in a chosen citation style.

Parked here rather than built into the transcript view for one reason: **it
needs a format decision nobody has made yet.** Chicago, MLA, APA and the
broadcast-archive conventions the Library of Congress people would expect all
disagree about how to cite a radio segment, and picking one blind means
building the wrong thing confidently. Worth asking them.

It also gets substantially better *after* the extraction pass: a citation is
much more useful when it can name the speaker and the interviewer, and when
the quoted names have been repaired. Copying the raw passage — which the
transcript view does today — covers the immediate need without guessing.

### 7. Suggested re-airs

Combining topic, duration, and last-aired date into a ranked "worth running
again" list. This is the scheduling question the archive was built to answer,
and it's only answerable once topics exist.

---

## What it would cost

Measured against the real archive, not estimated from a brochure. Batched,
which halves the price and is the right shape for work nobody is waiting on.

| | Tokens | Cost |
|---|---|---|
| Per episode | ~7,000 in, ~350 out | **$0.022** |
| Initial run, all 200 episodes | 1.55M | **$4.35** |
| Ongoing — 2 shows weekly, ~104/year | — | **~$2.26/year** |
| The 55 episodes with no transcript | — | included above (notes only) |

Two things follow from these numbers.

**The initial run is a rounding error.** Four dollars, once. The earlier
estimate of ~$7 in the build plan was conservative and close enough.

**Ongoing cost is not the deciding factor for anything.** Two dollars a year is
below the threshold where it's worth optimising, and well below the cost of the
time spent choosing a provider. If a cheaper model is chosen it should be for a
reason other than price — an existing account, a billing relationship already
in place, or measured output quality.

Costs above are for a frontier model. A smaller, cheaper model would run this
for well under a dollar total, at some cost in how sensibly topics are chosen.
The seeded vocabulary narrows that gap considerably, because the hard part —
deciding what to call things — is already decided.

### A note on provider

`ingest/extract.py` is written against the Anthropic API. Moving it to Gemini
or anything else is a contained change — one file, the request-building and
response-parsing parts — but it is a rewrite of that file, not a configuration
switch. The database schema, the API, the UI, the export and the seeded
vocabulary are all provider-agnostic and would not change.

---

## What has to exist first

**This should not be run from a shell command, and currently that's the only
way to run it.**

Every AI operation needs three things the site does not yet have:

1. **A key, held properly.** As a Coolify environment variable, never in the
   repo, never pasted into a terminal history. The container is already
   configured this way for `DATABASE_PATH` and friends, so the mechanism exists.

2. **An admin interface.** Something behind a login that can trigger a run, show
   what it's about to do and what it will cost, report progress, and show what
   changed. AI work costs money and rewrites catalogue data — two properties
   that make "run it and hope" the wrong shape. This is the real blocker, and
   it's needed for more than AI: there's currently no way to add a staff note,
   correct a bad tag, or mark an episode as already re-aired, all of which the
   schema already supports.

3. **Authentication.** There is deliberately none today, and that is correct
   while everything served is already-published material. The moment there's a
   button that spends money or edits records, that stops being true.

The pipeline is built so that none of this blocks anything else: the archive
works fully without the AI layer, and adding it later changes no existing
behaviour.

---

## Running it

For reference, and for whoever builds the admin interface. Today this is a
developer operation on a machine with a key:

```bash
pip install anthropic                   # the project's only dependency
export ANTHROPIC_API_KEY=sk-ant-...     # in production: a Coolify env var

python3 ingest/extract.py --dry-run     # build and cost the batch, send nothing
python3 ingest/extract.py               # submit, wait, collect, build
python3 ingest/extract.py --rebuild     # re-derive tables from stored output, free
```

`--dry-run` needs no key and no network. It builds every request against the
real database and prices the job, which is how the figures above were produced.

It is deliberately **not** part of `refresh.py`, the daily job that runs
unattended in the container. That loop must stay stdlib-only, keyless and free.
A step that can fail on an expired key, or quietly spend money, is a different
kind of thing from one that re-reads a public feed. The pass only processes
episodes it hasn't seen, so running it after a batch of new episodes costs only
what's new.

---

## The decision

The groundwork is done and costs nothing to leave sitting there. What it needs
now is a conversation with the client about whether they want an AI layer at
all, and if so, which of the six items above is worth having — because they
differ a lot in value and not much in price.

Worth saying plainly in that conversation: the archive is complete and useful as
it stands. The AI layer closes the last gap in the original brief and opens
several doors beyond it, but nothing currently breaks without it.
