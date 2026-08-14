# Feed update audit — 13 August 2026

Written after production showed 9 August as its newest episode while Podbean
carried one from 13 August.

**Everything below is marked measured or inferred.** An earlier draft of this
document presented a deduction as a finding, then retracted a diagnosis that had
actually been correct, which cost an evening. The marking is the point.

---

## Q1. How often does the app update?

**Was: every 24 hours. Now: every 15 minutes.**

`docker-entrypoint.sh` starts `refresh.py --loop` in the background when the
container boots, unless `LHF_AUTO_REFRESH=0`. Coolify deploys the Dockerfile and
runs one container, so this in-container loop is the entire scheduler — there is
no host cron and no Coolify scheduled task.

**Nobody has to run anything by hand.** A manual `refresh.py` pulls an episode
early; it is not the mechanism.

A daily check was never right for a live podcast: a new episode could sit unseen
for most of a day. It was chosen because a tick was expensive. It no longer is —
see Q4.

---

## Q2. Why was the 13 August episode missing?

**Measured, 13 August 23:24 UTC:**

| Show | Podbean feed | Production | Gap |
|---|---|---|---|
| Power Hour | 2026-08-13 | 2026-08-06 | 1 episode, 10 h old |
| Labor History Today | 2026-08-09 | 2026-08-09 | none |

Only one episode exists between 9 and 13 August, so "production is four days
behind" was never what was happening — it was ten hours behind, on a 24-hour
cycle. Working as designed, and not the bug.

The `guid`-keyed upsert is demonstrably healthy: Podbean retitled the 2 August
LHT episode (dropping the `Labor History Today: ` prefix) and production carries
the **new** title. Edits propagate.

**Transcripts are healthy too.** Of 200 episodes, 145 have a transcript URL in
the feed and 144 have the text pulled — one failure, from January. The other 55
were never offered a transcript by Podbean, mostly encores.

---

## Q3. The real bug: `/data` was not a persistent volume

**Confirmed by Paul, 13 August 2026: there was no volume mounted at `/data` in
Coolify.** He added one during this session.

This was originally reached by inference, and the inference was right:

1. There is no `DELETE FROM episodes` anywhere in the codebase — verified by
   grep across all `.py`, `.sql` and `.sh`. Episode rows can only accumulate.
2. Production held Power Hour 2026-08-06, so it ingested on or after 6 August.
3. Before 6 August the Power Hour feed's oldest entry was 2024-09-12 — proven by
   a local copy ingested 4 August which still holds it.
4. Had production ingested even once before 6 August, that row would still be
   there and the count would exceed 100.
5. Production held exactly 100 per show and lacked 2024-09-12 entirely.

So production's database began empty on or after 6 August, and the app had been
live well before. The Dockerfile declares no `VOLUME` — only `mkdir -p /data`
(line 32) — so `/data` lived in the container's writable layer and was destroyed
on every redeploy.

`HANDOFF.md:780` had already specified the test: *"the check is whether the live
site reports more than 100 episodes for either show."* Production reported
exactly 100. **The check failed, and nobody had run it.**

### What it cost

**Three episodes have now rotated off Podbean** (measured after ingesting the
13 August episode, which pushed the third out):

| Show | Date | Title | On production? |
|---|---|---|---|
| Power Hour | 2024-09-12 | The power of our stories | **No** |
| Power Hour | 2024-09-19 | Shift Happens | Yes |
| Labor History Today | 2024-09-22 | The Disney Revolt (Encore) | **No** |

All three are in `~/Desktop/lhf-BACKUP-2026-08-13.sqlite`, taken during this
session. For the two absent from production, that backup is the only copy that
exists anywhere.

**Now that the volume is mounted, the archive accumulates as designed.** Verified
on a copy: after ingesting the 13 August episode, Power Hour holds 102 and LHT
101 — past the feed's 100 cap, which is the whole point.

---

## Q4. Making a 15-minute poll nearly free

Both shows are weekly: two publishing events a week, against ~672 polls. The
poll had to become cheap before the interval could come down.

