PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL CHECK (version >= 1),
    profile_json TEXT NOT NULL CHECK (json_valid(profile_json))
);
CREATE TABLE IF NOT EXISTS vacancy (
    dataset TEXT NOT NULL,
    id TEXT NOT NULL,
    facts_json TEXT NOT NULL CHECK (json_valid(facts_json)),
    PRIMARY KEY (dataset, id)
);
CREATE TABLE IF NOT EXISTS verification (
    seq INTEGER PRIMARY KEY,
    dataset TEXT NOT NULL,
    vacancy_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    result TEXT NOT NULL,
    authoritative INTEGER NOT NULL,
    note TEXT NOT NULL,
    UNIQUE(dataset, vacancy_id, observed_at, source, result),
    FOREIGN KEY (dataset, vacancy_id) REFERENCES vacancy(dataset, id)
);
CREATE INDEX IF NOT EXISTS verification_order ON verification(dataset, vacancy_id, observed_at DESC);
