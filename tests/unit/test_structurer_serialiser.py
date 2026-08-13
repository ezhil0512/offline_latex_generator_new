"""Unit tests for Phase 15 serialiser: document_to_dict() and document_to_json().

Covers:
1.  document_to_dict() output is json.dumps()-able (no PIL objects).
2.  Diagram entries in JSON contain only diagram_id strings (no PIL).
3.  All required keys present: kind, text, latex, diagram_id, bbox, source_page.
4.  Round-trip: json.loads(document_to_json(doc)) succeeds.
5.  questions[0].body[0].kind == "text" survives round-trip.
6.  Empty document serialises correctly.
7.  "diagrams" key is a sorted list of strings.
8.  Formula ContentItem serialises with latex field set.
9.  Diagram ContentItem serialises with diagram_id set and no PIL image.
10. Text ContentItem serialises with text field set.
11. Options serialise with label and body.
12. document_to_json returns a valid UTF-8 string.
13. Multiple diagrams in sorted order in "diagrams" key.
14. Preamble items are serialised.
15. Nested option body items are serialised.
"""

from __future__ import annotations

import json
from typing import Dict

import pytest
from PIL import Image

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)
from offline_latex_generator.structurer.serialiser import (
    document_to_dict,
    document_to_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pil() -> Image.Image:
    return Image.new("RGB", (30, 20))


def _text_item(
    text: str = "Sample text",
    bbox: tuple = (0.0, 0.0, 10.0, 10.0),
    block_index: int = 0,
    source_page: int = 0,
    confidence: float = 0.95,
) -> ContentItem:
    return ContentItem(
        kind="text",
        text=text,
        latex=None,
        diagram_id=None,
        bbox=bbox,
        block_index=block_index,
        source_page=source_page,
        confidence=confidence,
    )


def _formula_item(
    latex: str = r"x^2 + y^2",
    source_page: int = 0,
) -> ContentItem:
    return ContentItem(
        kind="formula",
        text=None,
        latex=latex,
        diagram_id=None,
        bbox=(5.0, 5.0, 50.0, 20.0),
        block_index=1,
        source_page=source_page,
    )


def _diagram_item(
    diagram_id: str = "diagram_001",
    source_page: int = 0,
) -> ContentItem:
    return ContentItem(
        kind="diagram",
        text=None,
        latex=None,
        diagram_id=diagram_id,
        bbox=(10.0, 10.0, 80.0, 60.0),
        block_index=None,
        source_page=source_page,
    )


def _simple_doc(
    questions: list = None,
    preamble: list = None,
    diagrams: Dict[str, Image.Image] = None,
    pages: int = 1,
) -> StructuredDocument:
    doc = StructuredDocument(pages=pages)
    doc.questions = questions or []
    doc.preamble = preamble or []
    doc.diagrams = diagrams or {}
    return doc


def _one_question_doc() -> StructuredDocument:
    body = (_text_item("What is 2+2?"),)
    opt_a = StructuredOption(label="A", body=(_text_item("4"),))
    opt_b = StructuredOption(label="B", body=(_text_item("5"),))
    q = StructuredQuestion(question_number="1", body=body, options=(opt_a, opt_b))
    doc = _simple_doc(questions=[q])
    return doc


# ===========================================================================
# 1. document_to_dict() is json.dumps()-able
# ===========================================================================


class TestDocumentToDictJsonSafe:

    def test_json_dumps_succeeds_for_empty_doc(self):
        doc = _simple_doc()
        d = document_to_dict(doc)
        # Must not raise
        json.dumps(d)

    def test_json_dumps_succeeds_for_text_question(self):
        d = document_to_dict(_one_question_doc())
        json.dumps(d)

    def test_json_dumps_succeeds_with_formula(self):
        body = (_formula_item(r"\alpha = \beta"),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        doc = _simple_doc(questions=[q])
        json.dumps(document_to_dict(doc))

    def test_json_dumps_succeeds_with_diagram(self):
        body = (_diagram_item("diagram_001"),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        doc = _simple_doc(
            questions=[q],
            diagrams={"diagram_001": _pil()},
        )
        json.dumps(document_to_dict(doc))

    def test_no_pil_image_in_output_dict(self):
        """PIL images must not appear anywhere in the serialised dict."""
        body = (_diagram_item("diagram_001"),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        doc = _simple_doc(
            questions=[q],
            diagrams={"diagram_001": _pil()},
        )
        d = document_to_dict(doc)
        # Recursively check no PIL image
        raw = json.dumps(d)
        assert "PIL" not in raw
        assert "Image" not in raw


# ===========================================================================
# 2. Diagrams key is list of strings (not PIL)
# ===========================================================================


class TestDiagramsKey:

    def test_diagrams_key_is_list(self):
        doc = _simple_doc(diagrams={"diagram_001": _pil()})
        d = document_to_dict(doc)
        assert isinstance(d["diagrams"], list)

    def test_diagrams_key_contains_strings_only(self):
        doc = _simple_doc(diagrams={"diagram_001": _pil(), "diagram_002": _pil()})
        d = document_to_dict(doc)
        for entry in d["diagrams"]:
            assert isinstance(entry, str)

    def test_diagrams_list_is_sorted(self):
        doc = _simple_doc(
            diagrams={
                "diagram_003": _pil(),
                "diagram_001": _pil(),
                "diagram_002": _pil(),
            }
        )
        d = document_to_dict(doc)
        assert d["diagrams"] == sorted(d["diagrams"])

    def test_empty_diagrams_is_empty_list(self):
        doc = _simple_doc()
        d = document_to_dict(doc)
        assert d["diagrams"] == []


# ===========================================================================
# 3. Required keys present in ContentItem dicts
# ===========================================================================


class TestContentItemKeys:

    def _get_first_body_item(self, doc: StructuredDocument) -> dict:
        d = document_to_dict(doc)
        return d["questions"][0]["body"][0]

    def test_text_item_has_kind_key(self):
        body = (_text_item(),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert "kind" in item_d
        assert item_d["kind"] == "text"

    def test_text_item_has_text_key(self):
        body = (_text_item("Hello"),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert "text" in item_d
        assert item_d["text"] == "Hello"

    def test_text_item_has_latex_none(self):
        body = (_text_item(),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert "latex" in item_d
        assert item_d["latex"] is None

    def test_text_item_has_diagram_id_none(self):
        body = (_text_item(),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert "diagram_id" in item_d
        assert item_d["diagram_id"] is None

    def test_text_item_has_bbox_key(self):
        body = (_text_item(bbox=(1.0, 2.0, 3.0, 4.0)),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert "bbox" in item_d
        assert item_d["bbox"] == [1.0, 2.0, 3.0, 4.0]

    def test_text_item_has_source_page_key(self):
        body = (_text_item(source_page=2),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert "source_page" in item_d
        assert item_d["source_page"] == 2

    def test_formula_item_has_latex_set(self):
        latex = r"\int_0^\infty e^{-x}\,dx"
        body = (_formula_item(latex),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        item_d = self._get_first_body_item(_simple_doc(questions=[q]))
        assert item_d["kind"] == "formula"
        assert item_d["latex"] == latex

    def test_diagram_item_has_diagram_id_set(self):
        body = (_diagram_item("diagram_007"),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        doc = _simple_doc(questions=[q], diagrams={"diagram_007": _pil()})
        item_d = self._get_first_body_item(doc)
        assert item_d["kind"] == "diagram"
        assert item_d["diagram_id"] == "diagram_007"


# ===========================================================================
# 4–5. Round-trip through json.loads / document_to_json
# ===========================================================================


class TestRoundTrip:

    def test_json_loads_succeeds(self):
        doc = _one_question_doc()
        s = document_to_json(doc)
        result = json.loads(s)
        assert isinstance(result, dict)

    def test_question_body_kind_survives_roundtrip(self):
        doc = _one_question_doc()
        s = document_to_json(doc)
        result = json.loads(s)
        assert result["questions"][0]["body"][0]["kind"] == "text"

    def test_formula_latex_survives_roundtrip(self):
        latex = r"F = ma"
        body = (_formula_item(latex),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        doc = _simple_doc(questions=[q])
        result = json.loads(document_to_json(doc))
        assert result["questions"][0]["body"][0]["latex"] == latex

    def test_diagram_id_survives_roundtrip(self):
        body = (_diagram_item("diagram_005"),)
        q = StructuredQuestion(question_number="1", body=body, options=())
        doc = _simple_doc(questions=[q], diagrams={"diagram_005": _pil()})
        result = json.loads(document_to_json(doc))
        assert result["questions"][0]["body"][0]["diagram_id"] == "diagram_005"

    def test_pages_survives_roundtrip(self):
        doc = _simple_doc(pages=4)
        result = json.loads(document_to_json(doc))
        assert result["pages"] == 4

    def test_question_number_survives_roundtrip(self):
        q = StructuredQuestion(question_number="42", body=(), options=())
        doc = _simple_doc(questions=[q])
        result = json.loads(document_to_json(doc))
        assert result["questions"][0]["question_number"] == "42"


# ===========================================================================
# 6. Empty document
# ===========================================================================


class TestEmptyDocument:

    def test_empty_doc_has_pages_key(self):
        d = document_to_dict(_simple_doc(pages=0))
        assert d["pages"] == 0

    def test_empty_doc_has_questions_list(self):
        d = document_to_dict(_simple_doc())
        assert d["questions"] == []

    def test_empty_doc_has_preamble_list(self):
        d = document_to_dict(_simple_doc())
        assert d["preamble"] == []

    def test_empty_doc_has_diagrams_list(self):
        d = document_to_dict(_simple_doc())
        assert d["diagrams"] == []

    def test_empty_doc_json_roundtrip(self):
        result = json.loads(document_to_json(_simple_doc()))
        assert result == {"pages": 1, "preamble": [], "questions": [], "diagrams": []}


# ===========================================================================
# 11. Options serialised with label and body
# ===========================================================================


class TestOptionsSerialisation:

    def test_option_label_serialised(self):
        opt = StructuredOption(label="C", body=(_text_item("Maybe"),))
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        d = document_to_dict(_simple_doc(questions=[q]))
        assert d["questions"][0]["options"][0]["label"] == "C"

    def test_option_body_serialised(self):
        opt = StructuredOption(label="A", body=(_text_item("Yes"),))
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        d = document_to_dict(_simple_doc(questions=[q]))
        option_body = d["questions"][0]["options"][0]["body"]
        assert len(option_body) == 1
        assert option_body[0]["text"] == "Yes"

    def test_multiple_options_serialised(self):
        opts = (
            StructuredOption(label="A", body=(_text_item("First"),)),
            StructuredOption(label="B", body=(_text_item("Second"),)),
            StructuredOption(label="C", body=(_text_item("Third"),)),
        )
        q = StructuredQuestion(question_number="1", body=(), options=opts)
        d = document_to_dict(_simple_doc(questions=[q]))
        labels = [o["label"] for o in d["questions"][0]["options"]]
        assert labels == ["A", "B", "C"]

    def test_option_body_with_diagram_item(self):
        opt = StructuredOption(label="A", body=(_diagram_item("diagram_002"),))
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        doc = _simple_doc(questions=[q], diagrams={"diagram_002": _pil()})
        d = document_to_dict(doc)
        opt_body = d["questions"][0]["options"][0]["body"]
        assert opt_body[0]["kind"] == "diagram"
        assert opt_body[0]["diagram_id"] == "diagram_002"


# ===========================================================================
# 12. document_to_json returns a UTF-8 string
# ===========================================================================


def test_document_to_json_returns_string():
    doc = _simple_doc()
    result = document_to_json(doc)
    assert isinstance(result, str)


def test_document_to_json_is_valid_json():
    doc = _one_question_doc()
    result = document_to_json(doc)
    parsed = json.loads(result)
    assert "questions" in parsed


# ===========================================================================
# 14. Preamble items serialised
# ===========================================================================


def test_preamble_items_serialised():
    preamble = [_text_item("PHYSICS EXAM 2024")]
    doc = _simple_doc(preamble=preamble)
    d = document_to_dict(doc)
    assert len(d["preamble"]) == 1
    assert d["preamble"][0]["text"] == "PHYSICS EXAM 2024"
    assert d["preamble"][0]["kind"] == "text"


def test_preamble_diagram_serialised():
    preamble = [_diagram_item("diagram_001")]
    doc = _simple_doc(preamble=preamble, diagrams={"diagram_001": _pil()})
    d = document_to_dict(doc)
    assert d["preamble"][0]["kind"] == "diagram"
    assert d["preamble"][0]["diagram_id"] == "diagram_001"


# ===========================================================================
# 15. Nested option body items serialised
# ===========================================================================


def test_nested_formula_in_option_serialised():
    formula = _formula_item(r"\sqrt{x}")
    opt = StructuredOption(label="B", body=(formula,))
    q = StructuredQuestion(question_number="1", body=(), options=(opt,))
    d = document_to_dict(_simple_doc(questions=[q]))
    opt_d = d["questions"][0]["options"][0]
    assert opt_d["body"][0]["kind"] == "formula"
    assert opt_d["body"][0]["latex"] == r"\sqrt{x}"
