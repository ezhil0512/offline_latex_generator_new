"""
Phase 8 focused unit tests for the layout_detector package.

Covers:
1. Basic layout element creation
2. Bounding-box preservation
3. Confidence preservation
4. Text / block association
5. Empty and invalid OCR input
6. Multiple layout elements with correct region_type classification
"""
from __future__ import annotations

import pytest

from offline_latex_generator.layout_detector import (
    LayoutDetectorError,
    LayoutElement,
    LayoutRegionType,
    OCRBlock,
    detect_layout,
    parse_ocr_blocks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quad(x0, y0, x1, y1):
    """Return a clockwise 4-corner quad for a given axis-aligned bbox."""
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _raw_detection(x0, y0, x1, y1, text, conf):
    """Build a single PaddleOCR detection entry."""
    return [_make_quad(x0, y0, x1, y1), (text, conf)]


def _raw_page(*detections):
    """Wrap detections in the page-list structure expected by parse_ocr_blocks."""
    return [list(detections)]


# ===========================================================================
# 1. Basic element creation
# ===========================================================================

class TestBasicElementCreation:

    def test_single_block_produces_single_element(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(10.0, 20.0, 100.0, 40.0), text="Some text here and more", confidence=0.75)
        ]
        elements = detect_layout(blocks)
        assert len(elements) == 1

    def test_element_is_layout_element_instance(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(0.0, 0.0, 50.0, 20.0), text="Hello world example text", confidence=0.70)
        ]
        elements = detect_layout(blocks)
        assert isinstance(elements[0], LayoutElement)

    def test_element_region_type_is_valid_string(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(0.0, 0.0, 50.0, 20.0), text="Some content text here and more", confidence=0.70)
        ]
        elements = detect_layout(blocks)
        valid_types = {
            LayoutRegionType.TEXT,
            LayoutRegionType.HEADING,
            LayoutRegionType.QUESTION,
            LayoutRegionType.OPTION,
            LayoutRegionType.UNKNOWN,
        }
        assert elements[0].region_type in valid_types

    def test_element_is_frozen(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(0.0, 0.0, 10.0, 10.0), text="Test text content phrase", confidence=0.80)
        ]
        element = detect_layout(blocks)[0]
        with pytest.raises((AttributeError, TypeError)):
            element.region_type = "mutated"  # type: ignore[misc]



# ===========================================================================
# 2. Bounding-box preservation
# ===========================================================================

class TestBoundingBoxPreservation:

    def test_bbox_tuple_matches_input_ocr_block(self):
        bbox = (10.5, 22.0, 300.0, 55.75)
        blocks = [
            OCRBlock(block_index=0, bbox=bbox, text="Some text content here", confidence=0.88)
        ]
        element = detect_layout(blocks)[0]
        assert element.bbox == bbox

    def test_parse_ocr_blocks_normalises_quad_to_bbox(self):
        # Quad with corners given in non-standard order
        quad = [[50, 100], [10, 100], [10, 20], [50, 20]]
        raw = [[quad, ("hello", 0.95)]]
        blocks = parse_ocr_blocks([raw])
        assert blocks[0].bbox == (10.0, 20.0, 50.0, 100.0)

    def test_bbox_preserved_from_parse_through_detect(self):
        raw = _raw_page(_raw_detection(5.0, 15.0, 200.0, 45.0, "Sample text line content", 0.90))
        blocks = parse_ocr_blocks(raw)
        elements = detect_layout(blocks)
        assert elements[0].bbox == blocks[0].bbox == (5.0, 15.0, 200.0, 45.0)

    def test_bbox_is_tuple_of_four_floats(self):
        raw = _raw_page(_raw_detection(0, 0, 100, 50, "Some content text here words", 0.85))
        blocks = parse_ocr_blocks(raw)
        bbox = detect_layout(blocks)[0].bbox
        assert isinstance(bbox, tuple)
        assert len(bbox) == 4
        assert all(isinstance(v, float) for v in bbox)