**Conditional GET.** Podbean serves an `ETag` on both feeds and honours
`If-None-Match` with a 304 and an empty body — verified directly. `shows.feed_etag`
stores it, so an unchanged feed costs no bytes instead of ~1 MB. Without this,
15-minute polling would pull ~3 GB/month to discover nothing had happened.

**Enrichment only when something arrived.** `enrich.py` does `DELETE FROM reairs`
+ `DELETE FROM mentions` and a full rebuild across every episode — it cannot run
every 15 minutes. It is now gated on the feed actually bringing something.
Transcripts still run every tick, because they are one indexed lookup when
nothing is outstanding, and Podbean sometimes attaches a transcript days after
publishing.

**Failure is remembered.** If enrichment fails, the next tick would see "nothing
new" and skip it, reporting success and swallowing the failure — exactly the
silently-broken updater this loop exists to avoid. A failed skippable step is now
owed and retried.

**Measured:** a full tick with nothing new takes **1 second and downloads
0 bytes**.

---

## Q5. Why nobody noticed

**Nothing in the application reported when it last updated.** Not the UI, not the
API, not a log anyone reads. `HANDOFF.md:603` predicted precisely this:

> a silently broken updater is how this rots, and the symptom (an archive that
> quietly stops growing) is exactly the kind nobody notices for months

The footer now shows **"Feeds checked N minutes ago"**, from a new
`shows.feed_checked_at` stamped on every poll that reached Podbean *including a
304*. It deliberately does not use `episodes.last_seen_in_feed`, which only moves
when a feed changed — on a weekly show that is days old almost always, and a
footer built on it would report a healthy updater as dead. Past two hours the
line is flagged as stale.

---

## Bugs found and fixed along the way

**`last_seen_in_feed` was stamped per row.** `datetime('now')` was evaluated
inside the episode loop; writing 100 episodes spans several seconds, so one pass
wrote several distinct timestamps and only the rows landing in the final second
matched `MAX(...)`. `ingest.py --stats` — the documented tool for spotting
rotated-out episodes — reported **84 of 203 episodes as lost** when the true
number was **3**. Now one stamp per pass.

**"Gone from the feed" was decided globally.** The feeds are read in sequence, so
the two shows are stamped seconds apart and a global `MAX` condemned whichever
was read first. Conditional GET made it worse: a feed answering 304 is not
restamped at all. Now compared within a show.

**`/api/facets` would have 500'd on a deployed database.** It is also the
container health check (`Dockerfile:44`), and `serve.py` never runs migrations —
so on the first deploy carrying this change, facets would have failed until a
poll landed, failing the health check and restarting the container in a loop.
The column lookup is now guarded.

`tests/test-ingest.py` covers the first two, and was confirmed to **fail**
against the original predicate rather than merely passing against the new one.

---

## Still to do

1. **Deploy.** None of this is committed or deployed; it exists in the working
   tree only.
2. **Restore the two lost episodes** from the Desktop backup after the first
   deploy on the new volume, rather than letting a rebuild stand — a rebuild
   cannot recover them, because Podbean no longer serves them.
3. **Confirm `LHF_AUTO_REFRESH` is not `0`** in Coolify. `docker-compose.yml:18`
   sets it to `0` because compose runs a separate worker; Coolify runs one
   container and has none, so a copied `0` would disable updates entirely.
   **Unverified — nobody has looked at that panel.** A one-glance check, not a
   diagnosis.

---

## Corrections to earlier claims in this repo

| Claim | Location | Status |
|---|---|---|
| "updating itself daily" | `HANDOFF.md:3`, `:265`, `docs/client-guide.md:35` | **Now every 15 minutes.** |
| "Measured 9 August 2026" production table | `HANDOFF.md:767` | **Wrong source** — those are local dev numbers from 4 August. Production was never measured until 13 August. |
| "Losing the volume costs two and a half minutes" | `HANDOFF.md:758` | **No longer true** — it costs every rotated-out episode, permanently. |
| "The browser persists exactly two things" | `CLAUDE.md` | **Stale** — `clips.js` added a third, `localStorage["lhf-clips"]`, which is real user data. |
