# GenericSaathi AI

GenericSaathi AI is a responsive medicine-catalogue comparison MVP for India. It searches a supplied Jan Aushadhi catalogue alongside a broad Indian medicine/brand catalogue, shows source-listed prices when available, helps find Jan Aushadhi Kendras, and lets users save comparisons and hear a short Hindi savings announcement.

> **Price and medicine safety:** Prices imported from the supplied CSV catalogues are source-listed values, not guaranteed current retail prices or live pharmacy quotes. A catalogue match does not prove clinical interchangeability. Check the exact ingredient, strength, form and pack with a pharmacist, and do not change a prescribed medicine without advice from a qualified professional.

## Features implemented

- English/Hindi interface and medicine search with typo-tolerant catalogue matching.
- Branded options matched conservatively by composition, strength, dosage form and pack count; a compatible Dolo 500 record is promoted for Paracetamol 500 mg when present in the catalogue.
- Fast autocomplete that skips broad brand enrichment; full catalogue results are displayed without waiting for optional spelling correction.
- Indicative price difference in rupees and percentage when listed prices and units can be compared. Differing tablet/capsule/liquid pack sizes are normalized by comparable unit where the source records allow it.
- Save medicine to the browser's local storage, with automatic scrolling to the Savings checklist and duplicate prevention.
- Hindi text-to-speech for the listed prices and calculated difference; the announcement ends with “धन्यवाद।” when the browser supports speech synthesis.
- Browser location permission on demand. The app opens a nearby Jan Aushadhi search in Google Maps and attempts to show nearby mapped centres in the app, including distance and map/direction links where coordinates are available.
- Manual search in the supplied 4,484-entry Uttar Pradesh Kendra directory by name, district, PIN code, Kendra code or other address text.
- Optional prescription image OCR endpoint and review interface; OCR requires the system Tesseract engine to be installed separately.

## Data included

- `data/input/indian_medicine_data.csv`: broad branded-medicine dataset with source-listed prices and composition/pack fields. Current retail validity is not established.
- `data/input/jan_aushadhi_extracted(3).csv`: 2,308 Jan Aushadhi catalogue records. The supplied source flags the extracted data for human review and does not confirm the publication date as current.
- `data/input/kendra_directory.csv`: 4,484 Kendra directory entries extracted from a supplied Uttar Pradesh directory. Addresses are not independently reverified, and latitude/longitude are not populated in the supplied file.
- `data/input/branded_price_evidence.csv`: structured evidence file for independently checked prices; the distributed file may be empty until evidence is added through a documented review process.

Because the Kendra source has no coordinates, nearby searches first query public OpenStreetMap data through the backend. Map coverage may be incomplete; the nearby list is not an official or exhaustive directory and does not establish opening status, availability, or stock. Google Maps remains available as a fallback.

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer recommended
- Internet connectivity for OpenStreetMap nearby lookups and optional Gemini spelling correction

## Run locally on Windows PowerShell

Open two separate PowerShell terminals from the extracted project folder.

### Terminal 1 — backend

```powershell
cd "PATH\TO\generic-saathi-ai\backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Optional: enable Gemini spelling correction on the backend (not required for basic catalogue search):

```powershell
$env:GEMINI_SEARCH_API_KEY = "YOUR_GOOGLE_AI_STUDIO_API_KEY"
$env:GEMINI_SEARCH_MODEL = "gemini-2.5-flash"
python -m uvicorn app.main:app --reload --port 8000
```

Open the API documentation at `http://127.0.0.1:8000/docs`.

### Terminal 2 — frontend

```powershell
cd "PATH\TO\generic-saathi-ai\frontend"
npm install
npm run dev
```

Open the local Vite URL printed in the terminal (normally `http://localhost:5173`). Use localhost or HTTPS for browser geolocation and microphone permissions. The default API URL is `http://localhost:8000`; set `VITE_API_BASE_URL` before running the frontend if the backend uses another URL.

## Tests and verification

From the project folder:

```powershell
cd backend
python -m pytest -q
python -m compileall -q app tests
```

The current implementation adds regression tests for Paracetamol/Dolo matching, excluding combination products from a single-ingredient search, and lightweight autocomplete. The full frontend production build should be checked locally with:

```powershell
cd frontend
npm install
npm run build
```

## Limitations

- The medicine catalogues and source prices are not a live pharmacy price/stock service. The app displays their source-listed prices as such, with current validity unverified.
- A pack-normalized difference is indicative arithmetic, not a guarantee of the amount a customer will save at checkout.
- A brand option found through ingredient/strength matching is for comparison discovery only, not a substitution recommendation.
- Nearby centre coverage depends on OpenStreetMap data and public service availability; confirm the centre's address, hours and operation before travelling.
- Hindi speech requires browser speech synthesis and an installed Hindi voice; availability varies by device/browser.
- OCR requires Tesseract to be installed and accessible on PATH. OCR extracts text only and does not prescribe or validate a medicine.
- Production authentication, persistent server-side user accounts, managed catalogue refresh, verified centre-coordinate maintenance, and deployment hardening remain out of scope for this MVP.

## API quick reference

- `GET /api/v1/health`
- `GET /api/v1/medicines/search?q=<medicine>&limit=20`
- `GET /api/v1/medicines/search?q=<medicine>&include_brand_options=false` — lightweight search/autocomplete
- `GET /api/v1/kendras/search?q=<city-or-area>`
- `GET /api/v1/kendras/nearby?lat=<latitude>&lon=<longitude>&radius_km=50`
- `POST /api/v1/prescriptions/ocr` — optional OCR, requires local Tesseract
- `GET /api/v1/medicines/ai-correct?q=<medicine>` — optional Gemini spelling correction

Keep all API keys in the backend environment. Never put secret keys into frontend `VITE_` variables or commit them to source control.
