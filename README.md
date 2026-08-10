# Offline LaTeX Generator

An offline application that converts scanned PDFs and images of question papers into high-quality LaTeX while preserving the original document structure.

The entire application runs locally without using any cloud service or external API.

---

# Project Status

🚧 **Under Active Development**

Current Phase:

- ✅ Project Architecture
- ✅ Project Scaffolding
- 🔄 Workspace & Processing Pipeline (Next)

Implementation is being developed one feature at a time.

Every feature is manually verified before moving to the next phase.

---

# Features (Planned)

- PDF and Image Upload
- Automatic Question Detection
- Question Segmentation
- MCQ Option Detection
- Layout Detection
- Formula Reconstruction
- Offline OCR Routing
- Text Recognition
- Formula Recognition
- Table Recognition
- Diagram Extraction
- Structured JSON Generation
- LaTeX Generation
- LaTeX Validation
- HTML Preview
- PDF Preview
- ZIP Export
- Automatic Workspace Cleanup

---

# Supported Input

- PDF
- PNG
- JPG
- JPEG
- BMP
- TIFF

---

# Planned Output

- LaTeX (.tex)
- PDF
- HTML Preview
- ZIP Package

---

# Project Structure

```text
offline_latex_generator/

├── src/
│   └── offline_latex_generator/
│       ├── web/
│       ├── pipeline/
│       ├── input/
│       ├── loader/
│       ├── preprocessor/
│       ├── question_detector/
│       ├── question_segmenter/
│       ├── option_detector/
│       ├── layout_detector/
│       ├── formula_reconstructor/
│       ├── ocr_router/
│       ├── recognizer/
│       ├── structurer/
│       ├── generator/
│       ├── preview/
│       ├── cleanup/
│       └── utils/

├── config/
├── docker/
├── docs/
├── models/
├── samples/
├── tests/
```

---

# Privacy

This application never uploads any user data.

All processing is performed locally.

Uploaded PDFs, images, OCR results, temporary files, generated LaTeX, generated PDFs, debug artifacts, and ZIP files exist only inside a temporary workspace and are automatically removed after download, timeout, or failure.

Only source code, configuration, documentation, tests, and local models remain permanently.

---

# Development Workflow

Every feature follows the same workflow:

```
Implement
    ↓
Manual Verification
    ↓
User Approval
    ↓
Git Commit
    ↓
Next Feature
```

No feature is considered complete until it has been manually verified.

---

# Technology Stack

Frontend

- HTML
- CSS
- JavaScript

Backend

- Flask

OCR

- PaddleOCR
- Pix2Text

Image Processing

- OpenCV
- Pillow

PDF Processing

- pdf2image
- Poppler

LaTeX

- pdflatex

Configuration

- YAML

---

# PDF Test Dependency

PDF loading uses `pdf2image`, which shells out to Poppler tools such as
`pdfinfo` and `pdftoppm`.

On Windows, do not rely on MiKTeX-provided PDF tools for tests. The test suite
will provision a project-local Poppler build under `.cache/` when needed and set
`POPPLER_PATH` for the test process.

To prepare Poppler manually for local development, run:

```powershell
python scripts\install_poppler_windows.py
```

The script prints the `POPPLER_PATH` value. The downloaded files stay in
`.cache/` and must not be committed.

---

# License

This project is licensed under the MIT License.
