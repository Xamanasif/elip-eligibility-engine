from fastapi.testclient import TestClient

from elip.app import create_app


def test_read_only_mode_blocks_persistence_and_keeps_the_audit_snapshot(tmp_path, monkeypatch):
    database = tmp_path / "audit.db"
    with TestClient(create_app(str(database), read_only=False)) as editable:
        saved = editable.get("/api/profile").json()
        saved["profile"]["countries"] = ["US"]
        assert editable.put("/api/profile", json=saved).status_code == 200
        assert editable.post("/api/vacancies/audit/A10/observations", json={
            "result": "open",
            "source": "https://example.com/employer",
            "note": "Regression fixture",
            "observed_at": "2026-11-27T23:00:00Z",
        }).status_code == 200

    monkeypatch.setenv("ELIP_READ_ONLY", "1")
    with TestClient(create_app(str(database))) as demo:
        standard = demo.get("/api/profile").json()
        assert demo.get("/api/profile?include_mode=true").json() == {**standard, "mode": "read_only"}
        assert standard["profile"]["countries"] == ["IN"]
        assert demo.put("/api/profile", json=standard).status_code == 403
        assert demo.post("/api/vacancies/audit/A10/observations", json={
            "result": "open",
            "source": "https://example.com/employer",
            "note": "Regression fixture",
            "observed_at": "2026-11-27T23:00:00Z",
        }).status_code == 403
        result = demo.post("/api/match", json={}).json()
        assert result["profile_version"] is None
        assert result["input_count"] == 31
        assert result["counts"] == {"Ineligible": 9, "Needs confirmation": 21, "Closed": 1}
        assert [row["id"] for row in result["groups"]["Closed"]] == ["A10"]
        assert result == demo.post("/api/match/demo", json={}).json()


def test_preview_is_isolated_and_does_not_create_a_database(tmp_path):
    database = tmp_path / "missing" / "sample.db"
    with TestClient(create_app(str(database), read_only=True)) as demo:
        original = demo.get("/api/profile").json()["profile"]
        modified = {**original, "countries": ["US"]}
        assert demo.post("/api/profile/preview", json=modified).json() == modified
        changed = demo.post("/api/match/preview", json={"dataset": "synthetic", "profile": modified}).json()
        assert changed["eligible"] == []
        fixed = demo.post("/api/match/demo", json={"dataset": "synthetic"}).json()
        assert [job["id"] for job in fixed["eligible"]] == ["S01"]
        assert demo.get("/api/profile").json()["profile"] == original
        assert demo.post("/api/match/preview", json={"profile": {**original, "countries": []}}).status_code == 422
    assert not database.exists()



def test_render_uses_read_only_mode_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("ELIP_READ_ONLY", raising=False)
    database = tmp_path / "demo.db"
    with TestClient(create_app(str(database))) as demo:
        result = demo.get("/api/profile?include_mode=true").json()
        assert result["mode"] == "read_only"
    assert not database.exists()


def test_explicit_mode_overrides_the_render_default(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("ELIP_READ_ONLY", "0")
    database = tmp_path / "demo.db"
    with TestClient(create_app(str(database))) as demo:
        result = demo.get("/api/profile?include_mode=true").json()
        assert result["mode"] == "editable"
    assert database.exists()
