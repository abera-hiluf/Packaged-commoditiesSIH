# Demo data and prototype rule library

All files in this directory are synthetic fixtures for SIH26034 development. They are fictional and must not be presented as government, Ministry, manufacturer, or official product data.

- `sample_products.json` contains six fictional products and their expected demo scenarios. `image_paths` points to package-label fixtures under `samples/package_images/`.
- `inspections.json` contains fictional historical inspection records used to exercise history and dashboard views.
- `rules/legal_rules.json` contains a small, versioned prototype rule configuration. It defines the shape of future configurable checks without claiming to reproduce current law.

## Data flow

`sample product → package image → later OCR → later extracted fields → later rule engine → later compliance result`

Source product data describes the product and supplied images. Later OCR produces raw text and OCR evidence. Later extraction produces structured fields while preserving source text. Later rule evaluation consumes the configured rules and extracted fields to produce validation findings. A later compliance layer aggregates those findings for human review.

Rules are separate from Python so they can be versioned, reviewed, and replaced without burying legal assumptions in application logic. They must still be verified against current official Legal Metrology notifications by a qualified professional before production use.

