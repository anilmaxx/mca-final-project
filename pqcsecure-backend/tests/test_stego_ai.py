import os
import pickle
import pytest
from PIL import Image
import numpy as np
import stego_ai
import steganography

def test_extract_stego_features():
    # Create a simple 256x256 RGB image
    img_arr = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    img = Image.fromarray(img_arr, mode="RGB")
    
    features = stego_ai.extract_stego_features(img)
    assert len(features) == 7
    for f in features:
        assert isinstance(f, float)

def test_predict_stego():
    img_arr = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    img = Image.fromarray(img_arr, mode="RGB")
    
    prob = stego_ai.predict_stego(img)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0

def test_analyze_cover_image():
    img_arr = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    img = Image.fromarray(img_arr, mode="RGB")
    
    analysis = stego_ai.analyze_cover_image(img)
    assert "global_texture_score" in analysis
    assert "safety_rating" in analysis
    assert "recommended_bit_depth" in analysis
    assert "high_frequency_regions" in analysis
    assert "image_dimensions" in analysis
    
    assert isinstance(analysis["global_texture_score"], float)
    assert isinstance(analysis["recommended_bit_depth"], int)
    assert isinstance(analysis["high_frequency_regions"], list)
    assert len(analysis["high_frequency_regions"]) <= 3


def test_analyze_cover_image_considers_message_size():
    img = Image.new("RGB", (256, 256), color=(120, 120, 120))
    message = "A" * 1200
    analysis = stego_ai.analyze_cover_image(img, message=message, kem_algo="RSA-2048")

    assert "recommended_bit_depth" in analysis
    assert analysis["recommended_bit_depth"] in (1, 2, 3)
    assert stego_ai._estimate_payload_size(message, "RSA-2048") <= steganography.max_payload_bytes(
        img, analysis["recommended_bit_depth"]
    )

def test_detects_embedded_payload_on_smooth_image():
    cover_arr = np.full((512, 512, 3), 120, dtype=np.uint8)
    cover = Image.fromarray(cover_arr, mode="RGB")
    stego = steganography.embed(cover, b"X" * 8000, bit_depth=3)

    cover_prob = stego_ai.predict_stego(cover)
    stego_prob = stego_ai.predict_stego(stego)

    assert 0.0 <= cover_prob <= 1.0
    assert 0.0 <= stego_prob <= 1.0
    assert stego_prob > cover_prob
    assert stego_prob >= 0.6


def test_init_model():
    # Verify init_model runs without error and sets up model file if missing
    stego_ai.init_model(force_train=False)
    assert stego_ai._clf is not None or os.path.exists(stego_ai.MODEL_PATH)


def test_init_model_retrains_when_pickle_is_stale(tmp_path, monkeypatch):
    stale_model = tmp_path / "stego_model.pkl"
    stale_meta = tmp_path / "stego_model.meta.json"
    monkeypatch.setattr(stego_ai, "MODEL_PATH", str(stale_model))
    monkeypatch.setattr(stego_ai, "MODEL_META_PATH", str(stale_meta))

    with open(stale_model, "wb") as f:
        pickle.dump("not-a-real-model", f)

    stale_meta.write_text('{"sklearn_version": "0.0.0", "model_format_version": "stale"}', encoding="utf-8")

    stego_ai.init_model(force_train=False)

    assert stego_ai._clf is not None
    assert hasattr(stego_ai._clf, "predict_proba")
    assert stale_model.exists()
    assert stale_meta.exists()
