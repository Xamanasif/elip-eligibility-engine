from fastapi.testclient import TestClient

from elip.app import create_app


def test_demo_uses_reference_profile_without_saving_it(tmp_path):
    with TestClient(create_app(str(tmp_path / "demo.sqlite3"))) as client:
        payload = {"dataset": "synthetic"}
        original = client.get("/api/profile").json()
        altered = {**original, "profile": {**original["profile"], "countries": ["US"]}}
        response = client.put("/api/profile", json=altered)
        assert response.status_code == 200
        saved = response.json()
        assert client.post("/api/match", json=payload).json()["eligible"] == []

        demo = client.post("/api/match/demo", json=payload)
        assert demo.status_code == 200
        assert demo.json()["profile_version"] is None
        assert [job["id"] for job in demo.json()["eligible"]] == ["S01"]
        assert client.get("/api/profile").json() == saved


def test_demo_audit_preserves_original_decisions_and_duplicate_pairs(tmp_path):
    with TestClient(create_app(str(tmp_path / "audit.sqlite3"))) as client:
        original = client.post("/api/match", json={"dataset": "audit"}).json()
        demo = client.post("/api/match/demo", json={"dataset": "audit"}).json()
        assert demo["groups"] == original["groups"]
        assert demo["baseline"] == original["baseline"]
        assert demo["duplicates"] == original["duplicates"]
        assert demo["counts"] == {"Ineligible": 9, "Needs confirmation": 21, "Closed": 1}
        assert demo["eligible"] == []
        assert client.post("/api/match/demo", json={"dataset": "unknown"}).status_code == 422
