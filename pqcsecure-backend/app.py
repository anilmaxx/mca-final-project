"""
app.py — Post-Quantum Secure Data Transmission System
Flask REST API

Phases implemented here:
  1  Key Generation      → /api/keygen
  2  Key Encapsulation   ┐
  3  AES-256 Encryption  │
  4  Payload Build       ├→ /api/encrypt-embed
  5  LSB Embed           │
  6  (return stego img)  ┘
  7  Extract + Decrypt   → /api/extract-decrypt
"""

import io
import os
import struct
import base64
import logging
import time
from pathlib import Path
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
from Crypto.Random import get_random_bytes
import numpy as np

import crypto
import steganography
import benchmark
import stego_ai


def _load_env_file() -> None:
    """Load variables from a local .env file if present."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _parse_origins(raw_value: str) -> list[str]:
    if not raw_value or raw_value.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _validate_bit_depth(bit_depth: int) -> tuple[bool, str | None]:
    if bit_depth not in (1, 2, 3):
        return False, "bit_depth must be 1, 2, or 3."
    return True, None


def _validate_symmetric_mode(symmetric_mode: str) -> tuple[bool, str | None]:
    if symmetric_mode not in {"AES-256-GCM"}:
        return False, "symmetric_mode must be AES-256-GCM."
    return True, None


ALLOWED_LOSSLESS_EXTENSIONS = {".png", ".bmp", ".tif", ".tiff"}
LOSSLESS_IMAGE_FORMATS = {"PNG", "BMP", "TIFF"}


def _file_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _validate_lossless_image_file(image_file) -> tuple[bool, str | None]:
    filename = image_file.filename or ""
    extension = _file_extension(filename)
    if extension not in ALLOWED_LOSSLESS_EXTENSIONS:
        return False, (
            "Unsupported image format. Upload a lossless file type such as PNG, BMP, or TIFF. "
            "JPEG is not supported for steganographic embedding/extraction."
        )

    try:
        image_file.stream.seek(0)
        img = Image.open(image_file.stream)
        img_format = img.format
    except Exception:
        return False, "Invalid image file."
    finally:
        try:
            image_file.stream.seek(0)
        except Exception:
            pass

    if img_format not in LOSSLESS_IMAGE_FORMATS:
        return False, (
            "Unsupported image format. Upload a lossless file type such as PNG, BMP, or TIFF. "
            "JPEG is not supported for steganographic embedding/extraction."
        )

    return True, None

# ─── App Setup ────────────────────────────────────────────────────────────────
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pqcsecure-frontend', 'dist'))
app = Flask(__name__, static_folder=frontend_dist, static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production")
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
app.config["PROPAGATE_EXCEPTIONS"] = True

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
allowed_origins = _parse_origins(os.getenv("CORS_ORIGINS", ",".join(default_origins)))
CORS(
    app,
    resources={r"/api/*": {"origins": allowed_origins, "supports_credentials": False}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_):
    return jsonify({"error": "Upload too large."}), 413

@app.errorhandler(400)
def bad_request(_):
    return jsonify({"error": "Bad request."}), 400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize local AI Stego models
stego_ai.init_model()

# ─── In-memory key store ──────────────────────────────────────────────────────
_key_store: dict = {}


def _cleanup_expired_sessions() -> None:
    """Remove expired sessions from the in-memory store."""
    ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
    now = time.time()
    expired_ids = [
        session_id
        for session_id, data in list(_key_store.items())
        if now - data.get("created_at", now) > ttl_seconds
    ]
    for session_id in expired_ids:
        del _key_store[session_id]


def _get_session(session_id: str) -> dict | None:
    """Fetch a session by ID, cleaning up expired entries first."""
    _cleanup_expired_sessions()
    session = _key_store.get(session_id)
    if not session:
        return None
    return session


@app.before_request
def enforce_security() -> None:
    """Enforce optional API key and HTTPS protections for protected routes."""
    if request.endpoint in {"index", "health"}:
        return

    if _env_flag("REQUIRE_HTTPS", "false"):
        is_localhost = request.host.startswith(("localhost", "127.0.0.1"))
        if not request.is_secure and not is_localhost:
            response = jsonify({"error": "HTTPS required"})
            response.status_code = 403
            return response

    api_key = os.getenv("API_KEY", "").strip()
    if api_key:
        supplied_key = (
            request.headers.get("X-API-Key", "").strip()
            or request.args.get("api_key", "").strip()
        )
        if supplied_key != api_key:
            response = jsonify({"error": "Unauthorized"})
            response.status_code = 401
            return response


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Key Generation
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/keygen", methods=["POST"])
def keygen():
    """Generate KEM keypair and return session metadata."""
    try:
        # Get requested algorithm
        algorithm = "ML-KEM-768"
        if request.is_json and request.json:
            algorithm = request.json.get("algorithm", "ML-KEM-768").strip()
        elif request.form:
            algorithm = request.form.get("algorithm", "ML-KEM-768").strip()

        t0 = time.perf_counter()
        ek, dk = crypto.generate_keypair(algorithm)
        keygen_time_ms = (time.perf_counter() - t0) * 1000

        session_id = base64.urlsafe_b64encode(get_random_bytes(32)).decode()
        _key_store[session_id] = {
            "ek": ek,
            "dk": dk,
            "algorithm": algorithm,
            "created_at": time.time(),
        }

        logger.info("Keygen OK — session=%s  algo=%s  ek=%d B  dk=%d B",
                    session_id[:8] + "…", algorithm, len(ek), len(dk))

        # Security level text
        if algorithm == "ML-KEM-768":
            security_level = "NIST Level 3 — 192-bit classical / quantum-safe"
            algo_display = "ML-KEM-768 (FIPS 203)"
        elif algorithm == "RSA-2048":
            security_level = "NIST Level 1 Equivalent — 112-bit security / classical"
            algo_display = "RSA-2048 (Classical Baseline)"
        elif algorithm == "X25519":
            security_level = "NIST Level 1 Equivalent — 128-bit security / classical"
            algo_display = "X25519 (ECDH Baseline)"
        else:
            security_level = "Unknown"
            algo_display = algorithm

        return jsonify({
            "session_id":         session_id,
            "public_key_b64":     base64.b64encode(ek).decode(),
            "public_key_length":  len(ek),
            "private_key_length": len(dk),
            "algorithm":          algo_display,
            "security_level":     security_level,
            "keygen_time_ms":     round(keygen_time_ms, 3),
        })

    except Exception as exc:
        logger.exception("Keygen failed")
        return jsonify({"error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# PHASES 2-6 — Encrypt + Embed
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/encrypt-embed", methods=["POST"])
def encrypt_embed():
    """Encapsulate shared secret, encrypt message, embed payload into image."""
    try:
        session_id     = request.form.get("session_id", "").strip()
        message        = request.form.get("message", "")
        image_file     = request.files.get("image")
        kem_algo       = request.form.get("kem_algo", "ML-KEM-768").strip()
        symmetric_mode = request.form.get("symmetric_mode", "AES-256-GCM").strip()
        bit_depth      = int(request.form.get("bit_depth", 1))

        is_valid_bit_depth, bit_depth_error = _validate_bit_depth(bit_depth)
        if not is_valid_bit_depth:
            return jsonify({"error": bit_depth_error}), 400

        is_valid_mode, mode_error = _validate_symmetric_mode(symmetric_mode)
        if not is_valid_mode:
            return jsonify({"error": mode_error}), 400

        session_data = _get_session(session_id)
        if session_data is None:
            return jsonify({"error": "Invalid session_id — generate keys first."}), 400
        if not message:
            return jsonify({"error": "Message is empty."}), 400
        if image_file is None:
            return jsonify({"error": "No image file provided."}), 400

        is_image_valid, image_error = _validate_lossless_image_file(image_file)
        if not is_image_valid:
            return jsonify({"error": image_error}), 400

        stored_algo = session_data["algorithm"]
        if stored_algo != kem_algo:
            return jsonify({
                "error": f"Algorithm Mismatch: Session keys were generated for {stored_algo} but you requested {kem_algo}. Please re-generate keys for {kem_algo}."
            }), 400

        ek = session_data["ek"]

        # Phase 2: Key Encapsulation
        t0 = time.perf_counter()
        shared_secret, kem_ct = crypto.encapsulate(ek, kem_algo)
        encaps_time_ms = (time.perf_counter() - t0) * 1000

        # Phase 3: Symmetric Encryption
        t1 = time.perf_counter()
        iv, auth_tag, ciphertext = crypto.aes_encrypt(shared_secret, message.encode("utf-8"), symmetric_mode)
        aes_enc_time_ms = (time.perf_counter() - t1) * 1000

        # Phase 4: Payload Construction
        payload = crypto.build_payload(kem_ct, iv, auth_tag, ciphertext)

        # Phase 5: LSB Embedding
        cover_img = Image.open(image_file)
        max_bytes = steganography.max_payload_bytes(cover_img, bit_depth)

        if len(payload) > max_bytes:
            return jsonify({
                "error": (
                    f"Image too small. Payload needs {len(payload)} B "
                    f"but image holds {max_bytes} B at bit depth {bit_depth}. Use a larger image or increase depth."
                )
            }), 400

        stego_img = steganography.embed(cover_img, payload, bit_depth)
        mse, psnr, ssim = steganography.calculate_image_metrics(cover_img, stego_img)

        # Calculate Chi-Square steganalysis detector probabilities
        cover_chi_prob = steganography.calculate_chi_square_detector(cover_img)
        stego_chi_prob = steganography.calculate_chi_square_detector(stego_img)

        # Grayscale histograms
        cover_hist = steganography.get_grayscale_histogram(cover_img)
        stego_hist = steganography.get_grayscale_histogram(stego_img)

        # Generate Difference Map (100x absolute differences)
        cover_arr = np.array(cover_img.convert("RGB"), dtype=np.int16)
        stego_arr = np.array(stego_img.convert("RGB"), dtype=np.int16)
        diff = np.abs(cover_arr - stego_arr)
        diff_map = np.clip(diff * 100, 0, 255).astype(np.uint8)
        diff_img = Image.fromarray(diff_map, mode="RGB")

        # Serialise stego image (PNG = lossless)
        buf = io.BytesIO()
        stego_img.save(buf, format="PNG")
        stego_b64 = base64.b64encode(buf.getvalue()).decode()

        # Serialise difference map
        buf_diff = io.BytesIO()
        diff_img.save(buf_diff, format="PNG")
        diff_b64 = base64.b64encode(buf_diff.getvalue()).decode()

        return jsonify({
            "stego_image_b64":     stego_b64,
            "diff_image_b64":      diff_b64,
            "kem_ct_length":       len(kem_ct),
            "payload_bytes":       len(payload),
            "image_capacity_bits": max_bytes * 8,
            "aes_mode":            symmetric_mode,
            "iv_b64":              base64.b64encode(iv).decode(),
            "auth_tag_b64":        base64.b64encode(auth_tag).decode() if auth_tag else "",
            "encaps_time_ms":      round(encaps_time_ms, 3),
            "aes_enc_time_ms":     round(aes_enc_time_ms, 3),
            "psnr":                round(psnr, 2),
            "ssim":                round(ssim, 2),
            "mse":                 round(mse, 6),
            "cover_chi_prob":      round(cover_chi_prob, 4),
            "stego_chi_prob":      round(stego_chi_prob, 4),
            "cover_hist":          cover_hist,
            "stego_hist":          stego_hist,
        })

    except Exception as exc:
        logger.exception("Encrypt-embed failed")
        return jsonify({"error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — Extract + Decrypt
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/extract-decrypt", methods=["POST"])
def extract_decrypt():
    """Extract hidden payload from stego-image and decrypt the message."""
    try:
        session_id     = request.form.get("session_id", "").strip()
        stego_file     = request.files.get("stego_image")
        kem_algo       = request.form.get("kem_algo", "ML-KEM-768").strip()
        symmetric_mode = request.form.get("symmetric_mode", "AES-256-GCM").strip()
        bit_depth      = int(request.form.get("bit_depth", 1))
        tamper_mode    = request.form.get("tamper_mode", "none").strip()

        is_valid_bit_depth, bit_depth_error = _validate_bit_depth(bit_depth)
        if not is_valid_bit_depth:
            return jsonify({"error": bit_depth_error}), 400

        is_valid_mode, mode_error = _validate_symmetric_mode(symmetric_mode)
        if not is_valid_mode:
            return jsonify({"error": mode_error}), 400

        session_data = _get_session(session_id)
        if session_data is None:
            return jsonify({"error": "Invalid session_id."}), 400
        if stego_file is None:
            return jsonify({"error": "No stego image provided."}), 400

        is_image_valid, image_error = _validate_lossless_image_file(stego_file)
        if not is_image_valid:
            return jsonify({"error": image_error}), 400

        stored_algo = session_data["algorithm"]
        if stored_algo != kem_algo:
            return jsonify({
                "error": f"Algorithm Mismatch: Keys generated for {stored_algo} but request uses {kem_algo}."
            }), 400

        dk = session_data["dk"]

        # LSB Extraction
        stego_img = Image.open(stego_file)

        # Calculate Chi-Square steganalysis detector probabilities
        stego_chi_prob = steganography.calculate_chi_square_detector(stego_img)

        # Handle tamper mode: flip stego pixel
        if tamper_mode == "flip_pixel":
            stego_arr = np.array(stego_img.convert("RGB"))
            flat = stego_arr.flatten()
            if len(flat) > 500:
                flat[500] ^= 1
            else:
                flat[-1] ^= 1
            stego_img = Image.fromarray(flat.reshape(stego_arr.shape), mode="RGB")

        # Read header first
        t_start_extract = time.perf_counter()
        try:
            header_bytes = steganography.extract(stego_img, crypto.header_size(), bit_depth)
            if len(header_bytes) != crypto.header_size():
                raise ValueError("Incomplete payload header.")

            kem_ct_len, enc_msg_len, iv_len, tag_len = struct.unpack(">IIBB", header_bytes)
            total_payload = crypto.header_size() + kem_ct_len + iv_len + tag_len + enc_msg_len
            max_bytes = steganography.max_payload_bytes(stego_img, bit_depth)

            if total_payload <= 0 or total_payload > max_bytes:
                raise ValueError(
                    f"Invalid payload header. Expected payload size {total_payload} bytes, "
                    f"but image capacity is {max_bytes} bytes."
                )
            if iv_len != 12 or tag_len != 16:
                raise ValueError("Unsupported payload format or corrupted header.")

            payload = steganography.extract(stego_img, total_payload, bit_depth)
        except (ValueError, struct.error) as err:
            logger.warning("LSB extraction failed: %s", err)
            return jsonify({
                "error": "Extraction failed: Invalid or corrupt steganography payload/header."
            }), 400
            
        extract_time_ms = (time.perf_counter() - t_start_extract) * 1000

        # Parse payload components
        kem_ct, iv, auth_tag, ciphertext = crypto.parse_payload(payload)

        # Handle tamper mode: alter ciphertext
        if tamper_mode == "alter_ciphertext" and len(ciphertext) > 0:
            ct_list = bytearray(ciphertext)
            ct_list[0] ^= 1
            ciphertext = bytes(ct_list)

        # KEM Decapsulation
        t0 = time.perf_counter()
        try:
            shared_secret = crypto.decapsulate(dk, kem_ct, kem_algo)
            decaps_time_ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:
            decaps_time_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Decapsulation FAILED: %s", exc)
            if symmetric_mode == "AES-256-GCM":
                return jsonify({
                    "error":              "TAMPER DETECTED: DECRYPTION REJECTED",
                    "integrity_verified": False,
                    "detail":             "KEM decapsulation failed due to ciphertext alteration.",
                    "extraction_time_ms": round(extract_time_ms, 3),
                    "decaps_time_ms":     round(decaps_time_ms, 3),
                    "aes_dec_time_ms":    0.0,
                    "stego_chi_prob":     round(stego_chi_prob, 4),
                }), 400
            else:
                return jsonify({
                    "error":              f"Decapsulation Error: {str(exc)}",
                    "integrity_verified": False,
                    "detail":             str(exc),
                    "extraction_time_ms": round(extract_time_ms, 3),
                    "decaps_time_ms":     round(decaps_time_ms, 3),
                    "aes_dec_time_ms":    0.0,
                    "stego_chi_prob":     round(stego_chi_prob, 4),
                }), 400

        # Symmetric Decryption
        t1 = time.perf_counter()
        try:
            plaintext = crypto.aes_decrypt(shared_secret, iv, auth_tag, ciphertext, symmetric_mode)
            aes_dec_time_ms = (time.perf_counter() - t1) * 1000

            return jsonify({
                "message":            plaintext.decode("utf-8", errors="replace"),
                "integrity_verified": True if symmetric_mode == "AES-256-GCM" else False,
                "extraction_success": True,
                "algorithm":          f"{kem_algo} + {symmetric_mode} + Adaptive LSB (Depth {bit_depth})",
                "extraction_time_ms": round(extract_time_ms, 3),
                "decaps_time_ms":     round(decaps_time_ms, 3),
                "aes_dec_time_ms":    round(aes_dec_time_ms, 3),
                "stego_chi_prob":     round(stego_chi_prob, 4),
            })
        except Exception as exc:
            aes_dec_time_ms = (time.perf_counter() - t1) * 1000
            logger.warning("Decryption FAILED: %s", exc)
            
            if symmetric_mode == "AES-256-GCM":
                error_msg = "TAMPER DETECTED: DECRYPTION REJECTED"
            else:
                error_msg = f"Decryption failed: {str(exc)}"

            return jsonify({
                "error":              error_msg,
                "integrity_verified": False,
                "detail":             str(exc),
                "extraction_time_ms": round(extract_time_ms, 3),
                "decaps_time_ms":     round(decaps_time_ms, 3),
                "aes_dec_time_ms":    round(aes_dec_time_ms, 3),
                "stego_chi_prob":     round(stego_chi_prob, 4),
            }), 400

    except Exception as exc:
        logger.exception("Extract-decrypt failed")
        return jsonify({"error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# SAMPLE COVER GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/sample-cover", methods=["GET"])
def sample_cover():
    """Generates Natural, Texture, or Synthetic sample cover images on the fly."""
    try:
        style = request.args.get("style", "Synthetic").strip()
        res = 512
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        
        if style == "Synthetic":
            img_arr[:, :] = [15, 23, 42]
            img_arr[res//4:3*res//4, res//4:3*res//4] = [59, 130, 246]
        elif style == "Texture":
            x = np.linspace(0, 10 * np.pi, res)
            y = np.linspace(0, 10 * np.pi, res)
            xx, yy = np.meshgrid(x, y)
            pattern = (np.sin(xx) * np.cos(yy) + 1) * 127.5
            img_arr[:, :, 0] = pattern.astype(np.uint8)
            img_arr[:, :, 1] = (pattern * 0.7).astype(np.uint8)
            img_arr[:, :, 2] = (255 - pattern * 0.5).astype(np.uint8)
        else:  # Natural
            for y in range(res):
                img_arr[y, :, 0] = int(255 * (y / res))
                img_arr[y, :, 1] = int(255 * (1 - y / res))
                img_arr[y, :, 2] = int(128 * (y / res))
                
        img = Image.fromarray(img_arr, mode="RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        return send_file(buf, mimetype="image/png")
    except Exception as exc:
        logger.exception("Failed to generate sample cover image")
        return jsonify({"error": str(exc)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# AI OPTIMIZER AND STEGO DETECTOR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/ai-optimize", methods=["POST"])
def ai_optimize():
    """Analyze cover image texture and suggest parameters and high-frequency regions."""
    try:
        image_file = request.files.get("image")
        if not image_file:
            return jsonify({"error": "No image file provided."}), 400

        message = request.form.get("message", "") or ""
        kem_algo = request.form.get("kem_algo", "ML-KEM-768").strip()

        cover_img = Image.open(image_file)
        analysis = stego_ai.analyze_cover_image(cover_img, message=message, kem_algo=kem_algo)
        return jsonify(analysis)
    except Exception as exc:
        logger.exception("AI Optimize failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/ai-detect", methods=["POST"])
def ai_detect():
    """Predict the probability of a hidden stego payload in an uploaded image."""
    try:
        image_file = request.files.get("image")
    except RequestEntityTooLarge:
        return jsonify({"error": "Upload too large."}), 413

    try:
        if not image_file:
            return jsonify({"error": "No image file provided."}), 400

        filename = secure_filename(image_file.filename or "")
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")):
            return jsonify({"error": "Unsupported image type. Use PNG, JPG, JPEG, BMP, TIFF."}), 400

        img = Image.open(image_file)
        img = img.convert("RGB")
        prob = stego_ai.predict_stego(img)
        features = stego_ai.extract_stego_features(img)

        feature_dict = {
            name: round(value, 5)
            for name, value in zip(stego_ai.FEATURE_NAMES, features)
        }
        metrics = stego_ai.get_detection_metrics()
        explanation = stego_ai.build_detection_explanation(features, prob)

        return jsonify({
            "stego_probability": round(prob, 4),
            "is_stego": bool(prob > 0.5),
            "confidence": "high" if prob >= 0.75 else "medium" if prob >= 0.5 else "low",
            "features": feature_dict,
            "metrics": metrics,
            "explanation": explanation,
            "filename": filename,
        })
    except Exception as exc:
        logger.exception("AI Detect failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/ai-compare", methods=["POST"])
def ai_compare():
    """Compare a cover image and a stego image using the local AI detector."""
    try:
        cover_file = request.files.get("cover_image")
        stego_file = request.files.get("stego_image")
    except RequestEntityTooLarge:
        return jsonify({"error": "Upload too large."}), 413

    try:
        if not cover_file or not stego_file:
            return jsonify({"error": "Both cover_image and stego_image are required."}), 400

        cover_img = Image.open(cover_file).convert("RGB")
        stego_img = Image.open(stego_file).convert("RGB")

        cover_prob = stego_ai.predict_stego(cover_img)
        stego_prob = stego_ai.predict_stego(stego_img)

        cover_features = stego_ai.extract_stego_features(cover_img)
        stego_features = stego_ai.extract_stego_features(stego_img)

        # Convert features to JSON-serializable rounded maps
        cover_feature_map = {
            name: round(float(value), 5)
            for name, value in zip(stego_ai.FEATURE_NAMES, cover_features)
        }
        stego_feature_map = {
            name: round(float(value), 5)
            for name, value in zip(stego_ai.FEATURE_NAMES, stego_features)
        }

        difference = round(max(0.0, stego_prob - cover_prob), 4)

        return jsonify({
            "cover": {
                "stego_probability": round(cover_prob, 4),
                "is_stego": bool(cover_prob > 0.5),
                "features": cover_feature_map,
            },
            "stego": {
                "stego_probability": round(stego_prob, 4),
                "is_stego": bool(stego_prob > 0.5),
                "features": stego_feature_map,
            },
            "comparison": {
                "difference": difference,
                "verdict": "stego-like" if difference > 0.1 else "similar",
            },
        })
    except Exception as exc:
        logger.exception("AI Compare failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/ai-train", methods=["POST"])
def ai_train():
    """Train or retrain the local AI detector model and return the resulting parameters."""
    try:
        force = request.form.get("force", "false").strip().lower() in {"1", "true", "yes", "on"}
        stego_ai.init_model(force_train=force)
        X, y = stego_ai.build_realistic_dataset()
        best_params = stego_ai.optimize_model_parameters(X, y)
        metrics = stego_ai.get_detection_metrics()
        return jsonify({
            "status": "trained",
            "force_retrained": force,
            "best_params": best_params,
            "model_path": stego_ai.MODEL_PATH,
            "evaluation_metrics": metrics,
            "dataset_size": len(X),
            "positive_samples": int(sum(1 for label in y if label == 1)),
            "negative_samples": int(sum(1 for label in y if label == 0)),
        })
    except Exception as exc:
        logger.exception("AI Train failed")
        return jsonify({"error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/", methods=["GET"])
def index():
    return app.send_static_file('index.html')

@app.errorhandler(404)
def not_found(e):
    return app.send_static_file('index.html')

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":     "ok",
        "algorithms": ["ML-KEM-768 (FIPS 203)", "RSA-2048", "X25519", "AES-256-GCM", "LSB Steganography"],
        "endpoints":  ["/api/keygen", "/api/encrypt-embed", "/api/extract-decrypt", "/api/sample-cover", "/api/benchmark", "/api/ai-optimize", "/api/ai-detect"],
    })

@app.route("/api/benchmark", methods=["GET"])
def run_benchmark():
    """Runs live on-hardware simulation benchmarks."""
    try:
        iterations = request.args.get("iterations", 100, type=int)
        
        t_start = time.perf_counter()
        kem_results = benchmark.run_kem_benchmark(iterations=iterations)
        sym_results = benchmark.run_symmetric_benchmark()
        stego_results = benchmark.run_stego_benchmark()
        isolated_stego = benchmark.run_isolated_stego_benchmark(res=512, payload_size=1024)
        e2e_results = benchmark.run_end_to_end_benchmark()
        total_time = time.perf_counter() - t_start
        
        return jsonify({
            "success": True,
            "benchmark_time_seconds": round(total_time, 2),
            "kem": kem_results,
            "symmetric": sym_results,
            "stego": stego_results,
            "isolated_stego": isolated_stego,
            "e2e": e2e_results
        })
    except Exception as exc:
        logger.exception("Benchmark suite execution failed")
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
