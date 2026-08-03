import importlib
import io
import os
import base64
from PIL import Image
import numpy as np


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


def test_api_allows_preflight_requests_from_react_frontend(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("REQUIRE_HTTPS", raising=False)
    import app as backend_app
    importlib.reload(backend_app)

    client = backend_app.app.test_client()
    response = client.options(
        "/api/keygen",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"


def test_end_to_end_encrypt_embed_and_extract_decrypt(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("EXPOSE_PRIVATE_KEY", "false")
    monkeypatch.delenv("REQUIRE_HTTPS", raising=False)
    import app as backend_app
    importlib.reload(backend_app)

    client = backend_app.app.test_client()
    keygen_resp = client.post("/api/keygen", data={"algorithm": "ML-KEM-768"})
    assert keygen_resp.status_code == 200
    session_id = keygen_resp.get_json()["session_id"]

    image = Image.fromarray(np.zeros((128, 128, 3), dtype=np.uint8), mode="RGB")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    encrypt_resp = client.post(
        "/api/encrypt-embed",
        data={
            "session_id": session_id,
            "message": "hello pqc secure",
            "kem_algo": "ML-KEM-768",
            "symmetric_mode": "AES-256-GCM",
            "bit_depth": 1,
            "image": (image_bytes, "cover.png"),
        },
        content_type="multipart/form-data",
    )

    assert encrypt_resp.status_code == 200, encrypt_resp.get_json()
    encrypt_body = encrypt_resp.get_json()
    assert "stego_image_b64" in encrypt_body
    assert encrypt_body["payload_bytes"] > 0

    stego_image_bytes = io.BytesIO(base64.b64decode(encrypt_body["stego_image_b64"]))
    extract_resp = client.post(
        "/api/extract-decrypt",
        data={
            "session_id": session_id,
            "kem_algo": "ML-KEM-768",
            "symmetric_mode": "AES-256-GCM",
            "bit_depth": 1,
            "stego_image": (stego_image_bytes, "stego.png"),
        },
        content_type="multipart/form-data",
    )

    assert extract_resp.status_code == 200, extract_resp.get_json()
    extract_body = extract_resp.get_json()
    assert extract_body["message"] == "hello pqc secure"
    assert extract_body["integrity_verified"] is True


def test_encrypt_embed_rejects_invalid_bit_depth(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("EXPOSE_PRIVATE_KEY", "false")
    monkeypatch.delenv("REQUIRE_HTTPS", raising=False)
    import app as backend_app
    importlib.reload(backend_app)

    client = backend_app.app.test_client()
    keygen_resp = client.post("/api/keygen", data={"algorithm": "ML-KEM-768"})
    assert keygen_resp.status_code == 200
    session_id = keygen_resp.get_json()["session_id"]

    image = Image.fromarray(np.zeros((128, 128, 3), dtype=np.uint8), mode="RGB")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    response = client.post(
        "/api/encrypt-embed",
        data={
            "session_id": session_id,
            "message": "hello",
            "kem_algo": "ML-KEM-768",
            "symmetric_mode": "AES-256-GCM",
            "bit_depth": 9,
            "image": (image_bytes, "cover.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "bit_depth" in response.get_json()["error"]
