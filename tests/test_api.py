from fastapi.testclient import TestClient
import pytest

from elip.app import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "test.db"))) as http:
        yield http


def test_original_audit_cohort(client):
    response = client.post("/api/match", json={})
    assert response.status_code == 200
    out = response.json()
    assert out["input_count"] == 31
    failed = {x["id"] for x in out["groups"]["Ineligible"]}
    assert {"A01","A05","A23","A24","A25","A26","A27","A28"} <= failed
    assert [x["id"] for x in out["groups"]["Closed"]] == ["A10"]
    assert {tuple(x["ids"]) for x in out["duplicates"] if x["kind"] == "probable"} == {
        ("A01","A02"), ("A13","A14")
    }


@pytest.mark.parametrize("body", [{"k":0},{"k":101},{"freshness_days":0},{"dataset":"live"},{ "typo":True}])
def test_api_validation(client,body):
    assert client.post("/api/match",json=body).status_code == 422


def test_profile_persistence_and_revision(client):
    snapshot = client.get("/api/profile").json()
    snapshot["profile"]["duration_months"] = 3
    assert client.put("/api/profile",json=snapshot).status_code == 200
    updated = client.get("/api/profile").json()
    assert updated["profile"]["duration_months"] == 3
    assert updated["version"] == snapshot["version"] + 1
    assert client.put("/api/profile",json=snapshot).status_code == 409


def test_profile_date_validation(client):
    snapshot = client.get("/api/profile").json()
    snapshot["profile"]["start_from"] = "2027-02-01"
    assert client.put("/api/profile",json=snapshot).status_code == 422


def obs(client,result,when,source="https://example.com/source", id="S01"):
    return client.post(f"/api/vacancies/synthetic/{id}/observations",json={
        "result":result,"observed_at":when,"source":source,"note":"Fixture event"
    })


def test_source_retries_keep_evidence(client):
    first = obs(client,"temporary_failure","2026-11-27T08:00:00Z").json()
    second = obs(client,"temporary_failure","2026-11-27T08:01:00Z").json()
    assert first["retry_delay_seconds"] == 30
    assert second["retry_delay_seconds"] == 60
    assert second["vacancy"]["status"] == "open"
    assert len(second["vacancy"]["evidence"]) == 3


def test_status_conflict_retry_and_reopen(client):
    when = "2026-11-27T09:00:00Z"
    assert obs(client,"closed",when).json()["vacancy"]["status"] == "closed"
    assert obs(client,"open",when,"https://example.com/alternate").json()["vacancy"]["status"] == "conflict"
    assert obs(client,"open","2026-11-27T10:00:00Z").json()["vacancy"]["status"] == "open"
    assert obs(client,"closed","2026-11-27T08:00:00Z").json()["vacancy"]["status"] == "open"
    attempts = obs(client,"open","2026-11-27T10:00:00Z").json()["attempts"]
    assert attempts == 4


def test_unknown_vacancy_returns_404(client):
    assert obs(client,"open","2026-11-27T09:00:00Z",id="unknown").status_code == 404
