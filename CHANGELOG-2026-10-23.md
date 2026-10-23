# GenericSaathi AI — improvements (23 October 2026)

- Prescription OCR now presents likely medicine lines as a patient-controlled single selection. The patient chooses a medicine before catalogue search; raw OCR text and detected personal details are not shown in the interface.
- Catalogue results are returned and scrolled into view independently of Gemini Google Search. Live web listings load in the background with an 18-second client wait limit and a retry control, so a slow web lookup does not keep the primary medicine search in its loading state.
- Added a Gemini-assisted spelling-normalization endpoint for zero-result searches. It only suggests a spelling/query correction; the application then reruns the catalogue search. Existing local typo-tolerant fuzzy matching remains available without Gemini.
- Added a “Hear in Hindi” action to medicine result cards using the browser's Hindi speech synthesis voice when available. It only announces a rupee savings amount when the comparison and comparable pack are verified; otherwise it speaks a polite price-verification message.
- Increased base type sizes, controls, focus visibility, spacing and touch targets for older users and small screens.
- Added process-local caching for loaded catalogue data and recent medicine search results to reduce repeat-search latency.
- Existing safeguards remain: web-listed prices are not treated as verified pharmacy quotes; stock is not asserted; unverified or non-comparable prices do not trigger a claimed savings amount.

## Configuration

For Gemini-assisted typo correction and Google Search-grounded listings, configure `GEMINI_SEARCH_API_KEY` and `GEMINI_SEARCH_MODEL` in the backend environment. For the separate Gemma search-term integration, use `GEMMA_PROVIDER=gemini-api`, `GEMMA_API_KEY`, and `GEMMA_MODEL_ID` as documented in `backend/.env.example`. Keep keys on the backend only.

Hindi audio depends on browser support for `speechSynthesis` and an installed Hindi voice; Chrome/Edge generally provide the best compatibility. This feature does not upload audio.

## Verification

- Backend test suite: 23 passed.
- Python syntax compilation: passed.
- TypeScript/JSX syntax transpilation: passed with zero syntax diagnostics.
- Full frontend production build was not verified in this environment because `npm install` timed out before dependencies were installed; run `npm install` and `npm run build` locally after extracting the project.

## Price comparison and Hindi voice UX update

- Removed the separate Gemini + Google web-price panel, including its unavailable/zero-results notice and retry action.
- Medicine search no longer waits for or triggers a separate live web-price lookup; catalogue search remains the primary flow.
- Price cards now show available listed branded and Jan Aushadhi prices and calculate the rupee difference plus a percentage relative to the branded listed price, without hiding the calculation behind a verification-status flag.
- Save medicine stores the available listed prices; the savings list shows the difference from available prices.
- Hear in Hindi now directly reads the two listed prices and the rupee/percentage difference. It no longer asks users to verify prices before providing the comparison.
- Source and current-price limitations remain described as listed-price estimates; the UI does not claim an unverified listing is a guaranteed live pharmacy price.
- Validation: backend tests passed (23 tests). TSX transpilation syntax check passed. Frontend production build was not verified because dependency installation timed out.

## UX implementation follow-up

- Nearby search now asks for browser location only after the user clicks the Google Maps action, opens a nearby Jan Aushadhi search in Maps, and requests a nearby list from OpenStreetMap through the backend. Permission or map-service failures leave Google Maps/manual city/district/PIN search as fallback.
- Manual Kendra search and nearby results automatically scroll into view after the action.
- Save medicine stores the available listed-price comparison, prevents duplicate entries for the same medicine/pack/brand, opens the Savings checklist, and scrolls to it.
- Search results scroll into view automatically. Search now has a bounded timeout and does not wait for the optional spelling-normalization request; autocomplete skips wide branded-option enrichment.
- Same-ingredient branded candidates are filtered by composition, strength, dosage form and pack count. For Paracetamol Tablets IP 500 mg, the supplied broad catalogue contains a Dolo 500 Tablet 10-tablet record listed at ₹10.19, matched to the Jan Aushadhi 10-tablet record listed at ₹6.57. The displayed pack-level arithmetic is ₹3.62 (about 35.5%) based on source-listed prices; those values have not been independently verified as current retail prices.
- Hindi speech announces the available listed branded and Jan Aushadhi prices, any safely calculable indicative difference and percentage, and ends with “धन्यवाद।” Missing/incomparable values are handled without inventing numbers.
- Added backend regression tests for the Paracetamol/Dolo case, single-ingredient matching against combination products, and lightweight autocomplete.

### Verification for this follow-up

- Backend test suite: 26 passed.
- Python syntax compilation: passed.
- TypeScript/JSX syntax transpilation: zero syntax diagnostics.
- A full Vite production build could not be completed here because `npm install` timed out before installing frontend dependencies. Run `npm install` and `npm run build` in the frontend folder locally to complete that check.
