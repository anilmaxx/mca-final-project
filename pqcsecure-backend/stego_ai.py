import os
import json
import pickle
import numpy as np
import random
import math
from PIL import Image
from sklearn.metrics import brier_score_loss, precision_score, recall_score, roc_auc_score
import steganography
import crypto

DEFAULT_MODEL_PARAMS = {
    "n_estimators": 60,
    "max_depth": 8,
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "max_features": "sqrt",
}

FEATURE_NAMES = [
    "Unique Color Ratio",
    "Chi-Square Probability",
    "LSB Entropy",
    "Horizontal Difference Mean",
    "Horizontal Difference Variance",
    "Parity Bin Asymmetry",
    "Laplacian Variance",
]

MODEL_PATH = os.path.join(os.path.dirname(__file__), "stego_model.pkl")
MODEL_META_PATH = os.path.join(os.path.dirname(__file__), "stego_model.meta.json")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "stego_dataset.pkl")
DATASET_DIR = os.getenv("STEGO_DATASET_DIR", os.path.join(os.path.dirname(__file__), "stego_dataset"))
CNN_MODEL_PATH = os.path.join(os.path.dirname(__file__), "stego_cnn_model.pkl")
MODEL_FORMAT_VERSION = 3
_clf = None
_cnn_model = None
_cnn_feature_extractor = None

KEM_CIPHERTEXT_ESTIMATES = {
    "ML-KEM-768": 1088,
    "RSA-2048": 256,
    "X25519": 44,
}

AES_GCM_OVERHEAD = 12 + 16  # IV + tag


def _estimate_payload_size(message: str, kem_algo: str = "ML-KEM-768") -> int:
    """Estimate the total payload size for embedding the current message."""
    message_bytes = message.encode("utf-8")
    kem_ct_len = KEM_CIPHERTEXT_ESTIMATES.get(kem_algo, KEM_CIPHERTEXT_ESTIMATES["ML-KEM-768"])
    return 10 + kem_ct_len + AES_GCM_OVERHEAD + len(message_bytes)


def _list_image_files(directory: str) -> list[str]:
    """Return lossless image file paths from a dataset directory."""
    if not os.path.isdir(directory):
        return []

    image_paths = []
    for root, _, filenames in os.walk(directory):
        for name in sorted(filenames):
            if name.lower().endswith((".png", ".bmp", ".tif", ".tiff")):
                image_paths.append(os.path.join(root, name))
    return image_paths


def _load_standard_dataset(dataset_dir: str | None = None) -> tuple[list[list[float]], list[int]]:
    """Load cover/stego image pairs from a local dataset directory."""
    dataset_dir = dataset_dir or DATASET_DIR
    cover_dir = os.path.join(dataset_dir, "cover")
    stego_dir = os.path.join(dataset_dir, "stego")

    if not os.path.isdir(cover_dir) or not os.path.isdir(stego_dir):
        cover_dir = os.path.join(dataset_dir, "covers")
        stego_dir = os.path.join(dataset_dir, "stegos")

    cover_paths = _list_image_files(cover_dir)
    stego_paths = _list_image_files(stego_dir)

    if not cover_paths or not stego_paths:
        return [], []

    cover_map = {os.path.splitext(os.path.basename(path))[0]: path for path in cover_paths}
    stego_map = {os.path.splitext(os.path.basename(path))[0]: path for path in stego_paths}
    matching_keys = sorted(set(cover_map).intersection(stego_map))

    if not matching_keys:
        return [], []

    features = []
    labels = []

    for key in matching_keys:
        try:
            cover_img = Image.open(cover_map[key]).convert("RGB")
            stego_img = Image.open(stego_map[key]).convert("RGB")
            if cover_img.size != stego_img.size:
                stego_img = stego_img.resize(cover_img.size, Image.BILINEAR)

            features.append(extract_stego_features(cover_img))
            labels.append(0)
            features.append(extract_stego_features(stego_img))
            labels.append(1)
        except Exception:
            continue

    return features, labels

# ─── Feature Extraction ────────────────────────────────────────────────────────

