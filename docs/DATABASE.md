# SQLite persistence and repository layer

Step 10 uses SQLite because it is built into Python, requires no server for the prototype, and is sufficient for local inspection history and repeatable tests. Runtime databases are ignored by Git.

## Schema

The database contains `products`, `inspections`, `images`, `ocr_results`, `extracted_fields`, `normalized_fields`, `applicability_results`, `compliance_findings`, `evidence`, and `reviews`. Foreign keys are enabled for inspection/product, image/OCR, inspection/findings, finding/evidence, and finding/review relationships. Structured values are stored as safe JSON text and deserialized by the repository.

## Repository pattern

Application code calls methods on `Repository` and does not issue SQL. `Database` owns connection setup, schema initialization, foreign-key enforcement, and transactions. This keeps the storage backend replaceable by a future PostgreSQL adapter.

## Images and evidence

Images are stored as file references, not binary blobs. OCR, extraction, normalization, and evidence provenance are stored separately so original values and source references remain auditable. Reviewer corrections are appended to `reviews`; they do not overwrite AI/OCR evidence.

## Commands

Initialize/seed synthetic data explicitly:

```powershell
python scripts/seed_demo_data.py
```

The production database path is `data/compliance.db` and is intentionally excluded from Git.

