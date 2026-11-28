from contextlib import asynccontextmanager
import json
import os
from typing import Literal, get_args

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from .engine import match
from .models import MatchQuery, Model, Observation, Profile, Vacancy
from .store import ROOT, Store, WriteConflict

Dataset = Literal["audit", "synthetic", "regression"]


class ProfileUpdate(Model):
    version: int = Field(ge=1)
    profile: Profile


class PreviewQuery(MatchQuery):
    profile: Profile


def create_app(db_path=None, *, read_only: bool | None = None):
    if read_only is None:
        setting = os.getenv("ELIP_READ_ONLY", os.getenv("RENDER", ""))
        read_only = setting.strip().lower() in {"1", "true", "yes"}
    store = Store(db_path or os.getenv("ELIP_DB_PATH", str(ROOT / "var/engine.sqlite3")))
    snapshots: dict[Dataset, list[Vacancy]] = {}
    reference: Profile

    @asynccontextmanager
    async def lifespan(_):
        nonlocal reference
        reference = Profile.model_validate_json((ROOT / "data/profile.json").read_text(encoding="utf-8"))
        if read_only:
            for dataset in get_args(Dataset):
                rows = json.loads((ROOT / f"data/{dataset}.json").read_text(encoding="utf-8"))
                snapshots[dataset] = sorted((Vacancy.model_validate(row) for row in rows), key=lambda row: row.id)
        else:
            store.initialize()
        yield

    def vacancies(query: MatchQuery):
        if read_only:
            return snapshots[query.dataset]
        return store.vacancies(query.dataset, query.as_of)

    def require_writes():
        if read_only:
            raise HTTPException(403, "This snapshot is read-only. Use a profile preview to try changes.")

    app = FastAPI(title="Elip Eligibility Engine", version="1.0.0", lifespan=lifespan)

    @app.get("/api/profile")
    def get_profile(include_mode: bool = False):
        version, profile = (1, reference) if read_only else store.profile()
        response = {"version": version, "profile": profile}
        if include_mode:
            response["mode"] = "read_only" if read_only else "editable"
        return response

    @app.put("/api/profile")
    def put_profile(update: ProfileUpdate):
        require_writes()
        try:
            version = store.save_profile(update.version, update.profile)
        except WriteConflict as exc:
            raise HTTPException(409, "Profile changed. Reload before saving again.") from exc
        return {"version": version, "profile": update.profile}

    @app.post("/api/match")
    def run_match(query: MatchQuery):
        version, profile = (None, reference) if read_only else store.profile()
        return {"profile_version": version, **match(vacancies(query), profile, query)}

    @app.post("/api/profile/preview", response_model=Profile)
    def validate_preview(profile: Profile):
        return profile

    @app.post("/api/match/preview")
    def run_preview(query: PreviewQuery):
        return {"profile_version": None, **match(vacancies(query), query.profile, query)}

    @app.post("/api/match/demo")
    def run_demo_match(query: MatchQuery):
        return {"profile_version": None, **match(vacancies(query), reference, query)}

    @app.post("/api/vacancies/{dataset}/{vacancy_id}/observations")
    def record_observation(dataset: Dataset, vacancy_id: str, observation: Observation):
        require_writes()
        try:
            return store.record(dataset, vacancy_id, observation)
        except KeyError as exc:
            raise HTTPException(404, "Vacancy not found.") from exc

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(ROOT / "web/dist/index.html")

    app.mount("/assets", StaticFiles(directory=ROOT / "web/dist/assets", check_dir=False), name="assets")
    return app


app = create_app()
