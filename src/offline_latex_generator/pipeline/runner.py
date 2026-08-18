"""Pipeline execution orchestrator — Phase 5 to 15.

Connects document loading, image preprocessing, OCR routing, layout analysis,
question detection/segmentation, MCQ option detection, formula reconstruction,
diagram extraction, and document structuring into an end-to-end processing pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from offline_latex_generator.diagram_extractor import DiagramRegion
from offline_latex_generator.formula_reconstructor import merge_formula_fragments
from offline_latex_generator.layout_detector import (
    OCRBlock,
    detect_layout,
    parse_ocr_blocks,
)
from offline_latex_generator.loader import ImageLoader, PDFLoader
from offline_latex_generator.ocr_router import OCRRouter
from offline_latex_generator.option_detector import detect_mcq_options
from offline_latex_generator.preprocessor import ImagePreprocessor
from offline_latex_generator.question_detector import OCRTextBlock
from offline_latex_generator.question_segmenter import segment_questions
from offline_latex_generator.structurer import (
    PageElements,
    StructuredDocument,
    build_document,
)
from offline_latex_generator.utils.logger import logger


def run_pipeline(file_path: Union[str, Path]) -> StructuredDocument:
    """Execute the offline document processing pipeline on an uploaded file.

    Parameters
    ----------
    file_path:
        Path to the uploaded PDF or image file inside the job workspace.

    Returns
    -------
    StructuredDocument
        The canonical Phase 15 intermediate representation.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file '{path.name}' does not exist.")

    ext = path.suffix.lower()

    # 1. Document Loading (Phase 4)
    if ext == ".pdf":
        images = PDFLoader().load(path)
    else:
        images = ImageLoader().load(path)

    if not images:
        return StructuredDocument(pages=0)

    # 2. Per-page processing loop (Phases 5–14)
    preprocessor = ImagePreprocessor()
    router = OCRRouter()
    page_elements_list: List[PageElements] = []

    for page_idx, raw_img in enumerate(images):
        # Phase 5: Image Preprocessing
        processed_img = preprocessor.process(raw_img)

        # Phase 6 & 8: OCR Layout detection
        ocr_blocks: List[OCRBlock] = []
        try:
            raw_ocr = router.route("layout", processed_img)
            ocr_blocks = parse_ocr_blocks(raw_ocr)
        except Exception as exc:
            logger.warning(
                f"Layout OCR fallback for page {page_idx}: {exc}"
            )
            ocr_blocks = []

        layout_elements = detect_layout(ocr_blocks)

        # Phase 7: Question Detection & Segmentation
        text_blocks = [OCRTextBlock(text=b.text) for b in ocr_blocks]
        q_regions = segment_questions(text_blocks)

        # Phase 7: MCQ Option Detection
        mcq_options = detect_mcq_options(ocr_blocks)
        for q in q_regions:
            q_start = q["start_index"]
            q_end = q["end_index"]
            matched_opts = [
                opt for opt in mcq_options if q_start <= opt.block_index < q_end
            ]
            if matched_opts:
                q["options"] = matched_opts

        # Phase 9 & 12: Formula Reconstruction & Math OCR Routing
        formula_regions = merge_formula_fragments(ocr_blocks)
        formula_latex_map = {}
        for f_region in formula_regions:
            try:
                latex_res = router.route_region(processed_img, f_region)
                formula_latex_map[f_region] = (
                    str(latex_res) if latex_res else ""
                )
            except Exception:
                formula_latex_map[f_region] = " ".join(f_region.texts)

        # Phase 14: Diagram Extraction
        diagram_regions: List[DiagramRegion] = []

        page_elements_list.append(
            PageElements(
                page_index=page_idx,
                layout_elements=layout_elements,
                diagram_regions=diagram_regions,
                formula_latex=formula_latex_map,
                question_regions=q_regions,
            )
        )

    # Phase 15: Structured JSON Generation
    return build_document(page_elements_list)


__all__ = ["run_pipeline"]
