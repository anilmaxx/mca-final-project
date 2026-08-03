# PQCSecure

PQCSecure is a secure data-transmission prototype that combines post-quantum key encapsulation, AES encryption, and adaptive image steganography. The repository demonstrates a full sender/receiver workflow where encrypted message payloads are hidden inside cover images and later extracted and verified using backend services and a React frontend.

---

## What this repository contains

This workspace is organized into three main parts:

- `pi_benchmark/` — benchmarking and performance-test scripts for hardware and cipher speed comparisons.
- `pqcsecure-backend/` — Flask API that provides key generation, encryption, steganographic embedding/extraction, ML model utilities, and benchmark runners.
- `pqcsecure-frontend/` — Vite + React user interface for interacting with the backend system.

---

## Core capabilities

- Quantum-safe key exchange using ML-KEM-768, with classical baselines such as X25519 and RSA-2048.
- Symmetric encryption using AES-256-GCM authenticated encryption.
- Adaptive steganography that embeds payloads into high-texture image regions.
- Local image-analysis and stego-detection utilities for receiver-side validation.
- Benchmarking and speed-test tooling for evaluating implementation behavior.

---

## Quick start

### 1. Backend setup

```bash
cd pqcsecure-backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a local environment file if your deployment needs one:

```bash
copy .env.example .env
```

Then adjust any required values for secret-key handling, session controls, and deployment settings.

### 3. Start the backend

```bash
python app.py
```

The backend serves the API on `http://localhost:5001` by default.

### 4. Frontend setup

```bash
cd ../pqcsecure-frontend
npm install
npm run dev
```

The frontend development server runs on `http://localhost:3000` by default.

---

## Useful verification commands

### Run backend tests

```bash
cd pqcsecure-backend
.venv\Scripts\python -m pytest -q
```

### Run a quick benchmark suite

```bash
cd pqcsecure-backend
.venv\Scripts\python run_benchmarks_quick.py
```

---

## System flow

The high-level flow is:

1. Bob generates a ML-KEM keypair and shares the public key.
2. Alice encapsulates a shared secret and encrypts the message payload.
3. Alice hides the encrypted payload in a cover image using adaptive LSB steganography.
4. The resulting stego image is transmitted over an untrusted channel.
5. Bob extracts the payload, decapsulates the shared secret, and verifies the decrypted message.

---

## Security notes

- Use lossless image formats such as PNG or BMP for correct extraction.
- Avoid sending JPEGs for embedded payload transport because lossy compression can alter the stego bits.
- The backend rejects JPEG uploads for embedding and extraction, enforcing lossless carriers only.
- Symmetric encryption is fixed to AES-256-GCM; AES-CBC is no longer supported.
- The backend stores ephemeral session state with TTL-backed session IDs and supports optional API key / HTTPS enforcement.
- The API never returns private key material in responses.
- Optional model training data can be supplied via `STEGO_DATASET_DIR` for real cover/stego corpus support.
- Validate input capacity and header integrity before attempting extraction and decryption.
- Keep deployment secrets out of source control by using environment variables and a local `.env` file.

---

## Notes for contributors

- Backend code lives under `pqcsecure-backend/`.
- Frontend code lives under `pqcsecure-frontend/src/`.
- Benchmark and measurement artifacts are commonly generated under `pi_benchmark/` and the backend working directory.
- The repository-level `.gitignore` is intended to keep generated artifacts, local environment files, and model/output files out of version control.

C:/Users/anilk/AppData/Local/Programs/Python/Python312/python.exe c:\Users\anilk\OneDrive\Desktop\pqc-1\pqcsecure-backend\app.py