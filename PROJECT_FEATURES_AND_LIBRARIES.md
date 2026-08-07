# PQCSecure Project Features and Libraries

## 1. Project Overview

`PQCSecure` is a prototype secure transmission project that combines:
- Post-quantum key encapsulation
- Symmetric authenticated encryption
- Adaptive image steganography
- Local stego detection and ML-based analysis
- Benchmarking for edge hardware
- React frontend for demonstration and UI interaction

The workspace is organized into:
- `pqcsecure-backend/` — Flask backend, crypto, steganography, AI, API endpoints
- `pqcsecure-frontend/` — Vite + React frontend
- `pi_benchmark/` — performance and device benchmark scripts

---

## 2. Features Used in This Project

### 2.1 Backend Features

- **Flask REST API** in `pqcsecure-backend/app.py`
  - `/api/keygen`
  - `/api/encrypt-embed`
  - `/api/extract-decrypt`
  - `/api/sample-cover`
  - `/api/benchmark`
  - `/api/ai-optimize`
  - `/api/ai-detect`
  - `/api/ai-compare`
  - `/api/ai-train`
  - `/api/health`
- **Session-based key handling** using in-memory session store `_key_store`
- **HTTPS / API key enforcement** via environment flags
- **Lossless image validation** for stego workflows
- **Error handling** for invalid payloads, malformed images, and large uploads

### 2.2 Cryptography Features

- **Post-quantum key encapsulation** using `ML-KEM-768`
- **Classical algorithm support**:
  - `RSA-2048`
  - `X25519`
- **AES-256-GCM authenticated encryption** with IV and auth tag support
- **Payload construction and parsing** for KEM ciphertext, IV, auth tag, and encrypted message
- **Dynamic payload header** packing lengths and sizes for safe extraction

### 2.3 Steganography Features

- **Adaptive LSB embedding** in `pqcsecure-backend/steganography.py`
  - Uses 32×32 image blocks
  - Selects high-texture blocks first using Laplacian variance
- **Bit-depth support**: 1, 2, and 3 LSBs per channel
- **Payload capacity calculation** for each image and bit depth
- **Lossless stego image creation** using PNG output
- **Payload extraction** using same adaptive ordering as embedding
- **Image quality metrics**:
  - MSE
  - PSNR
  - SSIM
- **Chi-square steganalysis detection** for hidden content probability
- **Grayscale histogram comparison** and diff image generation

### 2.4 AI / Stego Detection Features

- **Feature extraction** in `pqcsecure-backend/stego_ai.py`
  - Unique color ratio
  - Chi-square probability
  - LSB entropy
  - Horizontal difference mean
  - Horizontal difference variance
  - Parity bin asymmetry
  - Laplacian variance
- **ML model training** and prediction support
- **Synthetic dataset creation** when local dataset is unavailable
- **Cover/stego comparison** diagnostics
- **Local detector model storage** via `stego_model.pkl` and metadata files

### 2.5 Benchmarking Features

- **KEM algorithm benchmarks** in `pi_benchmark/benchmark.py`
  - Key generation, encapsulation, and decapsulation timings
- **AES-GCM throughput benchmarks**
- **Steganography performance benchmark**
- **End-to-end pipeline timing** for full secure stego flow
- **Raspberry Pi targeted scripts**:
  - `run_speed_test.py`
  - `run_speed_test2.py`
- **Result export** to `benchmark_results.json`

### 2.6 Frontend Features

- **React UI** in `pqcsecure-frontend/src/App.jsx`
- **Vite development environment**
- **Tailwind CSS styling**
- **API integration** with backend via `VITE_API_URL`
- **Interactive histograms** and stego analysis charts
- **Image zoom / magnifier component**
- **Error handling for API responses**
- **Visualization of cover / stego histograms** and difference detection

### 2.7 Deployment / Support Files

- `.env.example` files for backend and frontend environment configuration
- `pqcsecure-backend/Procfile` for platform deployment
- `pqcsecure-frontend/package-lock.json` for reproducible frontend installs
- `pqcsecure-backend/.gitignore` and `pqcsecure-frontend/.gitignore`

---

## 3. Files and Their Purpose

### 3.1 Backend Files

- `pqcsecure-backend/app.py`
  - Main Flask server and API endpoints
  - session handling, validation, workflows, AI endpoints
- `pqcsecure-backend/crypto.py`
  - KEM key generation, encapsulation, decapsulation
  - AES-256-GCM encryption and decryption
  - Payload build / parse helpers
- `pqcsecure-backend/steganography.py`
  - Adaptive LSB embed/extract functions
  - stego capacity, image metrics, chi-square detector
- `pqcsecure-backend/stego_ai.py`
  - Stego detection feature extraction and model training
  - dataset build and prediction logic
- `pqcsecure-backend/benchmark.py`
  - Benchmark helper functions for KEM, AES, and stego timing
- `pqcsecure-backend/run_benchmarks_quick.py`
  - quick benchmark runner for the backend package
- `pqcsecure-backend/.env.example`
  - example environment variables for backend settings
- `pqcsecure-backend/Procfile`
  - deployment process file for cloud platforms like Heroku
