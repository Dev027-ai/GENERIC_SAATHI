# GenericSaathi AI — Jan Aushadhi Sugam feature-parity plan

Research checked on 22 October 2026 against public official sources.

## Publicly documented Jan Aushadhi Sugam capabilities

The Government of India's PMBJP website describes the Jan Aushadhi Sugam app as providing:

1. Search for Jan Aushadhi generic medicines.
2. Compare generic and branded medicines using MRP and overall savings.
3. Locate nearby Jan Aushadhi Kendras through Google Maps/directions.

The Department of Pharmaceuticals 2025–26 annual report additionally describes checking medicine availability at nearby Kendras. The official Google Play listing identifies PMBI as the developer and was updated on 1 September 2026; its public listing does not document an API for third-party access.

Official references:
- PMBJP / Jan Aushadhi overview: https://janaushadhi.gov.in/about-pmbjb
- Official Kendra locator: https://janaushadhi.gov.in/near-by-kendra
- Official Play Store listing: https://play.google.com/store/apps/details?id=in.gov.pmbjp
- Department of Pharmaceuticals Annual Report 2025–26: https://pharma-dept.gov.in/sites/default/files/Annual%20Report%202025-26.pdf
- Official NPPA Pharma Sahi Daam price lookup: https://nppaipdms.gov.in/NPPA/PharmaSahiDaam/searchMedicine

## Changes in this project

- Medicine searches now rank single-ingredient records ahead of combination products when the user enters a single ingredient, such as `paracetamol`.
- Likely combination medicines are tagged with `is_combination` and `match_scope`; the UI labels them “Combination medicine · extra ingredients” rather than letting them look like an exact single-ingredient match.
- The result view can display up to eight candidates, rather than silently showing only the first candidate. The user can compare strength and form before proceeding.
- Existing bilingual UI, medicine search, Kendra search, map links, counter slip, WhatsApp share, and savings checklist are retained.
- Backend savings remain disabled unless the branded and Jan Aushadhi prices are independently verified for matching ingredient, strength, dosage form, pack size, source, and date.

## Known gaps — do not represent these as completed

- The bundled Jan Aushadhi price file was extracted from a user-provided source and its current publication date/MRP is not independently verified. It must not be represented as live pricing.
- The branded-price evidence CSV contains no verified records. NPPA is linked for manual confirmation; no documented public API was found during this review, so automatic live NPPA price retrieval is not claimed.
- The bundled Uttar Pradesh Kendra directory has 4,484 entries but no coordinates. Accurate distance ranking depends on an available geocoded source; otherwise use directory search and Google Maps fallback. Do not fabricate proximity.
- Real-time stock/availability at a specific Kendra is not connected to an authenticated live source. Do not display “in stock” or imply that an item is available at a given outlet.
- The current data is not sufficient to claim clinical interchangeability. Ingredient parsing is a conservative catalogue heuristic and requires review against authoritative product composition data before production.

## Search safety rules

1. Exact ingredient/name matches rank before fuzzy candidates.
2. Single-ingredient queries rank single-ingredient catalogue records before combination products that merely contain that ingredient.
3. Strength, dosage form and pack size must be shown so the user can distinguish records.
4. Fuzzy text similarity is discovery assistance only, not a clinical substitution recommendation.
5. Never calculate savings from unverified prices or different pack sizes.

## Data truth / integration boundaries

- Branded MRP: 100 pack-specific records are bundled from `data/sources/top_100_medicines_verified_nppa_prices.pdf`; the source PDF states August 2026 filed MRP records accessed on 2026-10-06. The app labels these as filed MRP, not guaranteed retail prices.
- Jan Aushadhi price: the supplied catalogue price export has no independently confirmed current publication/version date. It is shown as unverified and is not eligible for a savings calculation until reconciled to the current PMBI Product & MRP List.
- Kendra: the supplied Uttar Pradesh directory has 4,484 address records but no coordinates. Nearby search can use OpenStreetMap public map data as a fallback and reports when that source is unavailable. It does not fabricate coordinates or distances.
- Stock: no stock badge/status is shown in the app. No authenticated live stock source is connected.
- Clinical matching: simple single-salt searches rank single-ingredient records before combinations; a combination product is never an exact single-salt match. Exact pack/strength/form checks gate price matching.
