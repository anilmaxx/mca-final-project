# PQCSecure

This repository contains a demo application for secure message transmission using post-quantum cryptography, AES encryption, and image steganography.

## Project structure
- [pqcsecure-backend](pqcsecure-backend) — Flask API backend
- [pqcsecure-frontend](pqcsecure-frontend) — Vite + React frontend
- [implementation_plan.md](implementation_plan.md) — implementation notes and roadmap

## Quick start

### Backend
```bash
cd pqcsecure-backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python app.py
```

### Frontend
```bash
cd pqcsecure-frontend
npm install
npm run dev
```

## Security notes
The backend now supports optional API key enforcement, HTTPS checks, configurable secret handling, and session expiration. Copy [pqcsecure-backend/.env.example](pqcsecure-backend/.env.example) to [pqcsecure-backend/.env](pqcsecure-backend/.env) and set your values before deployment.

## Notes
- The project is intended as a demo/prototype, not a production-grade secure messaging system.
- See the backend and frontend readme files for more detailed setup instructions.
