from contextlib import asynccontextmanager
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from .engine import match
from .models import MatchQuery, Model, Observation, Profile
from .store import ROOT, Store, WriteConflict

Dataset = Literal["audit", "synthetic", "regression"]


class ProfileUpdate(Model):
    version: int = Field(ge=1)
    profile: Profile


def create_app(db_path=None):
    store = Store(db_path or os.getenv("ELIP_DB_PATH", str(ROOT / "var/engine.sqlite3")))

    @asynccontextmanager
    async def lifespan(_):
        store.initialize()
        yield

    app = FastAPI(title="Elip Eligibility Engine", version="1.0.0", lifespan=lifespan)

    @app.get("/api/profile")
    def get_profile():
        version, profile = store.profile()
        return {"version": version, "profile": profile}

    @app.put("/api/profile")
    def put_profile(update: ProfileUpdate):
        try:
            version = store.save_profile(update.version, update.profile)
        except WriteConflict as exc:
            raise HTTPException(409, "Profile changed. Reload before saving again.") from exc
        return {"version": version, "profile": update.profile}

    @app.post("/api/match")
    def run_match(query: MatchQuery):
        version, profile = store.profile()
        return {"profile_version": version, **match(store.vacancies(query.dataset, query.as_of), profile, query)}

    @app.post("/api/match/demo")
    def run_demo_match(query: MatchQuery):
        reference = Profile.model_validate_json((ROOT / "data/profile.json").read_text(encoding="utf-8"))
        return {"profile_version": None, **match(store.vacancies(query.dataset, query.as_of), reference, query)}

    @app.post("/api/vacancies/{dataset}/{vacancy_id}/observations")
    def record_observation(dataset: Dataset, vacancy_id: str, observation: Observation):
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
