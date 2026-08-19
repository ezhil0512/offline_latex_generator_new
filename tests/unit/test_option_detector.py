"""Unit tests for MCQ option detection."""

import pytest

from offline_latex_generator.option_detector import (
    MCQOption,
    OCRTextBlock,
    detect_mcq_options,
    group_options_by_question,
)


class TestDetectMCQOptions:
    """Test MCQ option pattern detection."""

    def test_detect_parentheses_pattern(self):
        """Test detection of (A), (B), etc. pattern."""
        blocks = [
            OCRTextBlock(text="(A) First option"),
            OCRTextBlock(text="(B) Second option"),
            OCRTextBlock(text="(C) Third option"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 3
        assert options[0].label == "A"
        assert options[0].pattern_type == "parentheses"
        assert options[0].block_index == 0
        assert options[1].label == "B"
        assert options[2].label == "C"

    def test_detect_closing_paren_pattern(self):
        """Test detection of A), B), etc. pattern."""
        blocks = [
            OCRTextBlock(text="A) First option"),
            OCRTextBlock(text="B) Second option"),
            OCRTextBlock(text="C) Third option"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 3
        assert options[0].label == "A"
        assert options[0].pattern_type == "closing_paren"
        assert options[1].label == "B"
        assert options[2].label == "C"

    def test_detect_period_pattern(self):
        """Test detection of A. B. C. pattern (with following text)."""
        blocks = [
            OCRTextBlock(text="A. First option here"),
            OCRTextBlock(text="B. Second option here"),
            OCRTextBlock(text="C. Third option here"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 3
        assert options[0].label == "A"
        assert options[0].pattern_type == "period"
        assert options[1].label == "B"
        assert options[2].label == "C"

    def test_detect_lowercase_options(self):
        """Test that lowercase labels preserve their original lowercase casing."""
        blocks = [
            OCRTextBlock(text="(a) First option"),
            OCRTextBlock(text="b) Second option"),
            OCRTextBlock(text="c. Third option"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 3
        assert options[0].label == "a"
        assert options[1].label == "b"
        assert options[2].label == "c"

    def test_ignore_non_option_blocks(self):
        """Test that non-option blocks are ignored."""
        blocks = [
            OCRTextBlock(text="This is a question text"),
            OCRTextBlock(text="Some other content"),
            OCRTextBlock(text="(A) First option"),
            OCRTextBlock(text="(B) Second option"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 2
        assert options[0].label == "A"
        assert options[0].block_index == 2

    def test_ignore_period_without_text(self):
        """Test that 'A. B. C. D.' without following text is not detected."""
        blocks = [
            OCRTextBlock(text="A."),
            OCRTextBlock(text="B."),
            OCRTextBlock(text="C."),
        ]

        options = detect_mcq_options(blocks)

        # Should detect none because no text follows the period
        assert len(options) == 0

    def test_ignore_period_with_single_char(self):
        """Test that period pattern with single character following is not detected."""
        blocks = [
            OCRTextBlock(text="A. X"),
            OCRTextBlock(text="B. Y"),
        ]

        options = detect_mcq_options(blocks)

        # Single characters after period should not qualify
        assert len(options) == 0

    def test_empty_block_sequence(self):
        """Test handling of empty block sequence."""
        options = detect_mcq_options([])
        assert options == []

    def test_mixed_patterns(self):
        """Test that different patterns are detected correctly even when mixed."""
        blocks = [
            OCRTextBlock(text="1. What is X?"),
            OCRTextBlock(text="(A) Option A"),
            OCRTextBlock(text="B) Option B"),
            OCRTextBlock(text="C. Option C is correct"),
            OCRTextBlock(text="2. Next question?"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 3
        assert options[0].label == "A"
        assert options[0].pattern_type == "parentheses"
        assert options[1].label == "B"
        assert options[1].pattern_type == "closing_paren"
        assert options[2].label == "C"
        assert options[2].pattern_type == "period"

    def test_options_with_leading_whitespace(self):
        """Test detection with leading whitespace."""
        blocks = [
            OCRTextBlock(text="  (A) Option with leading spaces"),
            OCRTextBlock(text="\t\tB) Option with tabs"),
            OCRTextBlock(text="   C. Option with more spaces"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 3
        assert all(opt.label in ["A", "B", "C"] for opt in options)

    def test_non_letter_labels_ignored(self):
        """Test that non-letter labels are not detected as options."""
        blocks = [
            OCRTextBlock(text="(1) This looks like an option but uses number"),
            OCRTextBlock(text="(A) This is a real option"),
            OCRTextBlock(text="(*) This uses special char"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 1
        assert options[0].label == "A"

    def test_block_index_preserved(self):
        """Test that block indices are correctly preserved."""
        blocks = [
            OCRTextBlock(text="Question text"),
            OCRTextBlock(text="Some filler"),
            OCRTextBlock(text="(A) Option A"),
            OCRTextBlock(text="(B) Option B"),
            OCRTextBlock(text="(C) Option C"),
        ]

        options = detect_mcq_options(blocks)

        assert options[0].block_index == 2
        assert options[1].block_index == 3
        assert options[2].block_index == 4

    def test_text_content_preserved(self):
        """Test that full text content is preserved in MCQOption."""
        blocks = [
            OCRTextBlock(text="(A) This is the full option text"),
            OCRTextBlock(text="B) Another full option text"),
        ]

        options = detect_mcq_options(blocks)

        assert options[0].text == "(A) This is the full option text"
        assert options[1].text == "B) Another full option text"

    def test_detect_ocr_variant_options(self):
        """Test detection of common OCR variants (b5.33, b)5.33, (b 5.33, B5.33, etc.)."""
        blocks = [
            OCRTextBlock(text="(b) 5.33"),
            OCRTextBlock(text="b5.33"),
            OCRTextBlock(text="b)5.33"),
            OCRTextBlock(text="(b 5.33"),
            OCRTextBlock(text="B5.33"),
        ]

        options = detect_mcq_options(blocks)

        assert len(options) == 5
        assert [opt.label for opt in options] == ["b", "b", "b", "b", "B"]


class TestGroupOptionsByQuestion:
    """Test grouping options with their containing questions."""

    def test_group_options_with_single_question(self):
        """Test grouping options for a single question."""
        question_regions = [
            {
                "start_index": 0,
                "end_index": 4,
                "question_text": "1. What is X?",
                "text_blocks": [
                    "1. What is X?",
                    "(A) Option A",
                    "(B) Option B",
                    "(C) Option C",
                ],
            }
        ]

        result = group_options_by_question(question_regions)

        assert len(result) == 1
        assert "options" in result[0]
        assert len(result[0]["options"]) == 3
        assert result[0]["options"][0].label == "A"

    def test_group_options_with_multiple_questions(self):
        """Test grouping options for multiple questions."""
        question_regions = [
            {
                "start_index": 0,
                "end_index": 3,
                "question_text": "1. Question one",
                "text_blocks": ["1. Question one", "(A) Option A", "(B) Option B"],
            },
            {
                "start_index": 3,
                "end_index": 6,
                "question_text": "2. Question two",
                "text_blocks": ["2. Question two", "(A) Option A", "(B) Option B"],
            },
        ]

        result = group_options_by_question(question_regions)

        assert len(result) == 2
        assert len(result[0]["options"]) == 2
        assert len(result[1]["options"]) == 2

    def test_group_options_adjusts_indices_correctly(self):
        """Test that block indices are adjusted relative to original document."""
        question_regions = [
            {
                "start_index": 5,
                "end_index": 8,
                "question_text": "Question",
                "text_blocks": [
                    "Question",
                    "(A) Option A",
                    "(B) Option B",
                ],
            }
        ]

        result = group_options_by_question(question_regions)

        options = result[0]["options"]
        # Original block indices within region are 0, 1, 2
        # Should be adjusted by start_index (5)
        assert options[0].block_index == 6
        assert options[1].block_index == 7

    def test_group_empty_regions(self):
        """Test handling of empty question regions."""
        question_regions = []
        result = group_options_by_question(question_regions)
        assert result == []

    def test_group_region_without_options(self):
        """Test handling of regions with no options."""
        question_regions = [
            {
                "start_index": 0,
                "end_index": 2,
                "question_text": "1. Question",
                "text_blocks": ["1. Question", "Some other text"],
            }
        ]

        result = group_options_by_question(question_regions)

        assert len(result) == 1
        assert result[0]["options"] == []

    def test_group_preserves_other_region_data(self):
        """Test that other region data is preserved."""
        question_regions = [
            {
                "start_index": 0,
                "end_index": 3,
                "question_text": "1. Question",
                "text_blocks": ["1. Question", "(A) Option A", "(B) Option B"],
                "custom_field": "custom_value",
            }
        ]

        result = group_options_by_question(question_regions)

        assert result[0]["question_text"] == "1. Question"
        assert result[0]["custom_field"] == "custom_value"
        assert len(result[0]["options"]) == 2

    def test_group_mixed_option_patterns_in_question(self):
        """Test grouping of questions with mixed option patterns."""
        question_regions = [
            {
                "start_index": 0,
                "end_index": 4,
                "question_text": "Which is correct?",
                "text_blocks": [
                    "Which is correct?",
                    "(A) First",
                    "B) Second",
                    "C. Third option",
                ],
            }
        ]

        result = group_options_by_question(question_regions)

        options = result[0]["options"]
        assert len(options) == 3
        assert options[0].pattern_type == "parentheses"
        assert options[1].pattern_type == "closing_paren"
        assert options[2].pattern_type == "period"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_option_at_end_of_text(self):
        """Test option detection when option is at the end of a block."""
        blocks = [OCRTextBlock(text="(A) Last option")]
        options = detect_mcq_options(blocks)
        assert len(options) == 1

    def test_multiple_options_same_block(self):
        """Test that only the first option pattern per block is detected."""
        blocks = [OCRTextBlock(text="(A) First (B) Second")]
        options = detect_mcq_options(blocks)
        # Should only detect the first pattern
        assert len(options) == 1
        assert options[0].label == "A"

    def test_option_after_question_marks(self):
        """Test that options following question marks are detected."""
        blocks = [
            OCRTextBlock(text="What is X? (A) Option"),
            OCRTextBlock(text="(B) Another"),
        ]
        options = detect_mcq_options(blocks)
        # First block doesn't match pattern (contains more than just option)
        assert len(options) == 1
        assert options[0].label == "B"

    def test_alphabetically_non_sequential_options(self):
        """Test detection of non-sequential option labels."""
        blocks = [
            OCRTextBlock(text="(A) First"),
            OCRTextBlock(text="(C) Third"),
            OCRTextBlock(text="(Z) Last"),
        ]
        options = detect_mcq_options(blocks)
        assert len(options) == 3
        assert options[0].label == "A"
        assert options[1].label == "C"
        assert options[2].label == "Z"


class TestOptionAssociation:
    """Test spatial and structural option label-value block association."""

    def test_option_label_and_value_in_same_block(self):
        blocks = [
            OCRTextBlock(text="(a) 3"),
            OCRTextBlock(text="(b) 5.33"),
        ]
        options = detect_mcq_options(blocks)
        assert len(options) == 2
        assert options[0].label == "a"
        assert options[0].text == "(a) 3"
        assert options[0].block_indices == (0,)

    def test_option_label_in_one_block_and_value_in_next_block(self):
        blocks = [
            OCRTextBlock(text="(c)"),
            OCRTextBlock(text="2.6"),
        ]
        options = detect_mcq_options(blocks)
        assert len(options) == 1
        assert options[0].label == "c"
        assert options[0].text == "(c) 2.6"
        assert options[0].block_indices == (0, 1)

    def test_multiple_consecutive_options_split_across_blocks(self):
        blocks = [
            OCRTextBlock(text="(a)"),
            OCRTextBlock(text="10"),
            OCRTextBlock(text="(b)"),
            OCRTextBlock(text="20"),
        ]
        options = detect_mcq_options(blocks)
        assert len(options) == 2
        assert options[0].label == "a"
        assert options[0].text == "(a) 10"
        assert options[0].block_indices == (0, 1)
        assert options[1].label == "b"
        assert options[1].text == "(b) 20"
        assert options[1].block_indices == (2, 3)

    def test_unrelated_question_text_after_option_not_merged(self):
        blocks = [
            OCRTextBlock(text="(d) 4"),
            OCRTextBlock(text="27. Next question start"),
        ]
        options = detect_mcq_options(blocks)
        assert len(options) == 1
        assert options[0].label == "d"
        assert options[0].text == "(d) 4"
        assert options[0].block_indices == (0,)

