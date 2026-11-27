from contextlib import contextmanager
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3

from .models import Evidence, Observation, Profile, Vacancy

ROOT = Path(__file__).resolve().parents[1]


class WriteConflict(Exception):
    pass


class Store:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript((ROOT / "elip/schema.sql").read_text())
            profile = Profile.model_validate_json((ROOT / "data/profile.json").read_text())
            db.execute("INSERT OR IGNORE INTO candidate VALUES (1, 1, ?)", (profile.model_dump_json(),))
            for dataset in ("audit", "synthetic", "regression"):
                for row in json.loads((ROOT / f"data/{dataset}.json").read_text()):
                    v = Vacancy.model_validate(row)
                    db.execute("INSERT OR IGNORE INTO vacancy VALUES (?, ?, ?)",
                               (dataset, v.id, v.model_dump_json()))

    def profile(self):
        with self.connect() as db:
            row = db.execute("SELECT version, profile_json FROM candidate WHERE id = 1").fetchone()
        return row["version"], Profile.model_validate_json(row["profile_json"])

    def save_profile(self, version: int, profile: Profile):
        with self.connect() as db:
            updated = db.execute("UPDATE candidate SET version = version + 1, profile_json = ? "
                                 "WHERE id = 1 AND version = ?", (profile.model_dump_json(), version))
            if updated.rowcount != 1:
                raise WriteConflict
        return version + 1

    def vacancies(self, dataset: str, as_of: date):
        with self.connect() as db:
            db.execute("BEGIN")
            jobs = db.execute("SELECT * FROM vacancy WHERE dataset = ? ORDER BY id", (dataset,)).fetchall()
            events = db.execute("SELECT * FROM verification WHERE dataset = ? AND substr(observed_at,1,10) <= ? "
                                "ORDER BY observed_at, seq", (dataset, str(as_of))).fetchall()
        by_id = {}
        for event in events:
            by_id.setdefault(event["vacancy_id"], []).append(event)
        return [resolve(Vacancy.model_validate_json(job["facts_json"]), by_id.get(job["id"], [])) for job in jobs]

    def record(self, dataset: str, job_id: str, observation: Observation):
        with self.connect() as db:
            row = db.execute("SELECT facts_json FROM vacancy WHERE dataset = ? AND id = ?", (dataset, job_id)).fetchone()
            if row is None:
                raise KeyError(job_id)
            db.execute("INSERT OR IGNORE INTO verification(dataset, vacancy_id, observed_at, source, result, "
                       "authoritative, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (dataset, job_id, observation.observed_at.isoformat(), str(observation.source),
                        observation.result, observation.authoritative, observation.note))
            events = db.execute("SELECT * FROM verification WHERE dataset = ? AND vacancy_id = ? "
                                "ORDER BY observed_at, seq", (dataset, job_id)).fetchall()
        vacancy = resolve(Vacancy.model_validate_json(row["facts_json"]), events)
        failures = 0
        for event in reversed(events):
            if event["result"] != "temporary_failure":
                break
            failures += 1
        delay = min(3600, 30 * 2 ** min(failures - 1, 7)) if failures else None
        retry_at = datetime.fromisoformat(events[-1]["observed_at"]) + timedelta(seconds=delay) if delay else None
        return {"vacancy": vacancy, "retry_at": retry_at, "retry_delay_seconds": delay, "attempts": len(events)}


def resolve(vacancy: Vacancy, events):
    usable = [event for event in events if event["authoritative"] and event["result"] != "temporary_failure"
              and (vacancy.verified_at is None or event["observed_at"][:10] >= str(vacancy.verified_at))]
    evidence = [*vacancy.evidence]
    for event in events:
        evidence.append(Evidence(date=date.fromisoformat(event["observed_at"][:10]), url=event["source"],
                                 note=f'{event["result"]}: {event["note"]}'))
    if not usable:
        return vacancy.model_copy(update={"evidence": evidence})
    newest = usable[-1]
    statuses = {event["result"] for event in usable if event["observed_at"] == newest["observed_at"]}
    status = statuses.pop() if len(statuses) == 1 else "conflict"
    return vacancy.model_copy(update={"evidence": evidence, "status": status,
                                      "verified_at": date.fromisoformat(newest["observed_at"][:10])})
