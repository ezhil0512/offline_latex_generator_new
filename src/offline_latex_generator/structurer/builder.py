"""Structured document assembly — Phase 15.

Provides :func:`build_document`, a pure function that assembles the outputs
of Phases 7–14 into a single :class:`StructuredDocument`.

Design constraints
------------------
- Pure function: no file I/O, no OCR calls, no side effects.
- Does NOT call OCRRouter or any recognizer internally.
- Formula LaTeX must be supplied by the caller as a pre-computed mapping
  ``{FormulaRegion → str}`` (the result of calling ``OCRRouter.route_region``
  for each formula before invoking the builder).
- Does NOT modify any Phase 7–14 DTO.
- ``source_page`` is carried as external context supplied by the caller;
  it is not read from frozen DTOs.

Input model
-----------
The builder accepts a list of :class:`PageElements` — one entry per page —
where each entry groups the :class:`LayoutElement` / :class:`FormulaRegion`
objects produced for that page together with any :class:`DiagramRegion`
objects and the pre-computed formula-LaTeX mapping for that page.

Assembly rules
--------------
1. All elements across all pages are sorted by ``(source_page, block_index)``.
2. Elements whose ``block_index`` falls inside a question's
   ``[start_index, end_index)`` range are attached to that question.
3. Within a question, option blocks (OPTION region_type or MCQOption)
   populate :class:`StructuredOption` objects; all other blocks go into
   the question ``body``.
4. :class:`DiagramRegion` objects are matched to questions by ``bbox``
   proximity on the same source page using vertical overlap with the
   question's block range.  A diagram that cannot be matched to any
   question goes into ``StructuredDocument.preamble``.
5. Within ``body`` and ``StructuredOption.body`` lists, items are ordered
   by their ``block_index`` (or diagram insertion order when no block_index
   is available).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from PIL import Image

from offline_latex_generator.diagram_extractor import DiagramRegion
from offline_latex_generator.formula_reconstructor import FormulaRegion
from offline_latex_generator.layout_detector import LayoutElement, LayoutRegionType
from offline_latex_generator.option_detector import MCQOption

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)


# ---------------------------------------------------------------------------
# Public input container
# ---------------------------------------------------------------------------


@dataclass
class PageElements:
    """Groups all recognised elements for one document page.

    Attributes
    ----------
    page_index:
        Zero-based page number.
    layout_elements:
        Ordered sequence of :class:`LayoutElement` objects from
        ``detect_layout()`` (Phase 8), possibly interleaved with
        :class:`FormulaRegion` objects from ``merge_formula_fragments()``
        (Phase 9).  The sequence may contain either type.
    diagram_regions:
        :class:`DiagramRegion` objects extracted from this page (Phase 14).
    formula_latex:
        Pre-computed mapping ``{FormulaRegion → latex_string}``.  Each
        :class:`FormulaRegion` that appears in *layout_elements* should
        have an entry here.  Missing entries fall back to joining
        ``FormulaRegion.texts`` with a space.
    question_regions:
        Output of ``segment_questions()`` (Phase 7) — a list of dicts with
        keys ``start_index``, ``end_index``, ``question_text``, and
        optionally ``options`` (list of :class:`MCQOption`).
    """

    page_index: int
    layout_elements: Sequence[Union[LayoutElement, FormulaRegion]]
    diagram_regions: Sequence[DiagramRegion]
    formula_latex: Dict[FormulaRegion, str]
    question_regions: List[dict]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DIAGRAM_ID_FMT = "diagram_{:03d}"


def _next_diagram_id(counter: itertools.count) -> str:  # type: ignore[type-arg]
    return _DIAGRAM_ID_FMT.format(next(counter))


def _element_block_index(el: Union[LayoutElement, FormulaRegion]) -> int:
    """Return the first (lowest) block index for an element."""
    return el.block_indices[0] if el.block_indices else 0


def _make_text_item(
    el: LayoutElement,
    source_page: int,
) -> ContentItem:
    """Convert a LayoutElement to a text ContentItem."""
    text = " ".join(el.texts).strip()
    return ContentItem(
        kind="text",
        text=text,
        latex=None,
        diagram_id=None,
        bbox=el.bbox,
        block_index=_element_block_index(el),
        source_page=source_page,
        confidence=el.confidence,
    )


def _make_formula_item(
    el: FormulaRegion,
    latex: str,
    source_page: int,
) -> ContentItem:
    """Convert a FormulaRegion + pre-computed LaTeX to a formula ContentItem."""
    return ContentItem(
        kind="formula",
        text=None,
        latex=latex,
        diagram_id=None,
        bbox=el.bbox,
        block_index=_element_block_index(el),
        source_page=source_page,
        confidence=el.confidence,
    )


def _make_diagram_item(
    diagram_id: str,
    bbox: Tuple[float, float, float, float],
    source_page: int,
) -> ContentItem:
    """Build a diagram ContentItem with a stable ID reference."""
    return ContentItem(
        kind="diagram",
        text=None,
        latex=None,
        diagram_id=diagram_id,
        bbox=bbox,
        block_index=None,
        source_page=source_page,
        confidence=-1.0,
    )


def _element_to_item(
    el: Union[LayoutElement, FormulaRegion],
    formula_latex: Dict[FormulaRegion, str],
    source_page: int,
) -> Optional[ContentItem]:
    """Convert a LayoutElement or FormulaRegion to a ContentItem.

    Returns ``None`` for OPTION-typed LayoutElements because those are
    handled separately via the question_regions dict.
    """
    if isinstance(el, FormulaRegion):
        latex = formula_latex.get(el) or " ".join(el.texts).strip()
        return _make_formula_item(el, latex, source_page)

    # LayoutElement
    if el.region_type == LayoutRegionType.OPTION:
        # Options are assembled from the MCQOption list, not here
        return None

    return _make_text_item(el, source_page)


def _block_index_of_option(opt: MCQOption) -> int:
    return opt.block_index


def _bbox_for_block(
    elements: Sequence[Union[LayoutElement, FormulaRegion]],
    block_index: int,
) -> Optional[Tuple[float, float, float, float]]:
    """Look up the bbox of the element whose block_indices contains block_index."""
    for el in elements:
        if block_index in el.block_indices:
            return el.bbox
    return None


def _option_content_item(
    opt: MCQOption,
    all_elements: Sequence[Union[LayoutElement, FormulaRegion]],
    formula_latex: Dict[FormulaRegion, str],
    source_page: int,
) -> ContentItem:
    """Build a text ContentItem for one MCQ option label + text."""
    bbox = _bbox_for_block(all_elements, opt.block_index) or (0.0, 0.0, 0.0, 0.0)
    return ContentItem(
        kind="text",
        text=opt.text,
        latex=None,
        diagram_id=None,
        bbox=bbox,
        block_index=opt.block_index,
        source_page=source_page,
        confidence=-1.0,
    )


def _vertical_midpoint(bbox: Tuple[float, float, float, float]) -> float:
    return (bbox[1] + bbox[3]) / 2.0


def _question_bbox(
    start_index: int,
    end_index: int,
    elements: Sequence[Union[LayoutElement, FormulaRegion]],
) -> Optional[Tuple[float, float, float, float]]:
    """Return the bounding box covering elements in [start_index, end_index)."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for el in elements:
        if any(start_index <= bi < end_index for bi in el.block_indices):
            xs0.append(el.bbox[0])
            ys0.append(el.bbox[1])
            xs1.append(el.bbox[2])
            ys1.append(el.bbox[3])
    if not xs0:
        return None
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def _assign_diagrams_to_questions(
    diagram_regions: Sequence[DiagramRegion],
    question_bbox_map: Dict[int, Optional[Tuple[float, float, float, float]]],
    source_page: int,
    diagram_counter: "itertools.count[int]",
    diagrams_dict: Dict[str, Image.Image],
) -> Dict[int, List[ContentItem]]:
    """Assign each diagram on this page to the nearest question (by bbox).

    Returns a mapping ``{question_list_index → [ContentItem, ...]}``.
    Diagrams that do not fall within any question's vertical span go to
    index ``-1`` (preamble / free-standing).
    """
    result: Dict[int, List[ContentItem]] = {}

    for dr in diagram_regions:
        diagram_id = _next_diagram_id(diagram_counter)
        diagrams_dict[diagram_id] = dr.image
        item = _make_diagram_item(diagram_id, dr.bbox, source_page)

        dr_mid_y = _vertical_midpoint(dr.bbox)

        best_q_idx: Optional[int] = None
        best_distance = float("inf")

        for q_idx, q_bbox in question_bbox_map.items():
            if q_bbox is None:
                continue
            q_y0, q_y1 = q_bbox[1], q_bbox[3]
            # Inside or closest
            if q_y0 <= dr_mid_y <= q_y1:
                best_q_idx = q_idx
                best_distance = 0.0
                break
            dist = min(abs(dr_mid_y - q_y0), abs(dr_mid_y - q_y1))
            if dist < best_distance:
                best_distance = dist
                best_q_idx = q_idx

        key = best_q_idx if best_q_idx is not None else -1
        result.setdefault(key, []).append(item)

    return result


