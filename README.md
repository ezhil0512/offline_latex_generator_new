# Offline LaTeX Generator

An offline application that converts scanned PDFs and images of question papers
into high-quality LaTeX while preserving the original document structure.

The entire application runs locally without using any cloud service or external
API.

---

# Project Status

Under Active Development

Current Phase:

- Complete: Project Architecture
- Complete: Project Scaffolding
- Complete: Workspace Lifecycle and Upload Validation
- Complete: Phase 4 PDF and Image Loader
- Complete: Phase 5 Processing Pipeline
- Next: Phase 6 (not started)

Implementation is being developed one feature at a time.

Every feature is manually verified before moving to the next phase.

---

# Features

Implemented:

- PDF and Image Upload
- Workspace Lifecycle
- Upload Validation
- PDF and Image Loading

Planned:

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
└── tests/
```

---

# Privacy

This application never uploads any user data.

All processing is performed locally.

Uploaded PDFs, images, OCR results, temporary files, generated LaTeX, generated
PDFs, debug artifacts, and ZIP files exist only inside a temporary workspace and
are automatically removed after download, timeout, or failure.

Only source code, configuration, documentation, tests, and local models remain
permanently.

---

# Development Workflow

Every feature follows the same workflow:

```text
Implement
  -> Manual Verification
  -> User Approval
  -> Git Commit
  -> Next Feature
```

No feature is considered complete until it has been manually verified.

---

# Phase 4 Status

Phase 4 is complete.

Implemented scope:

- `PDFLoader` loads uploaded workspace PDFs into in-memory Pillow images.
- `ImageLoader` loads uploaded workspace images into in-memory Pillow images.
- Loaders accept only `job_id` and filename, and resolve files through the
  workspace manager.
- PDF conversion uses `pdf2image` with Poppler, including optional
  `POPPLER_PATH` configuration.

Phase 4 does not include preprocessing, OCR, layout detection, question
detection, segmentation, LaTeX generation, preview generation, or export
workflows. Those belong to later phases, starting with Phase 5.

# Phase 5 Status

Phase 5 is complete.

Implemented scope:

- Contrast enhancement
- Binarization
- `deskew` flag is recognized by the pipeline, but is currently a no-op because
  the frozen architecture does not include a deskew implementation.

Latest verification:

```text
pytest: 36 passed / 36 collected
Phase 5 committed and pushed
Phase 6 has not started

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