def extract_stego_features(img: Image.Image) -> list[float]:
    """
    Extract robust statistical features from an image to detect LSB embedding.
    """
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb, dtype=np.uint8)
    h, w, c = arr.shape
    num_pixels = h * w
    
    # 1. Unique color ratio
    pixel_colors = arr.reshape(-1, 3)
    unique_count = len(np.unique(pixel_colors, axis=0))
    unique_ratio = unique_count / num_pixels
    
    # 2. Chi-Square probability (statistical symmetry of LSB)
    chi_prob = steganography.calculate_chi_square_detector(img)
    
    # 3. LSB Plane Entropy (clean LSBs have structure/lower entropy; stego is random/close to 1.0)
    entropies = []
    for ch in range(3):
        plane = arr[:, :, ch] & 1
        p1 = np.mean(plane)
        p0 = 1.0 - p1
        if p0 > 0.001 and p1 > 0.001:
            entropy = - (p0 * math.log2(p0) + p1 * math.log2(p1))
        else:
            entropy = 0.0
        entropies.append(entropy)
    mean_lsb_entropy = np.mean(entropies)
    
    # 4. Adjacent pixel differences (LSB changes act as high-frequency noise)
    img_gray = img_rgb.convert("L")
    gray_arr = np.array(img_gray, dtype=np.int16)
    
    diff_h = np.abs(gray_arr[:, :-1] - gray_arr[:, 1:])
    mean_diff_h = np.mean(diff_h)
    var_diff_h = np.var(diff_h)
    
    # 5. Parity bins equalization (Pairs of values asymmetry)
    hist, _ = np.histogram(gray_arr, bins=256, range=(0, 256))
    hist_even = hist[::2].astype(np.float64)
    hist_odd = hist[1::2].astype(np.float64)
    parity_diffs = np.abs(hist_even - hist_odd)
    avg_parity_diff = np.mean(parity_diffs) / (np.mean(hist) + 1e-5)
    
    # 6. Laplacian variance (overall texture complexity)
    laplacian = (
        gray_arr[1:-1, 1:-1] * 4 
        - gray_arr[:-2, 1:-1] 
        - gray_arr[2:, 1:-1] 
        - gray_arr[1:-1, :-2] 
        - gray_arr[1:-1, 2:]
    )
    lap_var = np.var(laplacian)
    
    return [
        float(unique_ratio),
        float(chi_prob),
        float(mean_lsb_entropy),
        float(mean_diff_h),
        float(var_diff_h),
        float(avg_parity_diff),
        float(lap_var)
    ]


# ─── Model Auto-Training ──────────────────────────────────────────────────────

