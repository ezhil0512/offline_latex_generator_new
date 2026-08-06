# Local Models Directory

This directory holds the pre-trained weights for the offline OCR and layout models.
Due to file size constraints, models are git-ignored and should be downloaded locally before running the application.

## Layout of Models

Create the following directories and place downloaded models inside them:

- `models/text_ocr/` (PaddleOCR detection/recognition models)
- `models/math_ocr/` (Pix2Text formula recognition models)
- `models/layout/` (PaddleOCR layout classification models)
- `models/table/` (PaddleOCR table structures models)

## Download Script

You can use the helper script `scripts/download_models.py` to fetch these weights automatically:

```bash
python scripts/download_models.py
```
