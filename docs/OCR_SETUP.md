# Tesseract OCR setup

The MVP uses [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) through `pytesseract`. Tesseract performs text recognition; the Python module preserves its text, OCR confidence, line structure, and bounding boxes for later extraction and evidence.

## Windows

Install Tesseract using a trusted Windows distribution, then either add its installation directory to `PATH` or set the executable path for the current shell:

```powershell
$env:TESSERACT_CMD = "C:\Path\To\tesseract.exe"
```

Do not put a personal machine path in source code. The application reports a clear configuration error when Tesseract cannot be discovered.

## Streamlit Community Cloud

The repository includes `packages.txt`, which asks Streamlit Cloud to install
the system packages `tesseract-ocr` and `tesseract-ocr-eng`. `requirements.txt`
only installs the Python wrapper (`pytesseract`); both files are required for
OCR in the deployed environment. After committing this file, redeploy or
restart the app so the build image is recreated.

The app reports `OCR engine unavailable/configuration error` when the binary is
not present. This is intentionally distinct from `OCR completed but no usable
text was detected`, which means the engine ran but returned no text.

## Important distinction

`OCR Confidence` estimates how confidently Tesseract recognized text tokens. It is not compliance confidence, legal confidence, or a compliance decision. Later extraction and rule-validation modules must treat OCR output as evidence that requires review.

## Pipeline

`package image → preprocessing.py → OCR-ready image → ocr.py → OCRResult → next: extractor.py`

This phase does not extract MRP, quantities, or other declarations and does not determine compliance status.