# ===========================================================================
# 3. Confidence preservation
# ===========================================================================

class TestConfidencePreservation:

    def test_confidence_flows_from_ocr_block(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(0, 0, 10, 10), text="Confidence test content text", confidence=0.9234)
        ]
        element = detect_layout(blocks)[0]
        assert element.confidence == pytest.approx(0.9234)

    def test_confidence_flows_through_parse(self):
        raw = _raw_page(_raw_detection(0, 0, 100, 20, "Text content here words more", 0.7654))
        blocks = parse_ocr_blocks(raw)
        assert blocks[0].confidence == pytest.approx(0.7654)

    def test_confidence_end_to_end(self):
        raw = _raw_page(_raw_detection(0, 0, 100, 20, "Full pipeline confidence check text", 0.8123))
        elements = detect_layout(parse_ocr_blocks(raw))
        assert elements[0].confidence == pytest.approx(0.8123)

    def test_negative_confidence_sentinel_preserved(self):
        # -1.0 is the sentinel for "not available"
        blocks = [
            OCRBlock(block_index=0, bbox=(0, 0, 10, 10), text="Some text here words", confidence=-1.0)
        ]
        element = detect_layout(blocks)[0]
        assert element.confidence == -1.0


# ===========================================================================
# 4. Text / block association
# ===========================================================================

class TestTextBlockAssociation:

    def test_texts_tuple_matches_block_text(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(0, 0, 50, 20), text="Hello world", confidence=0.95)
        ]
        element = detect_layout(blocks)[0]
        assert element.texts == ("Hello world",)

    def test_block_indices_tuple_matches_block_index(self):
        blocks = [
            OCRBlock(block_index=7, bbox=(0, 0, 50, 20), text="Some text content longer", confidence=0.90)
        ]
        element = detect_layout(blocks)[0]
        assert element.block_indices == (7,)

    def test_block_index_sequential_from_parse(self):
        raw = _raw_page(
            _raw_detection(0, 0, 10, 10, "First block text", 0.91),
            _raw_detection(0, 20, 10, 30, "Second block text", 0.88),
            _raw_detection(0, 40, 10, 50, "Third block text", 0.85),
        )
        blocks = parse_ocr_blocks(raw)
        assert [b.block_index for b in blocks] == [0, 1, 2]

    def test_texts_tuple_is_immutable(self):
        blocks = [
            OCRBlock(block_index=0, bbox=(0, 0, 10, 10), text="Content text here words more", confidence=0.80)
        ]
        element = detect_layout(blocks)[0]
        assert isinstance(element.texts, tuple)


# ===========================================================================
# 5. Empty / invalid OCR input
# ===========================================================================

class TestEmptyAndInvalidInput:

    def test_parse_none_returns_empty(self):
        assert parse_ocr_blocks(None) == []

    def test_parse_empty_list_returns_empty(self):
        assert parse_ocr_blocks([]) == []

    def test_parse_list_of_none_returns_empty(self):
        assert parse_ocr_blocks([None]) == []

    def test_parse_list_of_empty_page_returns_empty(self):
        assert parse_ocr_blocks([[]]) == []

    def test_detect_empty_blocks_returns_empty(self):
        assert detect_layout([]) == []

    def test_whitespace_only_text_becomes_unknown(self):
        raw = _raw_page(_raw_detection(0, 0, 10, 10, "   ", 0.50))
        blocks = parse_ocr_blocks(raw)
        elements = detect_layout(blocks)
        assert elements[0].region_type == LayoutRegionType.UNKNOWN

    def test_empty_text_becomes_unknown(self):
        raw = _raw_page(_raw_detection(0, 0, 10, 10, "", 0.50))
        blocks = parse_ocr_blocks(raw)
        elements = detect_layout(blocks)
        assert elements[0].region_type == LayoutRegionType.UNKNOWN

    def test_malformed_detection_raises_error(self):
        with pytest.raises(LayoutDetectorError):
            parse_ocr_blocks([["bad_entry"]])