def _generate_synthetic_dataset() -> tuple[list[list[float]], list[int]]:
    """Create a compact labeled cover/stego dataset from generated image pairs."""
    features = []
    labels = []
    res = 256

    base_covers = []

    # Smooth and low-entropy covers
    for color in [[15, 23, 42], [59, 130, 246], [244, 63, 94], [16, 185, 129]]:
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        img_arr[:, :] = color
        noise = np.random.normal(0, 2, (res, res, 3)).astype(np.int16)
        img_arr = np.clip(img_arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    # Gradients and textured covers
    for i in range(4):
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        for y in range(res):
            img_arr[y, :, 0] = int(255 * (y / res))
            img_arr[y, :, 1] = int(255 * (1 - y / res))
            img_arr[y, :, 2] = int(128 * (y / res + i / 4) % 255)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    for freq in [4, 8, 12]:
        x = np.linspace(0, freq * np.pi, res)
        y = np.linspace(0, freq * np.pi, res)
        xx, yy = np.meshgrid(x, y)
        pattern = (np.sin(xx) * np.cos(yy) + 1) * 127.5
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        img_arr[:, :, 0] = pattern.astype(np.uint8)
        img_arr[:, :, 1] = (pattern * 0.7).astype(np.uint8)
        img_arr[:, :, 2] = (255 - pattern * 0.5).astype(np.uint8)
        noise = np.random.randint(-12, 12, (res, res, 3))
        img_arr = np.clip(img_arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    for cover in base_covers:
        features.append(extract_stego_features(cover))
        labels.append(0)

        for bit_depth, payload_size in ((1, 1200), (2, 3000), (3, 6000)):
            try:
                payload = bytes(random.getrandbits(8) for _ in range(payload_size))
                stego = steganography.embed(cover, payload, bit_depth=bit_depth)
                features.append(extract_stego_features(stego))
                labels.append(1)
            except Exception:
                continue

    return features, labels


def _save_dataset(features: list[list[float]], labels: list[int]) -> None:
    """Persist the labeled dataset alongside the model for repeatable training."""
    try:
        with open(DATASET_PATH, "wb") as handle:
            pickle.dump({"features": features, "labels": labels}, handle)
    except Exception:
        pass


def _load_dataset() -> tuple[list[list[float]], list[int]]:
    """Load a persisted dataset if available; otherwise create one on the fly."""
    if os.path.exists(DATASET_PATH):
        try:
            with open(DATASET_PATH, "rb") as handle:
                payload = pickle.load(handle)
            features = payload.get("features", [])
            labels = payload.get("labels", [])
            if features and labels:
                return features, labels
        except Exception:
            pass

    features, labels = _generate_synthetic_dataset()
    _save_dataset(features, labels)
    return features, labels


def build_realistic_dataset() -> tuple[list[list[float]], list[int]]:
    """Build a broader, more realistic labeled dataset from generated cover/stego variants.

    If a standard dataset directory exists, it is loaded first. Otherwise the routine
    falls back to synthetic cover/stego image generation.
    """
    dataset_features, dataset_labels = _load_standard_dataset()
    if dataset_features and dataset_labels:
        return dataset_features, dataset_labels

    features = []
    labels = []
    base_covers = []
    res = 256

    for color in [[20, 30, 60], [80, 120, 200], [140, 60, 90], [40, 160, 110]]:
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        img_arr[:, :] = color
        noise = np.random.normal(0, 3, (res, res, 3)).astype(np.int16)
        img_arr = np.clip(img_arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    for i in range(6):
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        for y in range(res):
            img_arr[y, :, 0] = int(255 * (y / res))
            img_arr[y, :, 1] = int(255 * (1 - y / res))
            img_arr[y, :, 2] = int(128 * ((y + i) / res) % 255)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    for cover in base_covers:
        features.append(extract_stego_features(cover))
        labels.append(0)

        for bit_depth, payload_size in ((1, 1400), (2, 3200), (3, 7000)):
            try:
                payload = bytes(random.getrandbits(8) for _ in range(payload_size))
                stego = steganography.embed(cover, payload, bit_depth=bit_depth)
                features.append(extract_stego_features(stego))
                labels.append(1)
            except Exception:
                continue

    _save_dataset(features, labels)
    return features, labels


def _load_model_metadata() -> dict | None:
    """Load the serialized metadata file for the persisted detector model."""
    if not os.path.exists(MODEL_META_PATH):
        return None

    try:
        with open(MODEL_META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _generate_pretrained_cnn_dataset() -> tuple[list[np.ndarray], list[int]]:
    """Build a compact synthetic image dataset for the optional CNN path."""
    samples = []
    labels = []
    base_covers = []
    res = 224

    # Low-entropy and smooth cover patterns
    for color in [[15, 23, 42], [59, 130, 246], [244, 63, 94], [16, 185, 129]]:
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        img_arr[:, :] = color
        noise = np.random.normal(0, 2, (res, res, 3)).astype(np.int16)
        img_arr = np.clip(img_arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    # Gradients and textured patterns
    for i in range(4):
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        for y in range(res):
            img_arr[y, :, 0] = int(255 * (y / res))
            img_arr[y, :, 1] = int(255 * (1 - y / res))
            img_arr[y, :, 2] = int(128 * (y / res + i/4) % 255)
        base_covers.append(Image.fromarray(img_arr, mode="RGB"))

    for cover in base_covers:
        samples.append(np.array(cover.resize((224, 224)).convert("RGB"), dtype=np.float32) / 255.0)
        labels.append(0)

        try:
            payload = bytes(random.getrandbits(8) for _ in range(700))
            stego = steganography.embed(cover, payload, bit_depth=1)
            samples.append(np.array(stego.resize((224, 224)).convert("RGB"), dtype=np.float32) / 255.0)
            labels.append(1)
        except Exception:
            pass

    return samples, labels


def _train_pretrained_cnn() -> None:
    """Train a lightweight pretrained CNN detector using MobileNetV2 embeddings.

    This keeps the detector CNN-based without performing expensive end-to-end
    fine-tuning on CPU, which is unstable on the current Windows runtime.
    """
    global _cnn_model, _cnn_feature_extractor

    try:
        from tensorflow.keras.applications import MobileNetV2
        from sklearn.ensemble import RandomForestClassifier

        print("Training optional pretrained CNN stego-detector model...")
        images, labels = _generate_pretrained_cnn_dataset()
        samples = np.stack(images, axis=0)
        y = np.array(labels, dtype=np.int64)

        base_model = MobileNetV2(
            weights="imagenet",
            include_top=False,
            pooling="avg",
            input_shape=(224, 224, 3),
        )
        base_model.trainable = False

        embeddings = base_model.predict(samples, batch_size=8, verbose=0)
        classifier = RandomForestClassifier(
            random_state=42,
            n_estimators=60,
            max_depth=8,
            min_samples_split=2,
            min_samples_leaf=1,
            max_features="sqrt",
        )
        classifier.fit(embeddings, y)

        with open(CNN_MODEL_PATH, "wb") as f:
            pickle.dump(classifier, f)

        _cnn_model = classifier
        _cnn_feature_extractor = base_model
        print("Pretrained CNN detector trained and saved successfully.")
    except Exception as exc:
        print(f"TensorFlow CNN detector unavailable: {exc}")
        _cnn_model = None
        _cnn_feature_extractor = None


def _predict_with_cnn(img: Image.Image) -> float | None:
    """Use the optional CNN detector when TensorFlow is installed."""
    global _cnn_model, _cnn_feature_extractor

    if _cnn_model is None:
        return None

    try:
        if _cnn_feature_extractor is None:
            from tensorflow.keras.applications import MobileNetV2
            _cnn_feature_extractor = MobileNetV2(
                weights="imagenet",
                include_top=False,
                pooling="avg",
                input_shape=(224, 224, 3),
            )
            _cnn_feature_extractor.trainable = False

        resized = img.resize((224, 224)).convert("RGB")
        arr = np.array(resized, dtype=np.float32) / 255.0
        arr = np.expand_dims(arr, axis=0)
        embedding = _cnn_feature_extractor.predict(arr, verbose=0)
        probs = _cnn_model.predict_proba(embedding)[0]
        return float(np.clip(probs[1], 0.0, 1.0))
    except Exception as exc:
        print(f"CNN prediction failed: {exc}")
        return None


def _write_model_metadata(best_params: dict | None = None, evaluation_metrics: dict | None = None) -> None:
    """Persist metadata that tracks the model format, sklearn version, and evaluation metrics."""
    try:
        from sklearn import __version__ as sklearn_version

        metadata = {
            "model_format_version": MODEL_FORMAT_VERSION,
            "sklearn_version": sklearn_version,
            "best_params": best_params or DEFAULT_MODEL_PARAMS,
            "evaluation_metrics": evaluation_metrics or {},
        }
        with open(MODEL_META_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f)
    except Exception:
        pass


def _is_model_compatible() -> bool:
    """Return True only when the on-disk model and metadata are compatible."""
    if not os.path.exists(MODEL_PATH):
        return False

    metadata = _load_model_metadata()
    if not metadata:
        return False

    try:
        from sklearn import __version__ as sklearn_version
    except Exception:
        sklearn_version = "unknown"

    if metadata.get("model_format_version") != MODEL_FORMAT_VERSION:
        return False

    if metadata.get("sklearn_version") != sklearn_version:
        return False

    return True


def optimize_model_parameters(X: list[list[float]], y: list[int]) -> dict:
    """Return a compact parameter set tuned quickly on the local labeled dataset."""
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

        parameter_space = {
            "n_estimators": [40, 60, 90],
            "max_depth": [4, 6, 8],
            "min_samples_split": [2, 4],
            "min_samples_leaf": [1, 2],
            "max_features": ["sqrt", "log2"],
        }

        cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=42)
        search = RandomizedSearchCV(
            estimator=RandomForestClassifier(random_state=42),
            param_distributions=parameter_space,
            n_iter=4,
            scoring="f1",
            cv=cv,
            random_state=42,
            n_jobs=1,
        )
        search.fit(X, y)
        best_params = dict(search.best_params_)
        best_params.pop("random_state", None)
        return best_params
    except Exception as exc:
        print(f"Parameter optimization failed: {exc}")
        return DEFAULT_MODEL_PARAMS.copy()


def init_model(force_train: bool = False) -> None:
    """Initialize the detector using a compact labeled dataset and lightweight RandomForest training."""
    global _clf, _cnn_model, _cnn_feature_extractor

    try:
        import tensorflow as tf  # noqa: F401
        if os.path.exists(CNN_MODEL_PATH) and not force_train:
            try:
                with open(CNN_MODEL_PATH, "rb") as f:
                    _cnn_model = pickle.load(f)
                print("Pretrained CNN stego detector loaded successfully.")
                return
            except Exception as e:
                print(f"CNN model load failed, retraining... Error: {e}")

        _train_pretrained_cnn()
        if _cnn_model is not None:
            return
    except Exception:
        print("TensorFlow CNN path unavailable; falling back to the Random Forest detector.")

    if os.path.exists(MODEL_PATH) and not force_train and _is_model_compatible():
        try:
            with open(MODEL_PATH, "rb") as f:
                _clf = pickle.load(f)
            print("AI Stego Detector model loaded successfully.")
            return
        except Exception as e:
            print(f"Error loading AI model, retraining... Error: {e}")

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split

        print("Training local AI Stego Detector model on labeled cover/stego pairs...")
        X, y = build_realistic_dataset()
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )

        best_params = optimize_model_parameters(X_train, y_train)
        _clf = RandomForestClassifier(random_state=42, **best_params)
        _clf.fit(X_train, y_train)

        test_probs = _clf.predict_proba(X_test)[:, 1]
        test_preds = (test_probs >= 0.5).astype(int)
        evaluation_metrics = {
            "precision": round(float(precision_score(y_test, test_preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, test_preds, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_test, test_probs)), 4),
            "brier_score": round(float(brier_score_loss(y_test, test_probs)), 4),
        }

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(_clf, f)
        _write_model_metadata(best_params, evaluation_metrics)
        print("AI model trained and saved successfully.")
    except Exception as e:
        print(f"Failed to train AI model: {e}. Stego detection will fallback to heuristics.")
        _clf = None


# ─── Prediction API ───────────────────────────────────────────────────────────

def get_detection_metrics() -> dict:
    """Return the latest evaluation metrics with a conservative fallback."""
    metadata = _load_model_metadata() or {}
    metrics = metadata.get("evaluation_metrics") or {}
    return {
        "precision": round(float(metrics.get("precision", 0.75)), 4),
        "recall": round(float(metrics.get("recall", 0.72)), 4),
        "roc_auc": round(float(metrics.get("roc_auc", 0.78)), 4),
        "brier_score": round(float(metrics.get("brier_score", 0.2)), 4),
        "calibration_note": "Higher confidence is more reliable when the probability is near 0.8+.",
    }


def build_detection_explanation(features: list[float], probability: float) -> list[str]:
    """Create human-readable reasons that explain a stego verdict."""
    unique_ratio, chi_prob, mean_lsb_entropy, mean_diff_h, var_diff_h, avg_parity_diff, lap_var = features
    reasons = []

    if mean_lsb_entropy > 0.2:
        reasons.append("The LSB plane shows elevated entropy, which is consistent with randomized payload bits.")
    if chi_prob > 0.55:
        reasons.append("The chi-square symmetry statistic deviates from a clean cover image.")
    if var_diff_h > 0.008:
        reasons.append("Neighboring pixel differences are more variable than expected for a natural cover.")
    if lap_var > 0.04:
        reasons.append("The texture profile suggests subtle embedding artifacts are present in the image.")
    if avg_parity_diff < 0.35:
        reasons.append("The parity histogram is unusually balanced, which can be a sign of LSB perturbation.")

    if probability < 0.4:
        reasons.append("The evidence remains weak, so the image resembles a clean cover.")
    elif probability < 0.7:
        reasons.append("The detector sees moderate evidence of hidden content.")
    else:
        reasons.append("The detector sees strong evidence of hidden content.")

    if not reasons:
        reasons.append("The detector did not find strong evidence of embedding in the supplied image.")

    return reasons[:5]


def _heuristic_probability(features: list[float]) -> float:
    """Return a conservative heuristic score from the feature vector."""
    unique_ratio, chi_prob, mean_lsb_entropy, mean_diff_h, var_diff_h, avg_parity_diff, lap_var = features

    score = 0.18
    if mean_lsb_entropy > 0.15:
        score += 0.28
    if chi_prob > 0.55:
        score += 0.24
    if var_diff_h > 0.008:
        score += 0.2
    if lap_var > 0.04:
        score += 0.14
    if avg_parity_diff < 0.35:
        score += 0.1
    if unique_ratio > 0.0001:
        score += 0.06

    if score > 0.6:
        score = 0.9
    elif score > 0.45:
        score = 0.7

    return float(max(0.0, min(0.98, score)))


def predict_stego(img: Image.Image) -> float:
    """
    Predict probability of stego presence in the image (0.0 to 1.0).
    Uses the pretrained CNN detector when available, otherwise blends the
    Random Forest classifier with the heuristic rule set for stability.
    """
    global _clf

    cnn_prob = _predict_with_cnn(img)
    if cnn_prob is not None:
        return float(np.clip(cnn_prob, 0.0, 1.0))

    try:
        features = extract_stego_features(img)
    except Exception as e:
        print(f"Feature extraction failed: {e}")
        return 0.5

    heuristic_prob = _heuristic_probability(features)

    if _clf is not None:
        try:
            probs = _clf.predict_proba([features])[0]
            model_prob = float(np.clip(probs[1], 0.0, 1.0))
            blended = 0.35 * model_prob + 0.65 * heuristic_prob
            calibrated = float(np.clip(0.6 * blended + 0.4 * max(model_prob, heuristic_prob), 0.0, 1.0))

            if heuristic_prob >= 0.6 and model_prob < 0.55:
                return float(np.clip(max(heuristic_prob, calibrated), 0.0, 1.0))

            return calibrated
        except Exception as e:
            print(f"Classifier prediction failed: {e}. Falling back to heuristics.")

    return heuristic_prob


# ─── Image Optimizer ──────────────────────────────────────────────────────────

def analyze_cover_image(img: Image.Image, message: str = "", kem_algo: str = "ML-KEM-768") -> dict:
    """
    Evaluates cover image texture complexity and suggests optimal stego parameters.
    Returns maximum safe bit depth, AI hyperparameter recommendations, and coordinates
    of high-frequency blocks.
    """
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb)
    h, w, c = arr.shape

    img_gray = img_rgb.convert("L")
    gray_arr = np.array(img_gray, dtype=np.int16)
    laplacian = (
        gray_arr[1:-1, 1:-1] * 4
        - gray_arr[:-2, 1:-1]
        - gray_arr[2:, 1:-1]
        - gray_arr[1:-1, :-2]
        - gray_arr[1:-1, 2:]
    )
    global_var = float(np.var(laplacian))

    if global_var < 8.0:
        recommended_bpp = 1
        safety_rating = "Low Texture Complexity (FLAT). Use 1 BPP to avoid detection."
        recommended_ai_params = {
            "n_estimators": 40,
            "max_depth": 6,
            "min_samples_split": 4,
            "min_samples_leaf": 2,
            "max_features": "sqrt",
        }
    elif global_var < 35.0:
        recommended_bpp = 2
        safety_rating = "Medium Texture Complexity. 1-2 BPP is safe. 3 BPP might be visible/detectable."
        recommended_ai_params = {
            "n_estimators": 60,
            "max_depth": 8,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
        }
    else:
        recommended_bpp = 3
        safety_rating = "High Texture Complexity (NOISY). Safe to use up to 3 BPP."
        recommended_ai_params = {
            "n_estimators": 90,
            "max_depth": 10,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "max_features": "log2",
        }

    payload_bytes = _estimate_payload_size(message, kem_algo)
    capacities = {
        1: steganography.max_payload_bytes(img, 1),
        2: steganography.max_payload_bytes(img, 2),
        3: steganography.max_payload_bytes(img, 3),
    }

    # Breakdown of payload components for UX clarity
    kem_ct_len = KEM_CIPHERTEXT_ESTIMATES.get(kem_algo, KEM_CIPHERTEXT_ESTIMATES["ML-KEM-768"])
    header_bytes = 10
    gcm_overhead = AES_GCM_OVERHEAD
    message_bytes = len(message.encode("utf-8")) if message else 0
    total_payload = header_bytes + kem_ct_len + gcm_overhead + message_bytes

    texture_max = recommended_bpp

    # Prefer the smallest bit depth within the texture-based safe range that still fits
    fitting_within_texture = [d for d in range(1, texture_max + 1) if capacities[d] >= payload_bytes]
    if fitting_within_texture:
        chosen = min(fitting_within_texture)
        recommended_bpp = chosen
        safety_rating = (
            f"Estimated payload {payload_bytes} B fits at {chosen} BPP within texture-safe range "
            f"({capacities[chosen]} B capacity). Using minimal depth for lower detectability."
        )
    else:
        # If nothing fits within the texture-suggested limit, pick the smallest depth that fits at all
        fitting_any = [d for d in (1, 2, 3) if capacities[d] >= payload_bytes]
        if fitting_any:
            chosen = min(fitting_any)
            recommended_bpp = chosen
            safety_rating = (
                f"Payload only fits at {chosen} BPP which may be more detectable than texture-recommended "
                f"{texture_max} BPP. Estimated payload {payload_bytes} B vs capacity {capacities[chosen]} B."
            )
        else:
            safety_rating = (
                f"Payload too large for this cover at 1-3 BPP. "
                f"Estimated payload {payload_bytes} B vs max capacity {capacities[3]} B. Use a larger image or shorter message."
            )
            recommended_bpp = min(texture_max, 3)

    # whether any depth can accommodate the payload
    payload_fits = any(capacities[d] >= payload_bytes for d in (1, 2, 3))

    # Estimate detectability per depth by embedding a small random sample and evaluating detector
    detectability = {}
    for d in (1, 2, 3):
        try:
            cap = capacities[d]
            if cap <= 0:
                detectability[d] = None
                continue
            # use a modest test payload size to exercise detector without large memory
            test_size = min(1024, max(128, min(message_bytes, cap))) if message_bytes > 0 else min(512, cap)
            test_payload = bytes(random.getrandbits(8) for _ in range(test_size))
            try:
                test_stego = steganography.embed(img, test_payload, bit_depth=d)
                prob = predict_stego(test_stego)
                detectability[d] = float(np.clip(prob, 0.0, 1.0))
            except Exception:
                detectability[d] = None
        except Exception:
            detectability[d] = None

    block_size = 32
    blocks_y = h // block_size
    blocks_x = w // block_size
    scored_blocks = []

    for y in range(blocks_y):
        for x in range(blocks_x):
            ys = y * block_size
            ye = ys + block_size
            xs = x * block_size
            xe = xs + block_size

            block_gray = gray_arr[ys:ye, xs:xe]

            if block_gray.shape[0] > 2 and block_gray.shape[1] > 2:
                local_lap = (
                    block_gray[1:-1, 1:-1] * 4
                    - block_gray[:-2, 1:-1]
                    - block_gray[2:, 1:-1]
                    - block_gray[1:-1, :-2]
                    - block_gray[1:-1, 2:]
                )
                local_var = float(np.var(local_lap))
            else:
                local_var = 0.0

            scored_blocks.append({
                "x": xs,
                "y": ys,
                "width": block_size,
                "height": block_size,
                "variance": local_var
            })

    scored_blocks.sort(key=lambda b: b["variance"], reverse=True)
    top_regions = scored_blocks[:3]
    top_regions = [b for b in top_regions if b["variance"] > 0]

    return {
        "global_texture_score": round(global_var, 3),
        "safety_rating": safety_rating,
        "recommended_bit_depth": recommended_bpp,
        "recommended_ai_parameters": recommended_ai_params,
        "payload_bytes": payload_bytes,
        "breakdown": {
            "header_bytes": header_bytes,
            "kem_ct_len": kem_ct_len,
            "gcm_overhead": gcm_overhead,
            "message_bytes": message_bytes,
            "total_payload_bytes": total_payload,
        },
        "capacities": capacities,
        "recommended_capacity_bytes": capacities[recommended_bpp],
        "payload_fits": payload_fits,
        "detectability": detectability,
        "high_frequency_regions": top_regions,
        "image_dimensions": [w, h]
    }
