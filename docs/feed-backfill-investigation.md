# Complete archive backfill investigation — 26 August 2026

This records the live Podbean audit prompted by the client's request for the
complete runs of *Labor Heritage Power Hour*, *Your Rights at Work*, and
*Labor History Today*.

## Result

The RSS feeds still expose only the newest 100 episodes per channel. Query
parameters do not extend that window.

The public Podbean archive pages are a separate and usable source. Their
`/page/N/` routes are server-rendered and expose both JSON-LD and the page's
initial application state. The latter carries every field needed by the
existing catalogue: Podbean id, title, description HTML, publication time,
duration, episode permalink, artwork, audio URL, media type, and transcript URL
where one exists.

No Podbean credentials are required for this published backlog. The measured
last pages are [Your Rights at Work / Power Hour page 37](https://yourrightsatwork.podbean.com/page/37/)
and [Labor History Today page 47](https://laborhistorytoday.podbean.com/page/47/).

## Measured catalogue

Every advertised page was fetched and parsed, not estimated from a sample.

| Program | Public Podbean range | Episodes |
|---|---:|---:|
| Labor Heritage Power Hour | 14 Apr 2023 → 20 Aug 2026 | 181 |
| Your Rights at Work | 5 Mar 2020 → 13 Apr 2023 | 185 |
| Labor History Today | 27 Oct 2017 → 23 Aug 2026 | 419 |
| **Total** |  | **785** |

The first two programs share the `yourrightsatwork.podbean.com` channel, which
contains 366 episodes across 37 pages. The split above uses the client-supplied
first *Power Hour* episode, “Working Class Giant,” as the boundary: that episode
and everything newer are *Power Hour*; everything older is *Your Rights at
Work*. Podbean itself exposes one series name for the combined channel, not a
per-episode program field.

`laborhistorytoday.podbean.com` contains 419 unique episodes across 47 pages.

Across all 785 records:

- 785 have a unique Podbean id, title, description, publication timestamp,
  duration, episode URL, artwork, and direct audio URL.
- 175 expose a transcript URL. The current local database accounts for 148 of
  those; 27 transcript-bearing episodes are in the newly reachable backlog.
- All 203 episodes in the retained local database matched a public-page episode
  by permalink. The public pages contain 582 additional episodes relative to
  that database. Against the client's observed 200-episode production state,
  the difference is 585.

The three requested endpoints were confirmed directly:

- “Coronavirus and worker rights” — 5 March 2020, with playable audio.
- “Working Class Giant” — 14 April 2023, with playable audio.
- “Our First Show: Black Tuesday, Philly's General Strike & Debs Gets a Million
  Votes” — 27 October 2017, with playable audio.

## Implementation status

**Built and verified locally on 26 August 2026; not yet run in production.**
`ingest/backfill.py` is a one-time, resumable public-page backfill command.
Fresh Docker volumes run it automatically in the background before the normal
RSS/transcript/enrichment pipeline. Existing production volumes require the
one-time command explicitly.

1. Pages through both public archives and parses the embedded episode records.
2. Matches existing rows by normalized episode permalink before inserting. RSS
   GUIDs are not present on the archive pages, so using an invented GUID alone
   would duplicate the 203 rows already held.
3. Stores the stable Podbean episode id as the backfilled record's source key;
   retains the permalink for cross-source matching.
4. Creates a third `shows` row for *Your Rights at Work* and assigns the shared
   channel's episodes using the confirmed 14 April 2023 boundary.
5. Runs safely before or after RSS: RSS upgrades a page-first synthetic identity
   to the real GUID without duplication.

The isolated full run produced 785 unique GUIDs and permalinks, 546.9 hours,
17,316 transcript passages, 236 retained entities and 70 re-air relationships.
A second unchanged public-page pass made zero updates across all 785 rows. The
search API now reports the true 785-row total while returning deterministic
50-row pages. The initial page is 103 KB raw / 24 KB gzipped and took about
0.04 seconds locally; the separate export path still returns all matching rows.

Keep RSS as the ongoing update source: it is documented, cheap through ETags,
and carries stable GUIDs. Treat the public-page parser as a recovery tool because
Podbean can change its website markup without notice.

## Supported fallback

Podbean's official API remains the more stable long-term option. Its
[authenticated episode-list endpoint](https://developers.podbean.com/podbean-api-docs/#api-Episode-Get_Episodes),
`GET /v1/episodes`, supports `offset`, `limit`, and a `has_more` response. It
needs a Podbean developer client id and secret plus an access token with
episode-read access. Credentials are not needed to perform the current
backfill, but the API is the fallback if Podbean changes the public archive
pages before the recovery is complete.
