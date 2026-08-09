-- LHF Digital Asset Manager — schema
-- SQLite + FTS5. Everything keys off the RSS <guid>, which is stable
-- across Podbean edits (title and audio URL are not).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS shows (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    feed_url    TEXT NOT NULL,
    site_url    TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS episodes (
    id               INTEGER PRIMARY KEY,
    show_id          INTEGER NOT NULL REFERENCES shows(id),
    guid             TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    published_at     TEXT,              -- ISO 8601
    duration_sec     INTEGER,
    episode_url      TEXT,              -- Podbean page (stable)
    audio_url        TEXT,              -- direct MP3 (may rot)
    image_url        TEXT,
    description_html TEXT,              -- original; hyperlinks are a guest signal
    description_text TEXT,              -- stripped, for search + extraction
    is_encore        INTEGER DEFAULT 0, -- detected "(Encore)" / "Encore:" in title

    -- Podcast 2.0 <podcast:transcript> — 145 of 200 episodes publish a .srt
    -- straight from the producers' editing workflow. Free and timestamped.
    transcript_url    TEXT,
    transcript_type   TEXT,                     -- application/srt | application/json

    transcript_status TEXT DEFAULT 'pending',   -- pending|done|failed|missing
    transcript_source TEXT,                     -- feed|google|descript
    transcript_text   TEXT,
    extracted_at      TEXT,

    first_seen_at TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),

    -- Stamped every time this episode is seen in the feed, and by nothing else.
    -- Podbean serves only the most recent 100 per show, and both shows are at
    -- that number, so from here on one episode rotates out of reach each week
    -- while this row keeps it. An episode whose stamp stops advancing has left
    -- the feed — which is how the archive knows what only it still holds.
    --
    -- updated_at cannot answer that question: transcripts.py writes to it too,
    -- so it means "something changed" rather than "the feed still has this".
    last_seen_in_feed TEXT
);

CREATE INDEX IF NOT EXISTS idx_episodes_show      ON episodes(show_id);
CREATE INDEX IF NOT EXISTS idx_episodes_published ON episodes(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_tstatus   ON episodes(transcript_status);

-- People and topics: populated by the AI extraction pass (Tier 2).
-- normalized_name is the dedup hook — lowercase, punctuation and
-- honorifics stripped — so "Dr. Jeffrey Johnson" and "Jeffrey Johnson"
-- collapse to one record instead of two.
CREATE TABLE IF NOT EXISTS people (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    bio_url         TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS episode_people (
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    person_id  INTEGER NOT NULL REFERENCES people(id)   ON DELETE CASCADE,
    role       TEXT NOT NULL,          -- guest|host|interviewer|mentioned
    confidence REAL,
    PRIMARY KEY (episode_id, person_id, role)
);

CREATE TABLE IF NOT EXISTS topics (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS episode_topics (
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    topic_id   INTEGER NOT NULL REFERENCES topics(id)   ON DELETE CASCADE,
    confidence REAL,
    PRIMARY KEY (episode_id, topic_id)
);

-- Transcript chunks. Source-agnostic on purpose: Descript SRT, Google
-- BatchRecognize results, or anything else all land here the same way.
CREATE TABLE IF NOT EXISTS segments (
    id          INTEGER PRIMARY KEY,
    episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    start_sec   REAL,
    end_sec     REAL,
    speaker_tag TEXT,
    text        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_segments_episode ON segments(episode_id, start_sec);

-- Internal-only staff notes: the "have we already run this" workflow.
CREATE TABLE IF NOT EXISTS episode_notes (
    id          INTEGER PRIMARY KEY,
    episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    body        TEXT,
    replayed_at TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Full-text search. Contentless-linked to episodes via rowid so we don't
-- duplicate the text; triggers keep it in sync.
-- Tokenizer choice matters here and is deliberate.
--
-- porter (stemming) was tried first and rejected: it stores stems, so a
-- prefix query can't match mid-word. Typing "organizing" one letter at a
-- time collapsed to zero results at "organizi" before snapping back — which
-- breaks both as-you-type search and explicit truncation.
--
-- unicode61 stores whole words, so `organiz*` matches organize/organized/
-- organizing/organizers — the same recall stemming gave, but explicit and
-- predictable, which is what a cataloguer expects. `prefix` builds real
-- prefix indexes at 2-4 characters so incremental search stays fast.
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    title,
    description_text,
    transcript_text,
    content = 'episodes',
    content_rowid = 'id',
    tokenize = "unicode61 remove_diacritics 2",
    prefix = '2 3 4'
);

CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, title, description_text, transcript_text)
    VALUES (new.id, new.title, new.description_text, new.transcript_text);
END;

CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, title, description_text, transcript_text)
    VALUES ('delete', old.id, old.title, old.description_text, old.transcript_text);
END;

CREATE TRIGGER IF NOT EXISTS episodes_au AFTER UPDATE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, title, description_text, transcript_text)
    VALUES ('delete', old.id, old.title, old.description_text, old.transcript_text);
    INSERT INTO episodes_fts(rowid, title, description_text, transcript_text)
    VALUES (new.id, new.title, new.description_text, new.transcript_text);
END;

-- Passage-level index. episodes_fts answers "which episodes discuss this";
-- this answers "where exactly was it said", which is what a timestamp link
-- needs. Both are required — they're different questions.
CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    text,
    content = 'segments',
    content_rowid = 'id',
    tokenize = "unicode61 remove_diacritics 2",
    prefix = '2 3 4'
);

CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segments BEGIN
    INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS segments_ad AFTER DELETE ON segments BEGIN
    INSERT INTO segments_fts(segments_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS segments_au AFTER UPDATE ON segments BEGIN
    INSERT INTO segments_fts(segments_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
END;
