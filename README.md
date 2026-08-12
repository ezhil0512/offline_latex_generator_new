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
- Complete: Phase 6 OCR Foundation/Integration
- Complete: Phase 7 Question Detection, Segmentation, and MCQ Option Detection
- Next: Phase 8 (Layout Detection)

Implementation is being developed one feature at a time.

Every feature is manually verified before moving to the next phase.

---

# Features

Implemented:

- PDF and Image Upload
- Workspace Lifecycle
- Upload Validation
- PDF and Image Loading
- Automatic Question Detection
- Question Segmentation
- MCQ Option Detection (3 patterns: (A), A), A.)

Planned:

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
```

# Phase 6 Status

Phase 6 OCR foundation/integration is complete.

Implemented scope:

- OCR router added
- PaddleOCR recognizer wrapper added
- Pix2Text recognizer wrapper added

Latest verification:

```text
pytest: 8 passed / 8 collected
full suite: 44 passed / 44 collected
Phase 6 committed and pushed: not yet
```

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

# Phase 7 Status

Phase 7 MCQ option detection slice is complete.

Implemented scope:

**Question Detection and Segmentation:**
- Added a minimal OCR text block data structure for question analysis
- Added basic question detection for simple patterns such as `1.`, `1)`, and `Question 1:`
- Added deterministic question segmentation that produces structured question regions

**MCQ Option Detection:**
- Implemented deterministic MCQ option detection with 3 supported patterns:
  - `(A)`, `(B)`, `(C)`, `(D)` — parentheses pattern
  - `A)`, `B)`, `C)`, `D)` — closing parenthesis pattern
  - `A. [text]`, `B. [text]`, `C. [text]` — period pattern (with text validation)
- Case normalization: lowercase options `(a)`, `(b)`, etc. are normalized to uppercase
- False-positive filtering: non-option patterns correctly ignored (numeric labels, special characters, sentence-ending periods)
- Question-region association: options automatically linked to their containing question regions
- Block-index tracking: original document block indices preserved and adjusted for traceability

Latest verification:

```text
pytest Phase 7: 24/24 passed (MCQ option detection tests)
pytest Existing: 3/3 passed (question detector/segmenter regression)
pytest Total: 27/27 passed
Manual verification: 6/6 cases passed
  ✓ Parentheses pattern (A), (B), (C), (D)
  ✓ Closing paren pattern A), B), C), D)
  ✓ Period pattern A. B. C. D. (with text)
  ✓ Lowercase normalization (a), (b), (c), (d) → A, B, C, D
  ✓ Normal text filtering (no false positives)
  ✓ Question-region association with mixed patterns
```

Phase 7 MCQ option detection is complete. Full layout detection, formula/table/diagram processing, and later structural analysis work are not yet implemented.

Next:

- Phase 7 remaining structural analysis work

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
