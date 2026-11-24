from fastapi.testclient import TestClient

import app as api


def test_health_reports_engine_state():
    response = TestClient(api.app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["package_loaded"], bool)
    assert isinstance(body["connected"], bool)


def test_status_keeps_live_trading_disabled():
    response = TestClient(api.app).get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["account_mode"] == "PRACTICE"
    assert body["trading_enabled"] is False


def test_live_account_connection_is_rejected():
    response = TestClient(api.app).post("/api/connect", json={"demo": False})
    assert response.status_code == 403


def test_missing_engine_is_reported_without_crashing(monkeypatch):
    monkeypatch.setattr(api, "Quotex", None)
    monkeypatch.setattr(api, "_IMPORT_ERROR", "engine not installed")
    monkeypatch.setenv("QUOTEX_EMAIL", "test@example.invalid")
    monkeypatch.setenv("QUOTEX_PASSWORD", "not-a-real-password")
    response = TestClient(api.app).post("/api/connect", json={"demo": True})
    assert response.status_code == 503
    assert "engine not installed" in response.json()["detail"]


def test_disconnect_is_idempotent():
    response = TestClient(api.app).post("/api/disconnect")
    assert response.status_code == 200
    assert response.json() == {"connected": False}


def test_study_snapshot_endpoint_returns_simulated_candles():
    response = TestClient(api.app).get("/api/study/snapshot?asset=EURUSD&period=60&limit=30")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "SIMULATED"
    assert len(body["candles"]) == 30
    assert body["disclaimer"]


def test_study_backtest_endpoint_returns_simulated_metrics():
    response = TestClient(api.app).get(
        "/api/study/backtest?asset=EURUSD&period=60&limit=120&fast=5&slow=15"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "SIMULATED_BACKTEST"
    assert body["candles_tested"] == 120
    assert body["total_trades"] == len(body["trades"])
    assert body["disclaimer"]


def test_study_backtest_rejects_fast_period_not_below_slow():
    response = TestClient(api.app).get(
        "/api/study/backtest?fast=21&slow=9"
    )
    assert response.status_code == 422


def test_study_signal_history_records_snapshot_requests():
    client = TestClient(api.app)
    client.get("/api/study/snapshot?asset=EURUSD&period=60&limit=30")
    response = client.get("/api/study/signals?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "SIMULATED"
    assert body["signals"]
    assert body["signals"][0]["asset"] == "EURUSD"
