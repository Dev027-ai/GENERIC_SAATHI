# Medicine matching and price-comparison safeguards

GenericSaathi AI is an information and search aid, not a prescribing service.

- A fuzzy match score is a text-retrieval signal only. It does not establish that two medicines are interchangeable.
- Before any price comparison, verify active ingredient, strength, dosage form, pack quantity, and the precise product identity.
- Record the source URL, price type, observation date, and reviewer for price evidence. Mark stale, incomplete, or ambiguous records as unverified.
- Do not calculate or display savings when either price is missing or product quantities are not comparable.
- Do not infer local stock, opening hours, or availability from a directory entry.
- Prescription OCR may misread medicine names. Require user review before a result is searched; do not infer dose or treatment from OCR output.
- Do not recommend changing or stopping a prescribed medicine. Direct users to a qualified doctor or pharmacist for clinical decisions.
- Minimize retention of prescription images and location data. Obtain informed consent before sending sensitive information to an external provider.

These safeguards are product requirements and do not replace legal, clinical, privacy, or security review before public deployment.
