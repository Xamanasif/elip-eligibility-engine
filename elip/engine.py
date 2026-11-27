from calendar import monthrange
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from difflib import SequenceMatcher
import re

from sklearn.feature_extraction.text import TfidfVectorizer

from .models import MatchQuery, Profile, Vacancy

OUTCOMES = ("Eligible", "Ineligible", "Needs confirmation", "Closed")


def normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def employer_key(value: str) -> str:
    name = normalize(value)
    return {"fampay": "fam", "famapp": "fam"}.get(name, name)


@dataclass
class Reason:
    code: str
    result: str
    value: str
    evidence_url: str


def shift_months(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def decide(v: Vacancy, p: Profile, q: MatchQuery):
    reasons: list[Reason] = []

    def add(code, passed, value):
        outcome = "pass" if passed is True else "fail" if passed is False else "unknown"
        reasons.append(Reason(code, outcome, value, str(v.source_url)))

    if v.status == "closed":
        add("VACANCY_CLOSED", False, "Employer evidence confirms closure.")
        return "Closed", reasons

    if v.status == "conflict":
        add("STATUS_CONFLICT", None, "Employer and listing sources disagree.")
    elif v.status != "open" or v.verified_at is None:
        add("STATUS_UNVERIFIED", None, "No verified open state.")
    elif not 0 <= (q.as_of - v.verified_at).days <= q.freshness_days:
        add("STATUS_STALE", None, f"Last verified {v.verified_at}.")
    else:
        add("STATUS_OPEN", True, f"Last verified {v.verified_at}.")

    add("EMPLOYMENT_TYPE", v.job_type in p.job_types if v.job_type else None, v.job_type or "Unknown")
    if v.mode in ("remote", "conditional_remote"):
        common = set(v.remote_countries or []) & {c.upper() for c in p.countries}
        remote_ok = bool(common) if v.remote_countries is not None else None
        if v.mode == "conditional_remote" and remote_ok is True:
            remote_ok = None
        if "remote" not in p.modes:
            remote_ok = False
        add("REMOTE_PERMISSION", remote_ok, f"{v.mode} · {v.remote_countries or 'scope unspecified'}")
    else:
        add("COUNTRY", v.country in {c.upper() for c in p.countries} if v.country else None, v.country or "Unknown")
        add("WORK_MODE", v.mode in p.modes if v.mode else None, v.mode or "Unknown")
        if p.cities:
            common = {normalize(c) for c in p.cities} & {normalize(c) for c in v.cities}
            add("CITY", bool(common) if v.cities else None, ", ".join(v.cities) or "Unknown")

    if v.academic_stages:
        add("ACADEMIC_STAGE", p.academic_stage in v.academic_stages, ", ".join(v.academic_stages))
    if v.graduation_min is not None or v.graduation_max is not None:
        add("GRADUATION_YEAR", (v.graduation_min or 0) <= p.graduation_year <= (v.graduation_max or 9999),
            f"{v.graduation_min or 'any'} to {v.graduation_max or 'any'}")
    if v.degree_levels or v.degree_fields:
        candidates = [d for d in p.degrees if (not v.degree_levels or d.level in v.degree_levels)
                      and (not v.degree_completed or d.completed)]
        fields = {normalize(f) for f in v.degree_fields or []}
        matches = any(not fields or normalize(d.field or "") in fields for d in candidates)
        unknown = any(d.field is None for d in candidates)
        add("DEGREE", True if matches else None if unknown and fields else False,
            f"{v.degree_levels or 'any level'} · {v.degree_fields or 'field not narrowed'}")
    if v.curriculum_required:
        add("CURRICULUM", p.curricular_internship, "Mandatory academic placement.")
    if v.minimum_experience_months is not None:
        months = {"industry": p.industry_months, "internship": p.internship_months,
                  "industry_equivalent": p.equivalent_months}.get(v.experience_basis)
        passed = True if v.minimum_experience_months == 0 else (
            months >= v.minimum_experience_months if months is not None else None
        )
        add("EXPERIENCE", passed, f"{v.minimum_experience_months} months · {v.experience_basis or 'basis unspecified'}")
    if v.mandatory_skills:
        missing = {normalize(s) for s in v.mandatory_skills} - {normalize(s) for s in p.skills}
        add("MANDATORY_SKILL", not missing, ", ".join(sorted(missing)) or "Required skills present.")

    start, end = v.start_from, v.start_to or v.start_from
    feasible_start = max(start, p.start_from) if start else None
    add("START_WINDOW", feasible_start <= min(end, p.start_to) if feasible_start else None,
        f"{start} to {end}" if start else "No start window verified.")
    add("DURATION", v.duration_months == p.duration_months if v.duration_months else None,
        f"{v.duration_months} months" if v.duration_months else "No duration verified.")
    if p.available_until:
        finish = v.end_date
        if finish:
            add("AVAILABLE_UNTIL", finish <= p.available_until, str(finish))
        else:
            estimate = shift_months(min(end, p.start_to), v.duration_months) - timedelta(days=1) if end and v.duration_months else None
            add("AVAILABLE_UNTIL", True if estimate and estimate <= p.available_until else None,
                f"Calendar-month estimate {estimate}; confirm exact end date." if estimate else "End date unknown.")
    if not v.requirements_reviewed:
        add("REQUIREMENTS_INCOMPLETE", None, "Full set of employer screening rules is unverified.")

    if any(r.result == "fail" for r in reasons):
        return "Ineligible", reasons
    if any(r.result == "unknown" for r in reasons):
        return "Needs confirmation", reasons
    return "Eligible", reasons


def identity(v: Vacancy):
    return (employer_key(v.employer), v.provider.casefold(), v.req_id.casefold()) if v.provider and v.req_id else None


def duplicates(vacancies: list[Vacancy]):
    exact, likely = {}, set()
    for i, left in enumerate(vacancies):
        for right in vacancies[i + 1:]:
            if employer_key(left.employer) != employer_key(right.employer):
                continue
            if identity(left) and identity(left) == identity(right):
                exact[right.id] = exact.get(left.id, left.id)
                continue
            if left.provider == right.provider and left.req_id and right.req_id:
                continue
            tagged = left.probable_group and left.probable_group == right.probable_group
            similar = SequenceMatcher(None, normalize(left.title), normalize(right.title)).ratio() >= .90
            same_city = {normalize(c) for c in left.cities} & {normalize(c) for c in right.cities}
            if tagged or (similar and same_city):
                likely.add(tuple(sorted((left.id, right.id))))
    return exact, sorted(likely)


def compute_scores(vacancies, p, q):
    if not vacancies:
        return []
    texts = [normalize(" ".join(p.roles)) or "role"]
    texts += [normalize(f"{v.role_family} {v.title}") or "role" for v in vacancies]
    matrix = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b").fit_transform(texts)
    similarity = (matrix[1:] @ matrix[0].T).toarray().ravel()
    skills = {normalize(s) for s in p.skills}
    preferred_cities = {normalize(c) for c in p.preferred_cities}
    scores = []
    for sim, v in zip(similarity, vacancies):
        listed = {normalize(s) for s in v.skills}
        overlap = len(listed & skills) / max(1, len(listed))
        city = bool(preferred_cities & {normalize(c) for c in v.cities})
        mode = v.mode in p.preferred_modes
        stipend = next((x.amount for x in v.compensation if x.stage == "stipend" and x.currency == "INR"
                        and x.period == "month"), None)
        pay = p.expected_stipend_inr is not None and stipend is not None and stipend >= p.expected_stipend_inr
        fresh = 0 if v.verified_at is None else max(0, 1 - abs((q.as_of - v.verified_at).days) / q.freshness_days)
        scores.append(round(float(.60 * sim + .25 * overlap + .025 * city + .025 * mode + .025 * pay + .075 * fresh), 5))
    return scores


def match(vacancies: list[Vacancy], p: Profile, q: MatchQuery):
    exact, likely = duplicates(vacancies)
    # Every input is evaluated before a relevance score is used. The baseline can
    # surface any outcome, while only eligible canonical vacancies enter the shortlist.
    decisions = [decide(v, p, q) for v in vacancies]
    scores = compute_scores(vacancies, p, q)
    rows = []
    for v, (decision, reasons), score in zip(vacancies, decisions, scores):
        rows.append({**v.model_dump(mode="json"), "decision": decision, "score": score,
                     "reasons": [asdict(r) for r in reasons], "exact_duplicate_of": exact.get(v.id)})
    rank = lambda row: (-row["score"], row["id"])
    baseline = sorted(rows, key=rank)[:q.k]
    groups = {key: [] for key in OUTCOMES}
    for row in rows:
        groups[row["decision"]].append(row)
    canonical = defaultdict(list)
    for row in rows:
        canonical[exact.get(row["id"], row["id"])].append(row)
    safe = [min(group, key=rank) for group in canonical.values()
            if all(r["decision"] == "Eligible" for r in group)]
    eligible = sorted(safe, key=rank)[:q.k]
    warnings = [{"kind": "exact", "ids": [root, copy]} for copy, root in exact.items()]
    warnings += [{"kind": "probable", "ids": list(pair)} for pair in likely]
    return {"input_count": len(rows), "baseline": baseline, "eligible": eligible,
            "groups": groups, "duplicates": warnings, "k": q.k,
            "counts": dict(Counter(r["decision"] for r in rows))}
