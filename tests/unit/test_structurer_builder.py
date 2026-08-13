"""Unit tests for Phase 15 build_document() function.

Covers:
1.  Empty pages list → empty StructuredDocument.
2.  Single text LayoutElement (QUESTION) → one StructuredQuestion.
3.  FormulaRegion with pre-computed LaTeX → ContentItem(kind="formula").
4.  DiagramRegion → ContentItem(kind="diagram") + stable ID in diagrams dict.
5.  MCQOption → StructuredOption nested inside correct question.
6.  Document order preserved (body items in block_index order).
7.  Diagram between question text and options stays in body (not in options).
8.  Diagram inside an option body (by bbox overlap) stays in that option.
9.  Formula inside a question body.
10. Formula inside an option body.
11. Stable diagram IDs assigned in document order (diagram_001, diagram_002, …).
12. Multi-page: source_page on ContentItem matches PageElements.page_index.
13. Preamble: layout elements on a page with no question_regions → preamble.
14. Multiple questions on one page are all captured.
15. Non-MCQ question (no options) produces empty options tuple.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Union

import pytest
from PIL import Image

from offline_latex_generator.diagram_extractor import DiagramRegion
from offline_latex_generator.formula_reconstructor import FormulaRegion
from offline_latex_generator.layout_detector import LayoutElement, LayoutRegionType
from offline_latex_generator.option_detector import MCQOption

from offline_latex_generator.structurer.builder import PageElements, build_document
from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredQuestion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pil(w: int = 60, h: int = 40) -> Image.Image:
    return Image.new("RGB", (w, h), color=(180, 180, 180))


def _layout_el(
    region_type: str,
    block_index: int,
    text: str,
    bbox: tuple = (0.0, 0.0, 100.0, 20.0),
    confidence: float = 0.95,
) -> LayoutElement:
    return LayoutElement(
        region_type=region_type,
        block_indices=(block_index,),
        bbox=bbox,
        confidence=confidence,
        texts=(text,),
    )


def _formula_region(
    block_index: int,
    texts: tuple = ("x",),
    bbox: tuple = (0.0, 0.0, 50.0, 20.0),
    confidence: float = 0.90,
) -> FormulaRegion:
    return FormulaRegion(
        block_indices=(block_index,),
        bbox=bbox,
        confidence=confidence,
        texts=texts,
    )


def _diagram_region(
    bbox: tuple = (10.0, 30.0, 90.0, 70.0),
    source_page: int = 0,
) -> DiagramRegion:
    return DiagramRegion(bbox=bbox, image=_pil(), source_page=source_page)


def _mcq_option(label: str, block_index: int, text: str) -> MCQOption:
    return MCQOption(
        label=label,
        block_index=block_index,
        text=text,
        pattern_type="parentheses",
    )


def _page(
    page_index: int = 0,
    layout_elements: Sequence[Union[LayoutElement, FormulaRegion]] = (),
    diagram_regions: Sequence[DiagramRegion] = (),
    formula_latex: Dict[FormulaRegion, str] = None,
    question_regions: List[dict] = (),
) -> PageElements:
    return PageElements(
        page_index=page_index,
        layout_elements=list(layout_elements),
        diagram_regions=list(diagram_regions),
        formula_latex=formula_latex or {},
        question_regions=list(question_regions),
    )


def _q_region(
    start: int,
    end: int,
    question_text: str,
    text_blocks: List[str] = None,
    options: List[MCQOption] = None,
) -> dict:
    return {
        "start_index": start,
        "end_index": end,
        "question_text": question_text,
        "text_blocks": text_blocks or [question_text],
        "options": options or [],
    }


# ===========================================================================
# 1. Empty pages list
# ===========================================================================


def test_empty_pages_returns_empty_document():
    doc = build_document([])
    assert isinstance(doc, StructuredDocument)
    assert doc.pages == 0
    assert doc.questions == []
    assert doc.preamble == []
    assert doc.diagrams == {}


# ===========================================================================
# 2. Single text LayoutElement (QUESTION type) → one StructuredQuestion
# ===========================================================================


def test_single_question_element_creates_one_question():
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. What is gravity?")
    qr = _q_region(0, 1, "1. What is gravity?")
    page = _page(layout_elements=[el], question_regions=[qr])
    doc = build_document([page])
    assert len(doc.questions) == 1
    assert doc.questions[0].question_number == "1"


def test_question_body_contains_text_content_item():
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Describe Newton's laws.")
    qr = _q_region(0, 1, "1. Describe Newton's laws.")
    doc = build_document([_page(layout_elements=[el], question_regions=[qr])])
    body = doc.questions[0].body
    assert len(body) >= 1
    assert body[0].kind == "text"


# ===========================================================================
# 3. FormulaRegion → ContentItem(kind="formula")
# ===========================================================================


def test_formula_region_creates_formula_content_item():
    fr = _formula_region(block_index=1, texts=("x", "=", "2"))
    latex_map = {fr: r"x = 2"}
    qr = _q_region(0, 2, "1. Solve:", options=[])
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Solve:")
    page = _page(layout_elements=[el, fr], formula_latex=latex_map, question_regions=[qr])
    doc = build_document([page])
    body = doc.questions[0].body
    formula_items = [ci for ci in body if ci.kind == "formula"]
    assert len(formula_items) == 1
    assert formula_items[0].latex == r"x = 2"


def test_formula_latex_stored_unchanged():
    """Pre-computed Pix2Text LaTeX must be stored verbatim."""
    latex = r"\frac{d}{dx}\left(e^x\right) = e^x"
    fr = _formula_region(block_index=1)
    qr = _q_region(0, 2, "1. Differentiate:")
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Differentiate:")
    page = _page(
        layout_elements=[el, fr],
        formula_latex={fr: latex},
        question_regions=[qr],
    )
    doc = build_document([page])
    formula_items = [ci for ci in doc.questions[0].body if ci.kind == "formula"]
    assert formula_items[0].latex == latex


def test_formula_with_greek_symbols():
    latex = r"\alpha + \beta = \gamma"
    fr = _formula_region(block_index=1, texts=("α", "+", "β", "=", "γ"))
    qr = _q_region(0, 2, "2. Greek:")
    el = _layout_el(LayoutRegionType.QUESTION, 0, "2. Greek:")
    page = _page(
        layout_elements=[el, fr],
        formula_latex={fr: latex},
        question_regions=[qr],
    )
    doc = build_document([page])
    items = [ci for ci in doc.questions[0].body if ci.kind == "formula"]
    assert items[0].latex == latex


def test_formula_fallback_when_not_in_latex_map():
    """When a FormulaRegion has no entry in formula_latex, texts are joined."""
    fr = _formula_region(block_index=1, texts=("x", "=", "5"))
    qr = _q_region(0, 2, "1. Solve:")
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Solve:")
    # Empty formula_latex map → fallback to texts join
    page = _page(layout_elements=[el, fr], formula_latex={}, question_regions=[qr])
    doc = build_document([page])
    items = [ci for ci in doc.questions[0].body if ci.kind == "formula"]
    assert len(items) == 1
    assert "x" in items[0].latex or "5" in items[0].latex


# ===========================================================================
# 4. DiagramRegion → ContentItem(kind="diagram") + stable ID
# ===========================================================================


def test_diagram_creates_diagram_content_item():
    dr = _diagram_region(bbox=(10.0, 25.0, 90.0, 60.0))
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. See diagram:")
    qr = _q_region(0, 1, "1. See diagram:")
    page = _page(layout_elements=[el], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    all_items = list(doc.questions[0].body)
    diagram_items = [ci for ci in all_items if ci.kind == "diagram"]
    assert len(diagram_items) == 1
    assert diagram_items[0].diagram_id is not None


def test_diagram_id_stored_in_diagrams_dict():
    dr = _diagram_region()
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q:")
    qr = _q_region(0, 1, "1. Q:")
    page = _page(layout_elements=[el], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    diagram_items = [ci for ci in doc.questions[0].body if ci.kind == "diagram"]
    d_id = diagram_items[0].diagram_id
    assert d_id in doc.diagrams
    assert isinstance(doc.diagrams[d_id], Image.Image)


def test_diagram_pil_image_in_memory_not_in_content_item():
    """The ContentItem must hold only the ID, never the PIL image."""
    dr = _diagram_region()
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q:")
    qr = _q_region(0, 1, "1. Q:")
    page = _page(layout_elements=[el], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    for item in doc.questions[0].body:
        assert not isinstance(item, Image.Image)
        if item.kind == "diagram":
            assert isinstance(item.diagram_id, str)
            # No PIL image attribute on ContentItem
            assert not hasattr(item, "image") or not isinstance(
                getattr(item, "image", None), Image.Image
            )


# ===========================================================================
# 5. MCQOption → StructuredOption inside correct question
# ===========================================================================


def test_mcq_options_become_structured_options():
    el_q = _layout_el(LayoutRegionType.QUESTION, 0, "1. Which?", bbox=(0.0, 0.0, 200.0, 20.0))
    el_a = _layout_el(LayoutRegionType.OPTION, 1, "(A) First", bbox=(0.0, 25.0, 200.0, 40.0))
    el_b = _layout_el(LayoutRegionType.OPTION, 2, "(B) Second", bbox=(0.0, 45.0, 200.0, 60.0))
    opt_a = _mcq_option("A", 1, "(A) First")
    opt_b = _mcq_option("B", 2, "(B) Second")
    qr = _q_region(0, 3, "1. Which?", options=[opt_a, opt_b])
    page = _page(layout_elements=[el_q, el_a, el_b], question_regions=[qr])
    doc = build_document([page])
    q = doc.questions[0]
    assert len(q.options) == 2
    labels = [o.label for o in q.options]
    assert "A" in labels
    assert "B" in labels


def test_option_body_contains_text_item():
    el_q = _layout_el(LayoutRegionType.QUESTION, 0, "1. Which?")
    el_a = _layout_el(LayoutRegionType.OPTION, 1, "(A) Yes", bbox=(0.0, 25.0, 200.0, 40.0))
    opt_a = _mcq_option("A", 1, "(A) Yes")
    qr = _q_region(0, 2, "1. Which?", options=[opt_a])
    page = _page(layout_elements=[el_q, el_a], question_regions=[qr])
    doc = build_document([page])
    option = doc.questions[0].options[0]
    assert len(option.body) >= 1
    assert option.body[0].kind == "text"


# ===========================================================================
# 6. Document order preserved
# ===========================================================================


def test_body_items_in_block_index_order():
    """Items with lower block_index must appear first in body."""
    el1 = _layout_el(LayoutRegionType.QUESTION, 0, "1. First part", bbox=(0.0, 0.0, 200.0, 20.0))
    el2 = _layout_el(LayoutRegionType.TEXT, 1, "Second part", bbox=(0.0, 25.0, 200.0, 40.0))
    qr = _q_region(0, 2, "1. First part")
    page = _page(layout_elements=[el1, el2], question_regions=[qr])
    doc = build_document([page])
    body = doc.questions[0].body
    non_diagram = [ci for ci in body if ci.kind != "diagram"]
    indices = [ci.block_index for ci in non_diagram if ci.block_index is not None]
    assert indices == sorted(indices)


# ===========================================================================
# 7. Diagram between question text and options → stays in body
# ===========================================================================


def test_diagram_between_question_and_options_is_in_body():
    """A diagram placed between the question stem and the options must be
    in StructuredQuestion.body, not inside any StructuredOption."""
    el_q = _layout_el(
        LayoutRegionType.QUESTION, 0, "1. Circuit?", bbox=(0.0, 0.0, 200.0, 20.0)
    )
    # Diagram bbox sits between question text (y=0..20) and options (y=70..100)
    dr = _diagram_region(bbox=(10.0, 25.0, 90.0, 65.0))
    el_a = _layout_el(LayoutRegionType.OPTION, 1, "(A) Resistor", bbox=(0.0, 70.0, 200.0, 85.0))
    el_b = _layout_el(LayoutRegionType.OPTION, 2, "(B) Capacitor", bbox=(0.0, 90.0, 200.0, 105.0))
    opt_a = _mcq_option("A", 1, "(A) Resistor")
    opt_b = _mcq_option("B", 2, "(B) Capacitor")
    qr = _q_region(0, 3, "1. Circuit?", options=[opt_a, opt_b])
    page = _page(layout_elements=[el_q, el_a, el_b], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    q = doc.questions[0]
    body_diagram_ids = {ci.diagram_id for ci in q.body if ci.kind == "diagram"}
    option_diagram_ids = {
        ci.diagram_id
        for opt in q.options
        for ci in opt.body
        if ci.kind == "diagram"
    }
    assert len(body_diagram_ids) == 1
    assert len(option_diagram_ids) == 0


# ===========================================================================
# 8. Diagram inside an option → stays in that option's body
# ===========================================================================


def test_diagram_inside_option_stays_in_option_body():
    """A diagram whose bbox overlaps an option's bbox must appear inside
    that StructuredOption.body."""
    el_q = _layout_el(
        LayoutRegionType.QUESTION, 0, "1. Choose:", bbox=(0.0, 0.0, 200.0, 20.0)
    )
    el_a = _layout_el(
        LayoutRegionType.OPTION, 1, "(A) See below:", bbox=(0.0, 30.0, 200.0, 50.0)
    )
    # Diagram inside option A's vertical band (y=30..50)
    dr = _diagram_region(bbox=(10.0, 32.0, 90.0, 48.0))
    el_b = _layout_el(
        LayoutRegionType.OPTION, 2, "(B) None", bbox=(0.0, 60.0, 200.0, 75.0)
    )
    opt_a = _mcq_option("A", 1, "(A) See below:")
    opt_b = _mcq_option("B", 2, "(B) None")
    qr = _q_region(0, 3, "1. Choose?", options=[opt_a, opt_b])
    page = _page(layout_elements=[el_q, el_a, el_b], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    q = doc.questions[0]
    opt_a_result = next(o for o in q.options if o.label == "A")
    opt_b_result = next(o for o in q.options if o.label == "B")
    a_diagrams = [ci for ci in opt_a_result.body if ci.kind == "diagram"]
    b_diagrams = [ci for ci in opt_b_result.body if ci.kind == "diagram"]
    body_diagrams = [ci for ci in q.body if ci.kind == "diagram"]
    assert len(a_diagrams) == 1
    assert len(b_diagrams) == 0
    assert len(body_diagrams) == 0


# ===========================================================================
# 9. Formula inside question body
# ===========================================================================


def test_formula_inside_question_body():
    fr = _formula_region(block_index=1, bbox=(0.0, 25.0, 100.0, 40.0))
    el_q = _layout_el(LayoutRegionType.QUESTION, 0, "1. Evaluate:", bbox=(0.0, 0.0, 200.0, 20.0))
    latex_map = {fr: r"E = mc^2"}
    qr = _q_region(0, 2, "1. Evaluate:")
    page = _page(layout_elements=[el_q, fr], formula_latex=latex_map, question_regions=[qr])
    doc = build_document([page])
    body = doc.questions[0].body
    formula_items = [ci for ci in body if ci.kind == "formula"]
    assert len(formula_items) == 1
    assert formula_items[0].latex == r"E = mc^2"


# ===========================================================================
# 10. Formula inside option body
# ===========================================================================


def test_formula_in_option_reflected_in_option_body_text():
    """Options text containing formula indicators is stored in option text."""
    el_q = _layout_el(LayoutRegionType.QUESTION, 0, "1. Solve:", bbox=(0.0, 0.0, 200.0, 20.0))
    el_a = _layout_el(
        LayoutRegionType.OPTION, 1, r"(A) x^2", bbox=(0.0, 30.0, 200.0, 45.0)
    )
    opt_a = _mcq_option("A", 1, r"(A) x^2")
    qr = _q_region(0, 2, "1. Solve:", options=[opt_a])
    page = _page(layout_elements=[el_q, el_a], question_regions=[qr])
    doc = build_document([page])
    opt = doc.questions[0].options[0]
    assert opt.label == "A"
    assert opt.body[0].kind == "text"
    assert r"x^2" in opt.body[0].text


# ===========================================================================
# 11. Stable diagram IDs in document order
# ===========================================================================


def test_diagram_ids_are_stable_and_sequential():
    """Two diagrams on the same page get diagram_001 and diagram_002."""
    dr1 = _diagram_region(bbox=(0.0, 20.0, 100.0, 50.0))
    dr2 = _diagram_region(bbox=(0.0, 60.0, 100.0, 90.0))
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q:", bbox=(0.0, 0.0, 200.0, 15.0))
    qr = _q_region(0, 1, "1. Q:")
    page = _page(layout_elements=[el], diagram_regions=[dr1, dr2], question_regions=[qr])
    doc = build_document([page])
    all_diagram_ids = list(doc.diagrams.keys())
    assert "diagram_001" in all_diagram_ids
    assert "diagram_002" in all_diagram_ids


def test_diagram_ids_across_pages_are_sequential():
    """Diagram IDs must be unique and sequential across pages."""
    el_p0 = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q1:")
    qr_p0 = _q_region(0, 1, "1. Q1:")
    dr_p0 = _diagram_region(bbox=(0.0, 25.0, 100.0, 55.0))

    el_p1 = _layout_el(LayoutRegionType.QUESTION, 0, "2. Q2:")
    qr_p1 = _q_region(0, 1, "2. Q2:")
    dr_p1 = _diagram_region(bbox=(0.0, 25.0, 100.0, 55.0), source_page=1)

    page0 = _page(page_index=0, layout_elements=[el_p0], diagram_regions=[dr_p0], question_regions=[qr_p0])
    page1 = _page(page_index=1, layout_elements=[el_p1], diagram_regions=[dr_p1], question_regions=[qr_p1])

    doc = build_document([page0, page1])
    ids = sorted(doc.diagrams.keys())
    assert ids == ["diagram_001", "diagram_002"]


def test_diagram_id_format_three_digit_padded():
    dr = _diagram_region()
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q:")
    qr = _q_region(0, 1, "1. Q:")
    page = _page(layout_elements=[el], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    for d_id in doc.diagrams:
        assert d_id.startswith("diagram_")
        suffix = d_id[len("diagram_"):]
        assert len(suffix) == 3 and suffix.isdigit()


# ===========================================================================
# 12. Multi-page: source_page on ContentItem
# ===========================================================================


def test_source_page_set_correctly_on_content_items():
    el_p0 = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q1:")
    qr_p0 = _q_region(0, 1, "1. Q1:")
    el_p1 = _layout_el(LayoutRegionType.QUESTION, 0, "2. Q2:")
    qr_p1 = _q_region(0, 1, "2. Q2:")

    page0 = _page(page_index=0, layout_elements=[el_p0], question_regions=[qr_p0])
    page1 = _page(page_index=1, layout_elements=[el_p1], question_regions=[qr_p1])

    doc = build_document([page0, page1])
    assert len(doc.questions) == 2
    # First question's body items should have source_page=0
    for ci in doc.questions[0].body:
        assert ci.source_page == 0
    # Second question's body items should have source_page=1
    for ci in doc.questions[1].body:
        assert ci.source_page == 1


def test_diagram_source_page_set_correctly():
    el_p1 = _layout_el(LayoutRegionType.QUESTION, 0, "1. Q:", bbox=(0.0, 0.0, 200.0, 20.0))
    dr = _diagram_region(bbox=(0.0, 25.0, 100.0, 55.0), source_page=1)
    qr = _q_region(0, 1, "1. Q:")
    page = _page(page_index=1, layout_elements=[el_p1], diagram_regions=[dr], question_regions=[qr])
    doc = build_document([page])
    diagram_items = [ci for ci in doc.questions[0].body if ci.kind == "diagram"]
    assert len(diagram_items) == 1
    assert diagram_items[0].source_page == 1


# ===========================================================================
# 13. Preamble — content before first question
# ===========================================================================


def test_elements_on_page_with_no_questions_go_to_preamble():
    el = _layout_el(LayoutRegionType.TEXT, 0, "PHYSICS EXAM 2024")
    page = _page(layout_elements=[el], question_regions=[])
    doc = build_document([page])
    assert len(doc.questions) == 0
    assert len(doc.preamble) >= 1
    assert doc.preamble[0].kind == "text"


def test_diagram_with_no_questions_goes_to_preamble():
    dr = _diagram_region()
    page = _page(diagram_regions=[dr], question_regions=[])
    doc = build_document([page])
    assert len(doc.questions) == 0
    assert len(doc.preamble) >= 1
    preamble_diagrams = [ci for ci in doc.preamble if ci.kind == "diagram"]
    assert len(preamble_diagrams) == 1


# ===========================================================================
# 14. Multiple questions on one page
# ===========================================================================


def test_multiple_questions_on_one_page():
    el_q1 = _layout_el(LayoutRegionType.QUESTION, 0, "1. First?", bbox=(0.0, 0.0, 200.0, 20.0))
    el_q2 = _layout_el(LayoutRegionType.QUESTION, 1, "2. Second?", bbox=(0.0, 50.0, 200.0, 70.0))
    qr1 = _q_region(0, 1, "1. First?")
    qr2 = _q_region(1, 2, "2. Second?")
    page = _page(layout_elements=[el_q1, el_q2], question_regions=[qr1, qr2])
    doc = build_document([page])
    assert len(doc.questions) == 2
    assert doc.questions[0].question_number == "1"
    assert doc.questions[1].question_number == "2"


# ===========================================================================
# 15. Non-MCQ question — empty options
# ===========================================================================


def test_non_mcq_question_has_empty_options():
    el = _layout_el(LayoutRegionType.QUESTION, 0, "1. Explain Newton's 3rd law.")
    qr = _q_region(0, 1, "1. Explain Newton's 3rd law.", options=[])
    doc = build_document([_page(layout_elements=[el], question_regions=[qr])])
    assert doc.questions[0].options == ()
