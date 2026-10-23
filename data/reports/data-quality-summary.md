# GenericSaathi AI — Data Quality Summary

## Source files

| File | Rows | Columns | Exact duplicate rows | Missing strength | Missing pack info | Missing price |
|---|---:|---:|---:|---:|---:|---:|
| `generic_saathi_common_medicines_130(1).csv` | 130 | 20 | 0 | 7 | 1 Jan Aushadhi pack size | 130 branded prices |
| `jan_aushadhi_extracted(2).csv` | 2,308 | 9 | 0 | 460 | 216 | 0 |

## Key observations

- All 130 Jan Aushadhi drug codes referenced in the 130-row shortlist exist in the 2,308-row catalogue.
- No exact duplicate rows were found in either file; the larger catalogue also has no duplicate drug codes.
- All 130 shortlist records are marked as needing pharmacist/data review. All 2,308 extracted catalogue records are marked `extracted_needs_human_review`.
- The 2,308 price values are labelled in the supplied data as MRP values printed in a PDF, with publication date not verified.
- The 130-row file has no branded price values, source URLs, or branded price check dates. Branded price research is still required.
- Savings are intentionally not calculated or displayed. Search results should not be interpreted as confirmation of therapeutic equivalence or current stock.

## Recommended next actions

1. Validate the 2,308-row catalogue against the current official Jan Aushadhi/PMBI source and record source publication/check dates.
2. Resolve missing strength and pack-size data.
3. Research exact branded products using brand, manufacturer, ingredient, strength, dosage form, and pack size.
4. Store candidate source evidence separately and require human review before promoting prices to `VERIFIED`.
5. Enable savings calculations only for verified products with comparable quantities and price types.