# ===========================================================================
# 6. Multiple layout elements — classification correctness
# ===========================================================================

class TestMultipleLayoutElements:

    def _make_blocks(self, entries):
        """entries = list of (text, confidence)"""
        return [
            OCRBlock(block_index=i, bbox=(0.0, float(i * 20), 300.0, float(i * 20 + 18)), text=t, confidence=c)
            for i, (t, c) in enumerate(entries)
        ]

    def test_question_block_classified_correctly(self):
        blocks = self._make_blocks([("1. What is photosynthesis?", 0.92)])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.QUESTION

    def test_question_prefix_pattern_classified_correctly(self):
        blocks = self._make_blocks([("Question 2: Name the largest ocean.", 0.88)])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.QUESTION

    def test_unspaced_ocr_question_classified_correctly(self):
        blocks = self._make_blocks([("26.A thin prism P of angle of prism", 0.94)])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.QUESTION

    def test_option_parentheses_classified_correctly(self):
        blocks = self._make_blocks([("(A) Chlorophyll absorbs sunlight", 0.85)])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.OPTION

    def test_option_closing_paren_classified_correctly(self):
        blocks = self._make_blocks([("B) Carbon dioxide", 0.87)])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.OPTION

    def test_heading_classified_correctly(self):
        # Short (<=6 words) and high confidence
        blocks = self._make_blocks([("Section A: Biology", 0.95)])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.HEADING

    def test_long_text_classified_as_text(self):
        # More than 6 words → TEXT regardless of confidence
        blocks = self._make_blocks([
            ("The process of photosynthesis converts light energy into chemical energy stored in glucose molecules.", 0.92)
        ])
        assert detect_layout(blocks)[0].region_type == LayoutRegionType.TEXT

    def test_mixed_blocks_produce_correct_types(self):
        entries = [
            ("Sample Examination Paper",                  0.97),   # heading (2 words... actually 3)
            ("1. What is the powerhouse of the cell?",   0.93),   # question
            ("(A) Mitochondria",                          0.89),   # option
            ("(B) Nucleus",                               0.91),   # option
            ("The cell was first described by Robert Hooke in 1665 when he observed cork.", 0.88),  # text
        ]
        blocks = self._make_blocks(entries)
        elements = detect_layout(blocks)
        assert len(elements) == 5
        assert elements[0].region_type == LayoutRegionType.HEADING
        assert elements[1].region_type == LayoutRegionType.QUESTION
        assert elements[2].region_type == LayoutRegionType.OPTION
        assert elements[3].region_type == LayoutRegionType.OPTION
        assert elements[4].region_type == LayoutRegionType.TEXT

    def test_count_matches_input_block_count(self):
        entries = [("Text " + str(i) + " content here words longer", 0.80) for i in range(8)]
        blocks = self._make_blocks(entries)
        assert len(detect_layout(blocks)) == 8

    def test_parse_then_detect_round_trip(self):
        """parse_ocr_blocks + detect_layout end-to-end on a mixed raw result."""
        raw = _raw_page(
            _raw_detection(0, 0, 200, 20, "1. What is gravity?", 0.94),
            _raw_detection(0, 25, 200, 45, "(A) A force", 0.90),
            _raw_detection(0, 50, 200, 70, "(B) A type of energy", 0.88),
        )
        blocks = parse_ocr_blocks(raw)
        elements = detect_layout(blocks)
        assert len(elements) == 3
        assert elements[0].region_type == LayoutRegionType.QUESTION
        assert elements[1].region_type == LayoutRegionType.OPTION
        assert elements[2].region_type == LayoutRegionType.OPTION
        # Confidence preserved
        assert elements[0].confidence == pytest.approx(0.94)
        # Block indices preserved
        assert elements[1].block_indices == (1,)
        assert elements[1].texts == ("(A) A force",)
