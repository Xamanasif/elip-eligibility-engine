from datetime import date
import json

import pytest
from elip.engine import decide, duplicates, match
from elip.models import MatchQuery, Profile, Vacancy
from elip.store import ROOT


@pytest.fixture
def profile():
    return Profile.model_validate_json((ROOT / "data/profile.json").read_text())


@pytest.fixture
def job():
    return Vacancy.model_validate(json.loads((ROOT / "data/synthetic.json").read_text())[0])


@pytest.mark.parametrize(("updates","outcome","reason"), [
    ({}, "Eligible", "STATUS_OPEN"),
    ({"country":"MY"}, "Ineligible", "COUNTRY"),
    ({"status":"closed"}, "Closed", "VACANCY_CLOSED"),
    ({"job_type":"full_time"}, "Ineligible", "EMPLOYMENT_TYPE"),
    ({"academic_stages":["penultimate"]}, "Ineligible", "ACADEMIC_STAGE"),
    ({"graduation_min":2028}, "Ineligible", "GRADUATION_YEAR"),
    ({"degree_fields":["Computer Science"]}, "Ineligible", "DEGREE"),
    ({"degree_completed":True}, "Ineligible", "DEGREE"),
    ({"degree_levels":["masters"],"degree_fields":["Biology"]}, "Needs confirmation", "DEGREE"),
    ({"minimum_experience_months":24,"experience_basis":"industry"}, "Ineligible", "EXPERIENCE"),
    ({"minimum_experience_months":12,"experience_basis":"industry_equivalent"}, "Needs confirmation", "EXPERIENCE"),
    ({"minimum_experience_months":6,"experience_basis":"internship"}, "Eligible", "EXPERIENCE"),
    ({"curriculum_required":True}, "Needs confirmation", "CURRICULUM"),
    ({"duration_months":3}, "Ineligible", "DURATION"),
    ({"duration_months":None}, "Needs confirmation", "DURATION"),
    ({"start_from":date(2026,11,1),"start_to":date(2026,11,7)}, "Ineligible", "START_WINDOW"),
    ({"start_from":None,"start_to":None}, "Needs confirmation", "START_WINDOW"),
    ({"end_date":date(2027,7,1)}, "Ineligible", "AVAILABLE_UNTIL"),
    ({"mode":"conditional_remote","remote_countries":["IN"]}, "Needs confirmation", "REMOTE_PERMISSION"),
    ({"mode":"remote","remote_countries":["US"]}, "Ineligible", "REMOTE_PERMISSION"),
    ({"mode":"remote","remote_countries":None}, "Needs confirmation", "REMOTE_PERMISSION"),
    ({"mode":"remote","remote_countries":["IN"],"country":"US"}, "Eligible", "REMOTE_PERMISSION"),
    ({"status":"conflict"}, "Needs confirmation", "STATUS_CONFLICT"),
    ({"status":"unknown"}, "Needs confirmation", "STATUS_UNVERIFIED"),
    ({"verified_at":date(2026,11,1)}, "Needs confirmation", "STATUS_STALE"),
    ({"requirements_reviewed":False}, "Needs confirmation", "REQUIREMENTS_INCOMPLETE"),
])
def test_decisions(job, profile, updates, outcome, reason):
    result, reasons = decide(job.model_copy(update=updates), profile, MatchQuery())
    assert result == outcome
    assert any(r.code == reason and r.evidence_url.startswith("https://") for r in reasons)


def test_exact_identity_and_distinct_ids(job):
    first = job.model_copy(update={"employer":"Fam"})
    copy = job.model_copy(update={"employer":"Fampay","id":"S99"})
    distinct = job.model_copy(update={"employer":"Fam","id":"S98","req_id":"different"})
    exact, likely = duplicates([first,copy,distinct])
    assert exact == {"S99":first.id}
    assert likely == []


def test_probable_dup_retained(job, profile):
    second = job.model_copy(update={"id":"S98","req_id":None})
    results = match([job,second],profile,MatchQuery())
    assert results["duplicates"] == [{"kind":"probable","ids":["S01","S98"]}]
    assert len(results["eligible"]) == 2


def test_exact_duplicate_conflict_not_promoted(job, profile):
    closed = job.model_copy(update={"id":"S99","status":"closed"})
    assert match([job,closed],profile,MatchQuery())["eligible"] == []


def test_similarity_does_not_override_country(job, profile):
    bad = job.model_copy(update={"id":"S99","req_id":"bad","country":"MY"})
    weaker = job.model_copy(update={"skills":[],"role_family":"support","title":"Support internship"})
    result = match([bad,weaker], profile, MatchQuery())
    assert result["baseline"][0]["id"] == bad.id
    assert [row["id"] for row in result["eligible"]] == [weaker.id]


def test_empty_input(profile):
    result = match([],profile,MatchQuery())
    assert result["input_count"] == 0 and result["eligible"] == result["baseline"] == []


def test_compensation_stage_regression(profile):
    job = Vacancy.model_validate(json.loads((ROOT / "data/regression.json").read_text())[0])
    pay = {item.stage: item for item in job.compensation}
    assert pay["stipend"].amount == 75000 and pay["stipend"].period == "month"
    assert pay["conversion_base"].amount == 150000 and pay["conversion_base"].conditional
    assert pay["conversion_equity"].amount == 700000
    assert decide(job,profile,MatchQuery())[0] == "Needs confirmation"