- `pqcsecure-backend/tests/`:
  - `test_ai_compare_endpoint.py`
  - `test_ai_compare.py`
  - `test_security.py`
  - `test_stego_ai.py`
  - Backend pytest coverage for AI, security, and stego behavior
- `pqcsecure-backend/__init__.py`
  - package marker file
- `pqcsecure-backend/.gitignore`
  - backend ignore rules

### 3.2 Frontend Files

- `pqcsecure-frontend/package.json`
  - frontend dependency list and scripts
- `pqcsecure-frontend/package-lock.json`
  - locked package versions for npm
- `pqcsecure-frontend/vite.config.js`
  - Vite build configuration
- `pqcsecure-frontend/postcss.config.js`
  - PostCSS configuration for Tailwind
- `pqcsecure-frontend/tailwind.config.js`
  - Tailwind CSS settings
- `pqcsecure-frontend/README.md`
  - frontend-specific setup and run notes
- `pqcsecure-frontend/.env.example`
  - example frontend environment variables (`VITE_API_URL`)
- `pqcsecure-frontend/src/main.jsx`
  - application entry point for React
- `pqcsecure-frontend/src/App.jsx`
  - main frontend UI and analytics components
- `pqcsecure-frontend/src/index.css`
  - global frontend styling
- `pqcsecure-frontend/index.html`
  - root HTML template for the React app
- `pqcsecure-frontend/.gitignore`
  - frontend ignore rules

### 3.3 Benchmark Files

- `pi_benchmark/benchmark.py`
  - benchmark functions and measurement helpers
- `pi_benchmark/run_speed_test.py`
  - main Pi benchmark runner printing summary and JSON results
- `pi_benchmark/run_speed_test2.py`
  - algorithm comparison runner with stego quality metrics
- `pi_benchmark/README.md`
  - Raspberry Pi benchmark setup and instructions
- `pi_benchmark/requirements.txt`
  - Python dependencies used by benchmark scripts
- `pi_benchmark/crypto.py`
  - local benchmark-specific cryptography helper functions
- `pi_benchmark/implementation_plan.md`
  - plan or notes for benchmark implementation
- `pi_benchmark/steganography.py`
  - benchmark-specific steganography helper functions

### 3.4 Root Files

- `README.md`
  - project overview, setup, quick start
- `PROJECT_FEATURES_AND_LIBRARIES.md`
  - this generated summary file
- `final-project.pptx`
  - presentation file in the repository
- `sample.png`
  - sample image file available in repo root
- `.gitignore` and `.vscode` folder

---

## 4. Libraries and Purpose

### 4.1 Python Libraries (`pqcsecure-backend/requirements.txt`)

- `flask`
  - web framework for backend API endpoints
- `flask-cors`
  - CORS support for frontend/backend local development
- `kyber-py`
  - post-quantum ML-KEM implementation (`ML-KEM-768`)
- `pycryptodome`
  - RSA, ECC, AES-GCM, and other cryptographic primitives
- `pillow`
  - image file handling, reading, writing, and conversion
- `numpy`
  - image arrays, numeric processing, histogram calculations
- `gunicorn==21.2.0`
  - production-ready WSGI server for deployment
- `scikit-image`
  - PSNR and SSIM image quality metrics
- `scikit-learn`
  - ML classification and model utilities for stego detection

### 4.2 Frontend Libraries (`pqcsecure-frontend/package.json`)

Dependencies:
- `react`
  - UI library used to build the frontend application
- `react-dom`
  - browser rendering support for React

Dev dependencies:
- `vite`
  - development server and frontend bundler
- `@vitejs/plugin-react`
  - React plugin for Vite
- `tailwindcss`
  - utility-first CSS styling framework
- `autoprefixer`
  - autoprefix CSS for browser compatibility
- `postcss`
  - CSS processing pipeline for Tailwind and Vite

### 4.3 Benchmark-specific Libraries

The benchmark scripts use the same Python dependencies plus built-in modules:
- `time`
  - timing and performance measurement
- `json`
  - JSON serialization for benchmark output
- `hashlib`
  - cryptographic hashing and shared secret derivation support
- `random`
  - synthetic data generation for benchmark images
- `math`
  - numerical operations for stego metrics
- `os`, `io`, `pathlib`
  - filesystem and stream handling
- `PIL.Image`
  - image generation and manipulation during benchmark tests

---

## 5. Config and Environment Files

### Backend environment
- `pqcsecure-backend/.env.example`
  - shows example variables like `SECRET_KEY`, `API_KEY`, `REQUIRE_HTTPS`, `EXPOSE_PRIVATE_KEY`, `SESSION_TTL_SECONDS`, `STEGO_DATASET_DIR`

### Frontend environment
- `pqcsecure-frontend/.env.example`
  - shows `VITE_API_URL` for backend integration

---

## 6. Notes on Usage

### Backend startup
```bash
cd pqcsecure-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Frontend startup
```bash
cd pqcsecure-frontend
npm install
npm run dev
```

`VITE_API_URL` should point to the backend API base URL, typically `http://localhost:5001/api`.

---

## 7. Summary

This file documents every major feature used by the project, the backend and frontend files that implement those features, and the main libraries with their purpose.

If you want, I can also create a second markdown file with an installation guide and feature matrix table tailored for a project report or presentation.
