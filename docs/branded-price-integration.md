# Branded medicine price evidence integration

## What is implemented

- `GET /api/v1/prices/branded-search?q=...` searches the local evidence file and always returns the official NPPA Pharma Sahi Daam portal for live/manual confirmation.
- `POST /api/v1/medicines/compare` calculates savings only when both prices are independently marked verified and an exact brand/generic ingredient, strength, dosage form, and pack-size match exists.
- `/api/v1/integrations/status` reports whether verified evidence is loaded.
- No model-generated price is accepted as price evidence. Gemma can help parse names, but it cannot certify prices or medicine equivalence.

## Official source and limitation

NPPA's public Pharma Sahi Daam page supports medicine price lookup and is the official source to check brand MRP and regulated prices:

https://nppaipdms.gov.in/NPPA/PharmaSahiDaam/searchMedicine

The portal is an interactive website. No documented public search API was identified for this implementation. Therefore this project does not scrape hidden/private endpoints or falsely label a static result as live. The app links users to the official lookup and accepts reviewed records into a local evidence file.

## Add reviewed evidence

Edit `data/input/branded_price_evidence.csv`. One row per exact brand/strength/form/pack. Required columns:

`brand_name,generic_name,strength,dosage_form,pack_size,mrp_inr,source_url,source_name,checked_on,verification_status,reviewer_notes`

Only rows with `verification_status=Verified`, a valid numeric price, source URL/name, and check date are eligible. Record the price shown by the source and date checked. Never use Gemma's output as the source. Avoid normalizing pack sizes (e.g. 10 tablets vs 15 tablets) into an assumed equivalent.

**Important:** savings remain disabled unless the Jan Aushadhi price itself is also confirmed current and its source status is updated to a verified value in the catalogue. The currently bundled user-provided CSV explicitly says those prices are not independently verified/current, so the API intentionally returns no savings for those rows.

## Validation

Run `python -m pytest -q` from `backend/`.

## Imported 100-pack branded MRP evidence (2026-10-22)

The project now includes `data/input/branded_price_evidence.csv`, populated from `data/sources/top_100_medicines_verified_nppa_prices.pdf` (100 brand-pack records). The PDF describes August 2026 NPPA-filed MRP records accessed on 2026-10-06 and lists NPPA Pharma Sahi Daam plus Counterfoil brand listing sources. These are **filed maximum retail prices**, not necessarily discounted pharmacy selling prices. Each record carries a source URL, source name, checked date, pack size, strength and a reviewer note.

The catalogue attaches a branded price only if the single-ingredient salt, normalized strength, dosage form and pack size match exactly. A combination product cannot inherit a single-salt brand price. Search may show the sourced filed MRP with its date and source, but savings are still disabled unless the corresponding Jan Aushadhi price is also independently verified as current and the exact pack matches.

The PDF is not a live feed. Price records must be rechecked against the current NPPA record before production use; do not describe them as a guaranteed retail price.

## Lower-cost branded discovery fallback

Search results now include up to five source-backed brand packs for the same recorded single active ingredient, strength, and dosage form, ordered by listed filed MRP. This can help users explore options when a Jan Aushadhi Kendra is not nearby. Pack sizes are displayed because different packs are not directly comparable; this discovery list does not calculate savings or recommend switching. Combination products are excluded from single-ingredient alternatives. The available evidence is limited to the 100 loaded source records and should not be described as a complete market-wide cheapest-brand ranking. Users should confirm current price and ask a pharmacist/prescriber before changing a medicine.
