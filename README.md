# GenericSaathi AI

Mobile-responsive medicine catalogue search MVP for India. It helps users search medicine catalogues, review possible matches, inspect source and data-quality notes, and find configured Jan Aushadhi Kendra directory entries. The project is designed to avoid presenting unverified branded-vs-generic savings as facts.

## Features in this repository

- React + TypeScript + Vite frontend with responsive English/Hindi interface.
- FastAPI backend for catalogue search, fuzzy text matching, OCR text extraction, integration status, Kendra-directory lookup, and price-evidence review queue.
- CSV-backed catalogue loading and data-quality reporting.
- Optional prescription OCR endpoint (requires the Tesseract system engine).
- Optional AI text-review adapter configured through server-side environment variables.
- Backend tests for catalogue matching, integrations, and safe behavior when data is unavailable.

## Run locally

### Backend (Python 3.10+)

```powershell
cd backend
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend (Node.js 20+ recommended)

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if the API is not at `http://localhost:8000`.

### Tests

```powershell
cd backend
python -m pytest -q
```

## Configuration

Copy the relevant `.env.example` file to `.env` and fill in provider values only after checking the selected provider's current documentation. Never commit `.env`, API keys, patient prescriptions, or private data.

## Medicine safety and data limitations

- Fuzzy/text similarity is not evidence of pharmaceutical or clinical equivalence.
- Match strength, dosage form, pack size, and source before comparing prices.
- Catalogue prices may be stale or unverified; availability and stock are not guaranteed.
- Branded price evidence is incomplete. The app must not invent savings or present unverified savings percentages.
- Do not change a prescribed medicine without advice from a qualified doctor or pharmacist.
- OCR and AI text organization are assistive only; a human must review extracted medicine names.
- Do not send prescription/patient data to third-party services without informed consent and suitable privacy controls.

## Production readiness

This is an MVP, not a production-ready medical service. Verify prices against authoritative current sources, configure and validate integrations, install Tesseract (and optional PDF OCR dependencies), run the frontend production build, and add authentication/authorization, audit logging, rate limiting, monitoring, retention controls, and deployment security before public launch.

See `CHANGELOG-2026-10-23.md` and `docs/` for implementation notes and known limitations.
