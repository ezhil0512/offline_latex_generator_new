"""Unit tests for Phase 15 data models.

Covers:
1.  ContentItem(kind="text") — fields and immutability.
2.  ContentItem(kind="formula") — latex field.
3.  ContentItem(kind="diagram") — diagram_id field.
4.  ContentItem default source_page / confidence values.
5.  StructuredOption — label and body.
6.  StructuredOption — empty label raises ValueError.
7.  StructuredQuestion — question_number, body, options.
8.  StructuredQuestion — empty body and options are valid.
9.  StructuredDocument — mutable container.
10. StructuredDocument — diagrams dict holds PIL images.
11. Immutability of frozen DTOs.
12. diagram_id naming convention (diagram_NNN format).
13. ContentItem bbox is a 4-tuple of floats.
14. StructuredOption body ordering is preserved.
"""

from __future__ import annotations

import dataclasses

import pytest
from PIL import Image

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_item(
    text: str = "hello",
    bbox: tuple = (0.0, 0.0, 10.0, 10.0),
    block_index: int = 0,
    source_page: int = 0,
) -> ContentItem:
    return ContentItem(
        kind="text",
        text=text,
        latex=None,
        diagram_id=None,
        bbox=bbox,
        block_index=block_index,
        source_page=source_page,
    )


def _formula_item(
    latex: str = r"x^2 + y^2 = r^2",
    bbox: tuple = (0.0, 0.0, 50.0, 20.0),
    block_index: int = 1,
    source_page: int = 0,
) -> ContentItem:
    return ContentItem(
        kind="formula",
        text=None,
        latex=latex,
        diagram_id=None,
        bbox=bbox,
        block_index=block_index,
        source_page=source_page,
    )


def _diagram_item(
    diagram_id: str = "diagram_001",
    bbox: tuple = (10.0, 10.0, 80.0, 60.0),
    source_page: int = 0,
) -> ContentItem:
    return ContentItem(
        kind="diagram",
        text=None,
        latex=None,
        diagram_id=diagram_id,
        bbox=bbox,
        block_index=None,
        source_page=source_page,
    )


def _pil_image() -> Image.Image:
    return Image.new("RGB", (50, 40), color=(100, 150, 200))


# ===========================================================================
# 1. ContentItem — text
# ===========================================================================


class TestContentItemText:

    def test_kind_is_text(self):
        item = _text_item()
        assert item.kind == "text"

    def test_text_field_preserved(self):
        item = _text_item(text="The cat sat on the mat.")
        assert item.text == "The cat sat on the mat."

    def test_latex_is_none(self):
        assert _text_item().latex is None

    def test_diagram_id_is_none(self):
        assert _text_item().diagram_id is None

    def test_block_index_preserved(self):
        item = _text_item(block_index=7)
        assert item.block_index == 7

    def test_source_page_preserved(self):
        item = _text_item(source_page=3)
        assert item.source_page == 3

    def test_bbox_preserved(self):
        bbox = (5.0, 10.0, 45.0, 30.0)
        item = _text_item(bbox=bbox)
        assert item.bbox == bbox

    def test_default_source_page_is_zero(self):
        item = ContentItem(
            kind="text",
            text="hi",
            latex=None,
            diagram_id=None,
            bbox=(0.0, 0.0, 1.0, 1.0),
            block_index=0,
        )
        assert item.source_page == 0

    def test_default_confidence_is_minus_one(self):
        item = ContentItem(
            kind="text",
            text="hi",
            latex=None,
            diagram_id=None,
            bbox=(0.0, 0.0, 1.0, 1.0),
            block_index=0,
        )
        assert item.confidence == -1.0

    def test_confidence_preserved(self):
        item = ContentItem(
            kind="text",
            text="hi",
            latex=None,
            diagram_id=None,
            bbox=(0.0, 0.0, 1.0, 1.0),
            block_index=0,
            confidence=0.97,
        )
        assert item.confidence == pytest.approx(0.97)


# ===========================================================================
# 2. ContentItem — formula
# ===========================================================================


class TestContentItemFormula:

    def test_kind_is_formula(self):
        assert _formula_item().kind == "formula"

    def test_latex_preserved(self):
        latex = r"\frac{d}{dx} e^x = e^x"
        item = _formula_item(latex=latex)
        assert item.latex == latex

    def test_text_is_none(self):
        assert _formula_item().text is None

    def test_diagram_id_is_none(self):
        assert _formula_item().diagram_id is None

    def test_source_page_preserved(self):
        item = _formula_item(source_page=2)
        assert item.source_page == 2

    def test_latex_with_greek_symbols(self):
        latex = r"\alpha + \beta = \gamma"
        item = _formula_item(latex=latex)
        assert item.latex == latex

    def test_latex_with_superscripts_and_subscripts(self):
        latex = r"x_1^2 + x_2^2"
        item = _formula_item(latex=latex)
        assert item.latex == latex


# ===========================================================================
# 3. ContentItem — diagram
# ===========================================================================


