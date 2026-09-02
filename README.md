# SIH26034 — Packaged Commodity Legal Compliance Checker

An AI-assisted, explainable decision-support prototype for reviewing declarations on packaged commodity labels under India's Legal Metrology (Packaged Commodities) Rules, 2011.

## Project status

Phase 1 foundation is initialized. The application currently provides the Streamlit shell, modular package layout, dependency manifest, and clearly labelled synthetic/prototype data locations. Processing and review capabilities are being implemented incrementally.

## Design principle

The system separates document intelligence from legal evaluation:

`image/document → preprocessing → OCR → field extraction → normalization → applicability → configurable rule validation → evidence → human review`

OCR and extraction assist a reviewer. They are not legal truth, and uncertain cases must remain `NEEDS REVIEW`.

## Planned MVP features

- Multi-image package inspection with optional PDF artwork
- OCR with confidence and source evidence retained separately from compliance status
- Structured declaration extraction and normalization
- External, versioned prototype rule configuration
- Field-level findings: `COMPLIANT`, `WARNING`, `NON-COMPLIANT`, and `NEEDS REVIEW`
- Human review, comments, overrides, and inspection history
- Product repository, dashboard, version comparison, PDF, and CSV reports
- Synthetic demo data and automated tests

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Tesseract OCR is a system dependency for the OCR phase. Locally, install the
Tesseract executable and add it to `PATH` (or set `TESSERACT_CMD`). On
Streamlit Community Cloud, the committed `packages.txt` installs
`tesseract-ocr` and English language data; `pytesseract` alone is only the
Python wrapper. If the executable is unavailable, the application reports a
reviewable OCR configuration error rather than claiming successful OCR.

## Legal and data disclaimer

This is a prototype and does not constitute legal advice, legal certification, or an official government system. Prototype rules must be verified against current official Department of Consumer Affairs / Legal Metrology notifications by a qualified professional. Synthetic data must not be represented as official data.

## Future production direction

The modules are designed to allow later replacement of Streamlit with React, SQLite with PostgreSQL, local files with object storage, and Tesseract with a stronger document-OCR provider without making an AI model the source of legal truth.
