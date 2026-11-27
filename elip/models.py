from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Mode = Literal["onsite", "hybrid", "remote", "conditional_remote"]
JobType = Literal["internship", "full_time", "contract", "part_time"]
Status = Literal["open", "closed", "conflict", "unknown"]
Stage = Literal["penultimate", "final_year", "graduate", "other"]
Level = Literal["bachelors", "masters", "doctorate", "other"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Degree(Model):
    level: Level
    field: str | None = None
    completed: bool = False


class Profile(Model):
    degrees: list[Degree]
    graduation_year: int = Field(ge=2000, le=2100)
    academic_stage: Stage
    internship_months: int = Field(default=0, ge=0)
    industry_months: int = Field(default=0, ge=0)
    equivalent_months: int | None = Field(default=None, ge=0)
    curricular_internship: bool | None = None
    countries: list[str] = Field(min_length=1)
    cities: list[str] = Field(default_factory=list)
    modes: list[Mode] = Field(min_length=1)
    job_types: list[JobType] = Field(min_length=1)
    start_from: date
    start_to: date
    available_until: date | None = None
    duration_months: int = Field(ge=1, le=36)
    roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    preferred_cities: list[str] = Field(default_factory=list)
    preferred_modes: list[Mode] = Field(default_factory=list)
    expected_stipend_inr: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_window(self):
        if self.start_from > self.start_to or (
            self.available_until and self.available_until < self.start_to
        ):
            raise ValueError("Start dates must be ordered and within availability.")
        if any(len(c) != 2 or not c.isascii() or not c.isalpha() for c in self.countries):
            raise ValueError("Use two-letter ISO country codes.")
        return self


class Evidence(Model):
    date: date
    url: HttpUrl
    note: str = Field(min_length=1)


class Pay(Model):
    stage: Literal["stipend", "conversion_base", "conversion_ctc", "conversion_equity"]
    amount: int = Field(gt=0)
    currency: str = "INR"
    period: Literal["month", "year"]
    conditional: bool = False


class Vacancy(Model):
    id: str
    employer: str
    title: str
    provider: str | None = None
    req_id: str | None = None
    country: str | None = None
    cities: list[str] = Field(default_factory=list)
    mode: Mode | None = None
    remote_countries: list[str] | None = None
    job_type: JobType | None = None
    elip_type: str | None = None
    status: Status = "unknown"
    verified_at: date | None = None
    start_from: date | None = None
    start_to: date | None = None
    end_date: date | None = None
    duration_months: int | None = Field(default=None, ge=1)
    academic_stages: list[Stage] | None = None
    graduation_min: int | None = None
    graduation_max: int | None = None
    degree_levels: list[Level] | None = None
    degree_fields: list[str] | None = None
    degree_completed: bool = False
    minimum_experience_months: int | None = Field(default=None, ge=0)
    experience_basis: Literal["industry", "internship", "industry_equivalent"] | None = None
    curriculum_required: bool | None = None
    requirements_reviewed: bool = False
    role_family: str = ""
    skills: list[str] = Field(default_factory=list)
    mandatory_skills: list[str] = Field(default_factory=list)
    compensation: list[Pay] = Field(default_factory=list)
    source_url: HttpUrl
    elip_apply_url: HttpUrl | None = None
    evidence: list[Evidence] = Field(min_length=1)
    probable_group: str | None = None


class MatchQuery(Model):
    k: int = Field(default=10, ge=1, le=100)
    as_of: date = date(2026, 11, 27)
    freshness_days: int = Field(default=7, ge=1, le=365)
    dataset: Literal["audit", "synthetic", "regression"] = "audit"


class Observation(Model):
    result: Literal["open", "closed", "temporary_failure", "conflict"]
    source: HttpUrl
    note: str = Field(min_length=1)
    observed_at: datetime
    authoritative: bool = True

    @model_validator(mode="after")
    def require_timezone(self):
        if self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        self.observed_at = self.observed_at.astimezone(timezone.utc)
        return self
