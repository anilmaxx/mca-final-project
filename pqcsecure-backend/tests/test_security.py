import importlib
import os


def test_api_key_required_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret")
    monkeypatch.delenv("EXPOSE_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("REQUIRE_HTTPS", raising=False)
    import app as backend_app
    importlib.reload(backend_app)

    client = backend_app.app.test_client()
    response = client.post("/api/keygen", data={"algorithm": "ML-KEM-768"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_private_key_not_exposed_by_default(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("EXPOSE_PRIVATE_KEY", "false")
    monkeypatch.delenv("REQUIRE_HTTPS", raising=False)
    import app as backend_app
    importlib.reload(backend_app)

    client = backend_app.app.test_client()
    response = client.post("/api/keygen", data={"algorithm": "ML-KEM-768"})

    assert response.status_code == 200
    payload = response.get_json()
    assert "private_key_pem" in payload
    assert payload["private_key_pem"] is None