class TestContentItemDiagram:

    def test_kind_is_diagram(self):
        assert _diagram_item().kind == "diagram"

    def test_diagram_id_preserved(self):
        item = _diagram_item(diagram_id="diagram_003")
        assert item.diagram_id == "diagram_003"

    def test_text_is_none(self):
        assert _diagram_item().text is None

    def test_latex_is_none(self):
        assert _diagram_item().latex is None

    def test_block_index_is_none(self):
        assert _diagram_item().block_index is None

    def test_source_page_preserved(self):
        item = _diagram_item(source_page=1)
        assert item.source_page == 1

    def test_diagram_id_naming_convention_001(self):
        """diagram_id must follow diagram_NNN format."""
        item = _diagram_item(diagram_id="diagram_001")
        assert item.diagram_id.startswith("diagram_")
        suffix = item.diagram_id[len("diagram_"):]
        assert suffix.isdigit() and len(suffix) == 3

    def test_diagram_id_naming_convention_012(self):
        item = _diagram_item(diagram_id="diagram_012")
        assert item.diagram_id == "diagram_012"

    def test_bbox_is_four_floats(self):
        bbox = (10.5, 20.3, 80.1, 60.7)
        item = _diagram_item(bbox=bbox)
        assert len(item.bbox) == 4
        assert all(isinstance(v, float) for v in item.bbox)


# ===========================================================================
# 4. Immutability of frozen DTOs
# ===========================================================================


class TestImmutability:

    def test_content_item_text_frozen(self):
        item = _text_item()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            item.text = "mutated"  # type: ignore[misc]

    def test_content_item_kind_frozen(self):
        item = _formula_item()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            item.kind = "text"  # type: ignore[misc]

    def test_content_item_diagram_id_frozen(self):
        item = _diagram_item()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            item.diagram_id = "diagram_999"  # type: ignore[misc]

    def test_structured_option_frozen(self):
        opt = StructuredOption(label="A", body=(_text_item(),))
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            opt.label = "B"  # type: ignore[misc]

    def test_structured_question_frozen(self):
        q = StructuredQuestion(
            question_number="1",
            body=(_text_item(),),
            options=(),
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            q.question_number = "2"  # type: ignore[misc]

    def test_structured_document_is_mutable(self):
        """StructuredDocument is intentionally NOT frozen."""
        doc = StructuredDocument(pages=1)
        doc.pages = 2  # must NOT raise
        assert doc.pages == 2


# ===========================================================================
# 5. StructuredOption
# ===========================================================================


class TestStructuredOption:

    def test_label_preserved(self):
        opt = StructuredOption(label="B", body=(_text_item(),))
        assert opt.label == "B"

    def test_body_is_tuple(self):
        opt = StructuredOption(label="A", body=(_text_item(),))
        assert isinstance(opt.body, tuple)

    def test_body_ordering_preserved(self):
        item1 = _text_item(text="first", block_index=0)
        item2 = _text_item(text="second", block_index=1)
        opt = StructuredOption(label="C", body=(item1, item2))
        assert opt.body[0].text == "first"
        assert opt.body[1].text == "second"

    def test_empty_label_raises(self):
        with pytest.raises(ValueError):
            StructuredOption(label="", body=())

    def test_whitespace_only_label_raises(self):
        with pytest.raises(ValueError):
            StructuredOption(label="   ", body=())

    def test_body_with_formula(self):
        opt = StructuredOption(label="D", body=(_formula_item(),))
        assert opt.body[0].kind == "formula"

    def test_body_with_diagram(self):
        opt = StructuredOption(label="A", body=(_diagram_item(),))
        assert opt.body[0].kind == "diagram"

    def test_body_with_mixed_items(self):
        body = (_text_item(), _formula_item(), _diagram_item())
        opt = StructuredOption(label="A", body=body)
        assert len(opt.body) == 3


# ===========================================================================
# 6. StructuredQuestion
# ===========================================================================


class TestStructuredQuestion:

    def test_question_number_preserved(self):
        q = StructuredQuestion(question_number="3", body=(), options=())
        assert q.question_number == "3"

    def test_body_is_tuple(self):
        q = StructuredQuestion(question_number="1", body=(_text_item(),), options=())
        assert isinstance(q.body, tuple)

    def test_options_is_tuple(self):
        opt = StructuredOption(label="A", body=(_text_item(),))
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        assert isinstance(q.options, tuple)

    def test_empty_body_is_valid(self):
        q = StructuredQuestion(question_number="1", body=(), options=())
        assert q.body == ()

    def test_empty_options_is_valid(self):
        q = StructuredQuestion(question_number="1", body=(_text_item(),), options=())
        assert q.options == ()

    def test_body_items_accessible(self):
        item = _text_item(text="What is 2 + 2?")
        q = StructuredQuestion(question_number="1", body=(item,), options=())
        assert q.body[0].text == "What is 2 + 2?"

    def test_options_accessible(self):
        opt = StructuredOption(label="A", body=(_text_item(text="4"),))
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        assert q.options[0].label == "A"


# ===========================================================================
# 7. StructuredDocument
# ===========================================================================


class TestStructuredDocument:

    def test_pages_preserved(self):
        doc = StructuredDocument(pages=5)
        assert doc.pages == 5

    def test_default_questions_is_empty_list(self):
        doc = StructuredDocument(pages=1)
        assert doc.questions == []

    def test_default_preamble_is_empty_list(self):
        doc = StructuredDocument(pages=1)
        assert doc.preamble == []

    def test_default_diagrams_is_empty_dict(self):
        doc = StructuredDocument(pages=1)
        assert doc.diagrams == {}

    def test_diagrams_stores_pil_image(self):
        doc = StructuredDocument(pages=1)
        img = _pil_image()
        doc.diagrams["diagram_001"] = img
        assert isinstance(doc.diagrams["diagram_001"], Image.Image)

    def test_multiple_diagrams(self):
        doc = StructuredDocument(pages=1)
        doc.diagrams["diagram_001"] = _pil_image()
        doc.diagrams["diagram_002"] = _pil_image()
        assert len(doc.diagrams) == 2

    def test_questions_can_be_appended(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion(question_number="1", body=(), options=())
        doc.questions.append(q)
        assert len(doc.questions) == 1
