"""Reproduce the fixed snapshot comparison from the command line."""
import json
from math import ceil
from statistics import median
from time import perf_counter

from .engine import match
from .models import MatchQuery, Profile, Vacancy
from .store import ROOT

KNOWN_INELIGIBLE = {"A01","A05","A23","A24","A25","A26","A27","A28"}
KNOWN_CLOSED = {"A10"}
PROBABLE_PAIRS = ({"A01","A02"},{"A13","A14"})


def rate(value, count):
    return {"n":value,"denominator":count,"rate":value / count if count else None}


def metrics(rows):
    ids = {r["id"] for r in rows}
    n = len(rows)
    return {
        "returned":n,
        "known_hard_violation":rate(len(ids & KNOWN_INELIGIBLE), n),
        "confirmed_closed_leakage":rate(len(ids & KNOWN_CLOSED), n),
        "probable_duplicate_extra_slot_rate":rate(sum(pair <= ids for pair in PROBABLE_PAIRS), n),
        "exact_duplicate_extra_slot_rate":rate(sum(bool(r["exact_duplicate_of"]) for r in rows),n),
        "needs_confirmation":rate(sum(r["decision"]=="Needs confirmation" for r in rows),n),
        "evidence_record_coverage":rate(sum(bool(r["evidence"]) for r in rows),n),
        "eligible_recall":None,
    }


def evaluate(repeats=100):
    profile = Profile.model_validate_json((ROOT / "data/profile.json").read_text())
    dataset = [Vacancy.model_validate(r) for r in json.loads((ROOT / "data/audit.json").read_text())]
    query = MatchQuery()
    result = match(dataset,profile,query)
    times = []
    for _ in range(repeats):
        started = perf_counter()
        match(dataset,profile,query)
        times.append((perf_counter()-started)*1000)
    full = match(dataset,profile,MatchQuery(k=len(dataset)))
    return {
        "as_of":str(query.as_of),"counts":result["counts"],"duplicate_warnings":result["duplicates"],
        "top10":{"baseline":metrics(result["baseline"]),"eligibility_aware":metrics(result["eligible"])},
        "top31":{"baseline":metrics(full["baseline"]),"eligibility_aware":metrics(full["eligible"])},
        "engine_ms":{"n":repeats,"median":round(median(times),3),"p95":round(sorted(times)[ceil(.95*repeats)-1],3)},
        "eligible_recall_note":"No independent positive ground-truth label set covering all constraints. Empty returned lists have undefined rates."
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(),indent=2))
