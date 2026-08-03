# pqcsecure-backend

This directory contains the Flask backend for the PQCSecure demo application.

## What it provides
- Key generation for ML-KEM-768, RSA-2048, and X25519
- AES-256-GCM authenticated encryption and decryption
- LSB image steganography embedding and extraction with lossless image enforcement
- Benchmarks and steganalysis metrics

## Setup
```bash
cd pqcsecure-backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Run locally
```bash
python app.py
```

The API will be available on port 5001 by default.

## Main endpoints
- POST /api/keygen
- POST /api/encrypt-embed
- POST /api/extract-decrypt
- GET /api/sample-cover
- GET /api/benchmark

## Configuration
Copy [.env.example](.env.example) to .env and set values such as:
- SECRET_KEY
- API_KEY
- REQUIRE_HTTPS
- EXPOSE_PRIVATE_KEY
- SESSION_TTL_SECONDS
- STEGO_DATASET_DIR  # optional local path to a cover/stego dataset directory for model training

## Testing
```bash
.venv\Scripts\python -m pytest -q
```

