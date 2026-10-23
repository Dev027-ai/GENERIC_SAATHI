# Uttar Pradesh Jan Aushadhi Kendra directory

- Source document: `data/sources/kendra_22_10_2026 @ 12_40_4.pdf` (provided in this conversation).
- Extracted CSV: `data/input/kendra_directory.csv`.
- Imported records: 4,484, numbered 1–4,484 in the PDF.
- Fields: PDF serial, Kendra code, name, state, district, PIN code, address, source document date, PDF page, and blank latitude/longitude fields.
- Data extraction date shown by the supplied document: 2026-10-22. This is a document date, **not** a claim that each centre was independently verified on that date.
- Coordinates: the source PDF has no latitude/longitude fields. The app does not invent coordinates or show fabricated distances. Nearby distance sorting requires a permitted geocoding source or a coordinate-enriched official directory. Until then, search by district/PIN/Kendra code/name and open address-based Google Maps search links.
- Status: imported from the supplied document; not independently reverified. Confirm the centre address, operation status, opening hours, and stock with PMBI/the centre before travel.
- The `source_url` and `last_verified` CSV columns are intentionally blank because the PDF itself does not provide a stable direct URL or per-centre verification timestamp.

## Location-based nearby search

When a user taps **Use my location · find nearby**, the browser requests permission and sends the coordinates to `/api/v1/kendras/nearby`. If the directory itself has coordinates, results are sorted by great-circle distance. The imported PDF does not contain coordinates, so the endpoint instead queries public OpenStreetMap Overpass data for nearby Jan Aushadhi-related places, calculates straight-line distances from the mapped coordinates, and links each result to its map source and driving directions. If live map lookup fails or finds nothing, the UI offers a Google Maps search centered on the user's coordinates.

**Coverage limitation:** OpenStreetMap is community-mapped and may omit centres. These results are not a complete or independently verified representation of all 4,484 PDF entries; verify the address and operating status before travelling. This avoids inventing coordinates or presenting PIN-code centroids as exact centre locations. The full imported directory remains searchable by name, district, PIN and Kendra code.

## Browser live-location behaviour

The frontend uses the browser Geolocation API only after the user presses the live-location button and grants permission. It uses `watchPosition` while enabled, refreshes nearby Kendra results when the device moves by at least approximately 250 metres, and stops watching when the user presses Stop or leaves the page. Coordinates are kept in page memory and are not saved to the app's local storage or sent to the medicine catalogue; the current coordinates are sent to the nearby-Kendra API to calculate nearby mapped places. Browser geolocation generally requires HTTPS or localhost. Nearby results depend on OpenStreetMap coverage and must be verified before travelling.
