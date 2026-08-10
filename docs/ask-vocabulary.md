# Draft: asking LHF about a shared topic vocabulary

**Status: written 9 August 2026, not sent.** Same shape as
`docs/reply-descript.md` — a short message meant to be pasted into an email and
edited, not a document to forward.

The reasoning behind it, including the numbers and the three-layer approach to
actually doing the tagging, is `docs/ai-layer.md` → *A shared vocabulary*. Read
that first if they come back with questions.

**Why it is worth sending before any work starts:** the answer changes what gets
built. Adopting the existing vocabulary makes topics a one-meeting approval and
opens the door to searching across all their collections at once. Inventing a
separate list here makes the two archives permanently incompatible, and joining
them later is much harder than starting that way.

**One thing to keep right in any edit:** the 34 terms are *informed by* Library
of Congress subject headings. They are not LCSH and nobody at the Library of
Congress approved them. Say the accurate thing — their group includes former LC
people, who are exactly the readers who would notice.

---

## The draft

> **Subject: topics — one question before we start**
>
> Hi Harold,
>
> Topics are the last piece of your original list, and before I build anything
> I want to check one thing with you, because it changes the answer.
>
> The problem with topics isn't finding them — it's agreeing what they're
> *called*. Left to itself, anything reading 200 episodes will produce "unions",
> "labor unions" and "unionization" as three separate topics, and a list like
> that is worse than none: you can't browse it and you can't trust a count.
>
> **You've already solved this once.** The Labor Arts & Culture Database uses a
> fixed list of 34 topics in three groups — Theme, Industry, and Social
> Dimension — and it's already sorted around 6,000 films, quotes, songs and
> history entries with it.
>
> **My suggestion is that the podcast archive uses the same 34.** Two things
> follow.
>
> One search could eventually cover everything you have. Ask for *Mining* and
> get the episodes, the films, the quotes, the songs — together. If this archive
> invents its own topic names instead, the two collections never join up, and
> joining them later is a much bigger job than starting that way.
>
> And it's the cheap version. Tagging 200 episodes by hand is about seven hours
> of somebody's time, then two more episodes every week forever. Agreeing a list
> of 34 terms is one meeting — and agreeing a labor-history vocabulary is
> exactly the kind of thing the former Library of Congress people in your group
> are qualified to do. It uses their expertise instead of their afternoons.
>
> **How the tagging itself would work** — and most of it isn't AI:
>
> 1. **Pattern matching first, which costs nothing.** The other database already
>    contains around 145 word patterns — *picket*, *walkout*, *card check*,
>    *shop steward* — that map onto those 34 topics. Running those across
>    880,000 words of transcript should tag a good share of the archive for
>    free, the same way every time. I'd like to measure exactly how much before
>    we spend anything; that's an afternoon's work.
> 2. **AI only for what's left**, and only ever choosing from the 34 rather than
>    inventing its own. That's a much smaller and safer job — anything it
>    returns that isn't on the list is a fault we can catch automatically, which
>    isn't true of free-form topics. Cost is a few dollars once.
> 3. **You approve.** Nothing goes into the catalogue without a person saying
>    yes.
>
> **One point of accuracy**, because it matters to your LC folks: that list of
> 34 is *informed by* Library of Congress labor subject headings — it isn't
> literally them. The real headings are formal records with permanent reference
> numbers. Linking each of your 34 to its official Library of Congress record is
> a small one-time job, and it's what would make the catalogue properly citable
> and shareable with other institutions. Worth deciding while the historians are
> looking at the list anyway.
>
> So, three questions:
>
> 1. Do you want the archive classified by topic at all?
> 2. If so, should it use the same vocabulary as the Labor Arts & Culture
>    Database?
> 3. Would your Library of Congress people review and approve the 34 terms —
>    and should we link them to the official LC records while they're at it?
>
> Nothing's blocked on this; the archive works as it stands. But it's a much
> better starting point than the question it replaces.

---

## Before sending

- **Run the measurement in step 1 first if you can.** "The patterns already tag
  62% of the archive for free" is a far stronger sentence than "should tag a
  good share", and it costs an afternoon and no money. If the number is high,
  the AI question shrinks to almost nothing.
- Check the 34 count against `/api/tags` on the day you send it. It was 34 on
  9 August 2026; their own `tags-dev.md` said 35 and was wrong.