def _build_option(
    opt: MCQOption,
    opt_diagram_items: List[ContentItem],
    all_elements: Sequence[Union[LayoutElement, FormulaRegion]],
    formula_latex: Dict[FormulaRegion, str],
    source_page: int,
) -> StructuredOption:
    """Build one StructuredOption from an MCQOption + any diagram items."""
    base_item = _option_content_item(opt, all_elements, formula_latex, source_page)
    # Merge diagram items that belong inside this option's bbox
    body_items: List[ContentItem] = [base_item]
    for d_item in opt_diagram_items:
        body_items.append(d_item)
    # Sort by block_index (None last)
    body_items.sort(key=lambda ci: ci.block_index if ci.block_index is not None else 999999)
    return StructuredOption(
        label=opt.label,
        body=tuple(body_items),
    )


def _parse_question_number(question_text: str, fallback: int) -> str:
    """Extract a question number string from the question stem text."""
    import re
    m = re.match(r"^\s*(\d+)\s*[.)\-:]", question_text)
    if m:
        return m.group(1)
    m2 = re.match(r"^\s*[Qq]uestion\s+(\d+)", question_text, re.IGNORECASE)
    if m2:
        return m2.group(1)
    return str(fallback)


def _strip_question_prefix(text: str) -> str:
    """Remove leading question number prefix (e.g. '1.', '26.', '26.A', 'Question 1:') from text."""
    if not text:
        return text
    import re
    pattern = r"^\s*(?:\d+\s*[.)\-:]|[Qq]uestion\s+\d+\s*[:\-]?)\s*"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_document(
    pages: Sequence[PageElements],
) -> StructuredDocument:
    """Assemble a :class:`StructuredDocument` from per-page recognition outputs.

    This is a **pure function** — it performs no file I/O, no OCR calls, and
    has no side effects beyond constructing and returning the document.

    Args:
        pages: Ordered sequence of :class:`PageElements`, one per page.
               The caller is responsible for pre-computing ``formula_latex``
               by calling ``OCRRouter.route_region()`` for each
               :class:`FormulaRegion` before invoking this function.

    Returns:
        :class:`StructuredDocument` containing all questions, preamble
        content, and an in-memory diagram registry.
    """
    total_pages = len(pages)
    all_questions: List[StructuredQuestion] = []
    preamble: List[ContentItem] = []
    diagrams: Dict[str, Image.Image] = {}
    diagram_counter: "itertools.count[int]" = itertools.count(1)

    question_ordinal = 0  # global question counter for fallback numbering

    for page_el in pages:
        source_page = page_el.page_index
        elements = page_el.layout_elements
        formula_latex = page_el.formula_latex
        question_regions = page_el.question_regions

        # --- Build per-question bbox map for diagram assignment ---
        q_bbox_map: Dict[int, Optional[Tuple[float, float, float, float]]] = {}
        for q_idx, qr in enumerate(question_regions):
            q_bbox_map[q_idx] = _question_bbox(
                qr["start_index"], qr["end_index"], elements
            )

        # --- Assign diagrams to questions (or preamble) ---
        diagram_assignments = _assign_diagrams_to_questions(
            page_el.diagram_regions,
            q_bbox_map,
            source_page,
            diagram_counter,
            diagrams,
        )

        # --- Handle preamble (diagrams before first question) ---
        for d_item in diagram_assignments.get(-1, []):
            preamble.append(d_item)

        # --- Build StructuredQuestion for each question region ---
        if not question_regions:
            # No questions on this page — all layout elements go to preamble
            for el in elements:
                item = _element_to_item(el, formula_latex, source_page)
                if item is not None:
                    preamble.append(item)
            continue

        for q_idx, qr in enumerate(question_regions):
            question_ordinal += 1
            start_idx: int = qr["start_index"]
            end_idx: int = qr["end_index"]
            question_text: str = qr.get("question_text", "")
            mcq_options: List[MCQOption] = qr.get("options", [])

            q_number = _parse_question_number(question_text, question_ordinal)

            # Collect option block indices for exclusion from body
            option_block_indices = set()
            for opt in mcq_options:
                indices = getattr(opt, "block_indices", ()) or (opt.block_index,)
                option_block_indices.update(indices)

            # --- Build body ContentItems ---
            body_items: List[ContentItem] = []

            for el in elements:
                # Only elements whose block indices fall in this question's range
                el_indices = set(el.block_indices)
                if not el_indices.intersection(range(start_idx, end_idx)):
                    continue
                # Skip pure option blocks (they'll be in StructuredOption)
                if el_indices.issubset(option_block_indices):
                    continue
                item = _element_to_item(el, formula_latex, source_page)
                if item is not None:
                    body_items.append(item)

            # Attach diagrams assigned to this question into body
            for d_item in diagram_assignments.get(q_idx, []):
                body_items.append(d_item)

            # Sort body by block_index (diagrams with None go last within body)
            body_items.sort(
                key=lambda ci: ci.block_index if ci.block_index is not None else 999999
            )

            # Strip leading question prefix from the first text item in question stem
            if body_items and body_items[0].kind == "text" and body_items[0].text:
                first_item = body_items[0]
                stripped_text = _strip_question_prefix(first_item.text)
                body_items[0] = ContentItem(
                    kind=first_item.kind,
                    text=stripped_text,
                    latex=first_item.latex,
                    diagram_id=first_item.diagram_id,
                    bbox=first_item.bbox,
                    block_index=first_item.block_index,
                    source_page=first_item.source_page,
                    confidence=first_item.confidence,
                )

            # --- Build StructuredOption list ---
            structured_options: List[StructuredOption] = []
            for opt in sorted(mcq_options, key=lambda o: o.label):
                # Diagrams inside an option: approximate by checking if the
                # diagram's bbox midpoint Y falls between this option's bbox
                # and the next option's bbox.
                opt_bbox = _bbox_for_block(elements, opt.block_index) or (
                    0.0, 0.0, 0.0, 0.0
                )
                # Find option-specific diagrams (those inside the option bbox)
                opt_diagram_items: List[ContentItem] = []
                remaining_body: List[ContentItem] = []
                for item in body_items:
                    if item.kind == "diagram" and item.diagram_id is not None:
                        d_mid_y = _vertical_midpoint(item.bbox)
                        if opt_bbox[1] <= d_mid_y <= opt_bbox[3]:
                            opt_diagram_items.append(item)
                            continue
                    remaining_body.append(item)
                body_items = remaining_body

                s_opt = _build_option(
                    opt, opt_diagram_items, elements, formula_latex, source_page
                )
                structured_options.append(s_opt)

            # Sort options by label
            structured_options.sort(key=lambda o: o.label)

            sq = StructuredQuestion(
                question_number=q_number,
                body=tuple(body_items),
                options=tuple(structured_options),
            )
            all_questions.append(sq)

    doc = StructuredDocument(
        pages=total_pages,
        questions=all_questions,
        preamble=preamble,
        diagrams=diagrams,
    )
    return doc


__all__ = [
    "PageElements",
    "build_document",
]
