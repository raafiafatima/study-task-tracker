-- Study Task Tracker schema. Safe to run more than once.
-- Run as the database owner/administrator, never as the runtime app user.

CREATE TABLE IF NOT EXISTS tasks (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title      VARCHAR(120) NOT NULL CHECK (char_length(btrim(title)) > 0),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tasks_newest_first_idx ON tasks (created_at DESC, id DESC);
