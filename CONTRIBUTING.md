# Contributing to GenericSaathi AI

## Before opening a change

1. Keep API keys and provider secrets in local `.env` files; commit only `.env.example` templates.
2. Never commit prescription images, identifiable patient data, generated user uploads, virtual environments, or dependency folders.
3. Preserve the medicine-safety rules: text similarity is not clinical equivalence, and savings must not be shown without comparable product identity, pack size, trustworthy price evidence, and source freshness.
4. Add or update backend tests for changed behavior.
5. Run `cd backend && python -m pytest -q` and `cd frontend && npm install && npm run build` before claiming validation. If a command cannot run, state that clearly in the PR.

## Pull requests

Describe the user-facing change, data/source assumptions, tests run, known limitations, and any privacy or safety implications. Do not claim a feature is production-ready merely because it works locally.
