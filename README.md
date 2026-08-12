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
- Complete: Phase 8 Layout Detection
- Complete: Phase 9 Formula Reconstruction
- Complete: Phase 10 Offline OCR Routing
- Complete: Phase 11 Text Recognition
- Next: Phase 12 Formula Recognition

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
- Layout Detection
- Formula Reconstruction
- Offline OCR Routing
- Text Recognition

Planned:

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

Commit:

```text
27ba2b9
```

Phase 7 MCQ option detection is complete.

# Phase 8 Status

Phase 8 Layout Detection is complete.

Implemented scope:
- Data structures: `OCRBlock`, `LayoutElement`, and `LayoutRegionType` constants.
- `parse_ocr_blocks()`: Converts raw PaddleOCR nested-list output to normalized blocks.
- `detect_layout()`: Classifies blocks into structural regions.
- Deterministic classification: Identifies regions as `TEXT`, `HEADING`, `QUESTION`, `OPTION`, or `UNKNOWN`.
- Bounding-box and confidence preservation: Coordinates are normalized and tracked through to the layout elements.

Phase 7 components (`question_detector`, `question_segmenter`, `option_detector`) were intentionally NOT refactored to consume `LayoutElement` because there is no active production consumer yet. That integration belongs to the future `structurer` and `pipeline` phases.

Latest verification:

```text
pytest Phase 8 focused: 29/29 passed
pytest Full related suite: 79/79 passed
Manual verification: 9/9 cases passed
```

Future work remaining out of scope for Phase 8:
- Formula, table, and diagram processing
- Block merging (merging adjacent layout blocks of the same type)
- Pipeline orchestration
- LaTeX generation

# Phase 9 Status

Phase 9 Formula Reconstruction is complete.

Implemented scope:

- Data structure: `FormulaRegion` immutable dataclass (`block_indices`, `bbox`, `confidence`, `texts`).
- `merge_formula_fragments()`: Deterministically merges spatially adjacent formula fragments belonging to the same formula line.
- Preserved attributes: Exact bounding-box spatial union `(min_x, min_y, max_x, max_y)`, all original constituent block indices, fragment text ordering, and mean OCR confidence.
- Architecture preservation: Phase 8 contracts (`LayoutRegionType`) remained completely unchanged. Phase 7/8 components were left untouched.

Latest verification:

```text
pytest: 87/87 passed
Manual verification: 10/10 cases passed
Commit: 45764ba
```

Out of scope for Phase 9:

- Pix2Text execution
- Image cropping
- Pipeline and structurer integration
- Table and diagram recognition

# Phase 10 Status

Phase 10 Offline OCR Routing is complete.

Implemented scope:

- Region-aware OCR routing: Extended `OCRRouter` with `route_region()` method.
- Layout element dispatch: `LayoutElement` objects automatically routed to `"text"` OCR engine.
- Formula region dispatch: `FormulaRegion` objects automatically routed to `"math"` OCR engine.
- Image cropping & normalization: Floating-point bounding box coordinates are safely floor/ceil normalized and clamped to page image boundaries `(0, 0, width, height)`.
- Architecture preservation: Existing `route()` method contract and exception handling (`RecognizerError`) remain strictly preserved.

Latest verification:

```text
pytest: 96/96 passed
Manual verification: 9/9 cases passed
Commit: 21d4b39
```

Out of scope for Phase 10:

- Pipeline orchestration
- Structurer integration
- New OCR engines
- LaTeX generation
- Preview/export

# Phase 11 Status

Phase 11 Text Recognition is complete.

Implemented scope:

- Engine wrapper: `PaddleOCRRecognizer` serves as the text OCR engine wrapper for local offline recognition.
- Language & Model configuration: Configured for English (`en`) text recognition via `models.text_ocr` in `config/default.yaml`.
- OCR Router dispatch: `OCRRouter.route("text", image)` dispatches task `"text"` directly to `PaddleOCRRecognizer`.
- Region-aware text routing: `OCRRouter.route_region(page_image, element)` automatically routes `LayoutElement` objects (`TEXT`, `HEADING`, `QUESTION`, `OPTION`) to the text OCR engine.
- Image format compatibility: Internal PIL-to-NumPy array conversion (`np.array(image)`) ensures PaddleOCR compatibility while preserving PIL `Image.Image` public input signatures.
- Local architecture preservation: Processing remains 100% offline and local without external APIs.
- API Design: No new text-recognition API was introduced because no production consumer requires one, and no Python implementation changes were required for Phase 11.

Latest verification:

```text
pytest: 96/96 passed (existing test suite covering recognizers, OCR router, and region router)
Phase 10 verification: 9/9 manual test cases passed
```

Out of scope for Phase 11:

- Formula Recognition (Phase 12)
- Pipeline and structurer integration
- LaTeX generation
- Preview/export

Next:

- Phase 12 Formula Recognition

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
