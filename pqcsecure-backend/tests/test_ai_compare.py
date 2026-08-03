import io
import numpy as np
from PIL import Image

from app import app
import stego_ai


def test_ai_compare_endpoint_accepts_cover_and_stego_uploads():
    client = app.test_client()

    cover_arr = np.full((128, 128, 3), 120, dtype=np.uint8)
    cover = Image.fromarray(cover_arr, mode="RGB")
    buf_cover = io.BytesIO()
    cover.save(buf_cover, format="PNG")
    buf_cover.seek(0)

    stego_arr = np.full((128, 128, 3), 125, dtype=np.uint8)
    stego = Image.fromarray(stego_arr, mode="RGB")
    buf_stego = io.BytesIO()
    stego.save(buf_stego, format="PNG")
    buf_stego.seek(0)

    response = client.post(
        "/api/ai-compare",
        data={
            "cover_image": (io.BytesIO(buf_cover.getvalue()), "cover.png"),
            "stego_image": (io.BytesIO(buf_stego.getvalue()), "stego.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "cover" in payload
    assert "stego" in payload
    assert "comparison" in payload
    assert 0.0 <= payload["cover"]["stego_probability"] <= 1.0
    assert 0.0 <= payload["stego"]["stego_probability"] <= 1.0
    assert isinstance(payload["comparison"]["difference"], float)


def test_ai_detect_endpoint_returns_all_named_features():
    client = app.test_client()

    cover_arr = np.full((128, 128, 3), 120, dtype=np.uint8)
    cover = Image.fromarray(cover_arr, mode="RGB")
    buf_cover = io.BytesIO()
    cover.save(buf_cover, format="PNG")
    buf_cover.seek(0)

    response = client.post(
        "/api/ai-detect",
        data={"image": (io.BytesIO(buf_cover.getvalue()), "cover.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload["features"].keys()) == set(stego_ai.FEATURE_NAMES)
    assert len(payload["features"]) == len(stego_ai.FEATURE_NAMES)


def test_ai_train_endpoint_returns_training_summary():
    client = app.test_client()

    response = client.post(
        "/api/ai-train",
        data={"force": "true"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "trained"
    assert payload["force_retrained"] is True
    assert "best_params" in payload
    assert "model_path" in payload
