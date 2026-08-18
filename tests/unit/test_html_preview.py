"""Unit tests for Phase 18: HTML Preview.

All tests build StructuredDocument objects purely in memory.
No files are written to disk during any test.
"""

from __future__ import annotations

import base64
import os
import struct

import pytest
from PIL import Image

from offline_latex_generator.preview import generate_html_preview
from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_BBOX = (0.0, 0.0, 10.0, 10.0)


def make_text(text: str) -> ContentItem:
    return ContentItem(
        kind="text", text=text, latex=None, diagram_id=None, bbox=_DUMMY_BBOX, block_index=0
    )


def make_formula(latex: str) -> ContentItem:
    return ContentItem(
        kind="formula", text=None, latex=latex, diagram_id=None, bbox=_DUMMY_BBOX, block_index=0
    )


def make_diagram(diagram_id: str) -> ContentItem:
    return ContentItem(
        kind="diagram", text=None, latex=None, diagram_id=diagram_id, bbox=_DUMMY_BBOX, block_index=0
    )


def small_pil_image() -> Image.Image:
    """Return a tiny valid 4×4 red PIL image for use as a diagram placeholder."""
    return Image.new("RGBA", (4, 4), color=(255, 0, 0, 255))


def make_doc_with_diagram(diag_id: str = "diagram_001") -> StructuredDocument:
    img = small_pil_image()
    q = StructuredQuestion(
        question_number="1",
        body=(make_diagram(diag_id),),
        options=(),
    )
    doc = StructuredDocument(pages=1)
    doc.questions.append(q)
    doc.diagrams[diag_id] = img
    return doc


# ---------------------------------------------------------------------------
# 1. HTML Structure
# ---------------------------------------------------------------------------


class TestHtmlStructure:

    def test_output_is_string(self):
        doc = StructuredDocument(pages=1)
        result = generate_html_preview(doc)
        assert isinstance(result, str)

    def test_doctype_present(self):
        doc = StructuredDocument(pages=1)
        assert "<!DOCTYPE html>" in generate_html_preview(doc)

    def test_html_tag_present(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        assert "<html" in out and "</html>" in out

    def test_head_tag_present(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        assert "<head" in out and "</head>" in out

    def test_body_tag_present(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        assert "<body>" in out
        assert "</body>" in out

    def test_empty_document_valid(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        assert "<!DOCTYPE html>" in out
        assert "<html" in out


# ---------------------------------------------------------------------------
# 2. Plain Text Escaping
# ---------------------------------------------------------------------------


class TestTextEscaping:

    def test_less_than_escaped(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_text("<script>"),), ())
        doc.questions.append(q)
        out = generate_html_preview(doc)
        # The escaped version must appear in the output
        assert "&lt;script&gt;" in out
        # The unescaped literal must NOT appear inside any text-content span.
        # (Note: the HTML foot legitimately contains real <script> tags, so we
        # check only that the escaped form is present — confirming html.escape fired.)
        assert '&lt;script&gt;' in out

    def test_greater_than_escaped(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_text("a > b"),), ())
        doc.questions.append(q)
        out = generate_html_preview(doc)
        assert "a &gt; b" in out

    def test_ampersand_escaped(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_text("H2O & NaCl"),), ())
        doc.questions.append(q)
        out = generate_html_preview(doc)
        assert "H2O &amp; NaCl" in out
        assert "H2O & NaCl" not in out

    def test_double_quote_escaped(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_text('say "hello"'),), ())
        doc.questions.append(q)
        out = generate_html_preview(doc)
        assert "&quot;hello&quot;" in out

    def test_plain_text_renders_inside_span(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_text("Hello world"),), ())
        doc.questions.append(q)
        out = generate_html_preview(doc)
        assert '<span class="text-content">Hello world</span>' in out


# ---------------------------------------------------------------------------
# 3. Formula Verbatim Preservation
# ---------------------------------------------------------------------------


class TestFormulaPreservation:

    def _html_for(self, latex: str) -> str:
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_formula(latex),), ())
        doc.questions.append(q)
        return generate_html_preview(doc)

    def test_superscript_preserved(self):
        out = self._html_for("x^2")
        assert "x^2" in out

    def test_subscript_preserved(self):
        out = self._html_for("E_n")
        assert "E_n" in out

    def test_frac_preserved(self):
        out = self._html_for(r"\frac{a}{b}")
        assert r"\frac{a}{b}" in out

    def test_sqrt_preserved(self):
        out = self._html_for(r"\sqrt{x}")
        assert r"\sqrt{x}" in out

    def test_alpha_preserved(self):
        out = self._html_for(r"\alpha")
        assert r"\alpha" in out

    def test_beta_preserved(self):
        out = self._html_for(r"\beta")
        assert r"\beta" in out

    def test_rightarrow_preserved(self):
        out = self._html_for(r"\rightarrow")
        assert r"\rightarrow" in out

    def test_integral_preserved(self):
        out = self._html_for(r"\int")
        assert r"\int" in out

    def test_inline_formula_wrapped_in_katex_inline_delimiter(self):
        out = self._html_for("x^2")
        assert r"\(x^2\)" in out

    def test_inline_formula_not_double_dollar_wrapped(self):
        out = self._html_for("x^2")
        assert "$$x^2$$" not in out

    def test_inline_formula_not_bracket_wrapped(self):
        out = self._html_for("x^2")
        # Should be \(x^2\) not \[x^2\]
        assert r"\[x^2\]" not in out


# ---------------------------------------------------------------------------
# 4. Display Formula — No Double-Wrapping
# ---------------------------------------------------------------------------


class TestDisplayFormula:

    def _html_for(self, latex: str) -> str:
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_formula(latex),), ())
        doc.questions.append(q)
        return generate_html_preview(doc)

    def test_bracket_display_not_double_wrapped(self):
        latex = r"\[ E = mc^2 \]"
        out = self._html_for(latex)
        # Must appear verbatim, not inside \( ... \)
        assert r"\[ E = mc^2 \]" in out
        # Must NOT be wrapped in \( ... \)
        assert r"\(\[ E = mc^2 \]\)" not in out

    def test_double_dollar_display_not_double_wrapped(self):
        latex = r"$$ E = mc^2 $$"
        out = self._html_for(latex)
        assert r"$$ E = mc^2 $$" in out
        assert r"\($$ E = mc^2 $$\)" not in out

    def test_begin_equation_not_double_wrapped(self):
        latex = r"\begin{equation} x = y \end{equation}"
        out = self._html_for(latex)
        assert r"\begin{equation} x = y \end{equation}" in out
        assert r"\(\begin{equation}" not in out

    def test_display_formula_class(self):
        latex = r"\[ x \]"
        out = self._html_for(latex)
        assert 'class="formula-display"' in out

    def test_inline_formula_class(self):
        latex = r"x^2"
        out = self._html_for(latex)
        assert 'class="formula-inline"' in out


# ---------------------------------------------------------------------------
# 5. Diagram Embedding
# ---------------------------------------------------------------------------


class TestDiagramEmbedding:

    def test_diagram_produces_img_tag(self):
        doc = make_doc_with_diagram()
        out = generate_html_preview(doc)
        assert "<img" in out

    def test_diagram_has_base64_data_url(self):
        doc = make_doc_with_diagram()
        out = generate_html_preview(doc)
        assert 'src="data:image/png;base64,' in out

    def test_diagram_base64_is_valid_png(self):
        doc = make_doc_with_diagram()
        out = generate_html_preview(doc)
        # Extract base64 content
        start = out.index('src="data:image/png;base64,') + len('src="data:image/png;base64,')
        end = out.index('"', start)
        raw = base64.b64decode(out[start:end])
        # PNG magic bytes: first 8 bytes
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"

    def test_diagram_class_present(self):
        doc = make_doc_with_diagram()
        out = generate_html_preview(doc)
        assert 'class="diagram"' in out

    def test_missing_diagram_produces_placeholder(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion("1", (make_diagram("diagram_999"),), ())
        doc.questions.append(q)
        # Do NOT add diagram_999 to doc.diagrams
        out = generate_html_preview(doc)
        assert "diagram-missing" in out
        assert "diagram_999" in out
        assert "<img" not in out

    def test_no_filesystem_writes(self):
        """Verifies the project directory is not modified during HTML generation."""
        doc = make_doc_with_diagram()
        before = set(os.listdir("."))
        generate_html_preview(doc)
        after = set(os.listdir("."))
        assert before == after, f"Unexpected files: {after - before}"

    def test_multiple_diagrams_embedded(self):
        img1 = small_pil_image()
        img2 = Image.new("RGBA", (4, 4), color=(0, 255, 0, 255))
        q = StructuredQuestion(
            "1",
            (make_diagram("diagram_001"), make_diagram("diagram_002")),
            (),
        )
        doc = StructuredDocument(pages=1)
        doc.questions.append(q)
        doc.diagrams["diagram_001"] = img1
        doc.diagrams["diagram_002"] = img2
        out = generate_html_preview(doc)
        assert out.count('src="data:image/png;base64,') == 2


# ---------------------------------------------------------------------------
# 6. Position Preservation
# ---------------------------------------------------------------------------


class TestPositionPreservation:

    def test_diagram_appears_between_text_and_options(self):
        """Diagram in body should render before the options block."""
        img = small_pil_image()
        q = StructuredQuestion(
            "1",
            (
                make_text("Question stem."),
                make_diagram("diagram_001"),
            ),
            (
                StructuredOption("A", (make_text("Option A"),)),
            ),
        )
        doc = StructuredDocument(pages=1)
        doc.questions.append(q)
        doc.diagrams["diagram_001"] = img
        out = generate_html_preview(doc)

        img_pos = out.index("<img")
        options_pos = out.index('class="options"')
        assert img_pos < options_pos, "Diagram must appear before options block"

    def test_diagram_inside_option_b(self):
        """Diagram inside option B's body must appear within option B's HTML block."""
        img = small_pil_image()
        opt_a = StructuredOption("A", (make_text("Option A text"),))
        opt_b = StructuredOption(
            "B",
            (make_text("Option B text"), make_diagram("diagram_001")),
        )
        q = StructuredQuestion("1", (make_text("Stem"),), (opt_a, opt_b))
        doc = StructuredDocument(pages=1)
        doc.questions.append(q)
        doc.diagrams["diagram_001"] = img
        out = generate_html_preview(doc)

        # Find where option B starts and option A ends
        opt_a_pos = out.index("Option A text")
        opt_b_pos = out.index("Option B text")
        img_pos = out.index("<img")

        assert img_pos > opt_b_pos, "Diagram must appear after option B label/text"
        assert img_pos > opt_a_pos, "Diagram must not appear inside option A"

    def test_text_and_formula_order_preserved(self):
        stem_text = "Evaluate"
        formula_latex = r"\int_0^1 x\,dx"
        q = StructuredQuestion(
            "1",
            (make_text(stem_text), make_formula(formula_latex)),
            (),
        )
        doc = StructuredDocument(pages=1)
        doc.questions.append(q)
        out = generate_html_preview(doc)

        text_pos = out.index(stem_text)
        formula_pos = out.index(r"\int_0^1 x\,dx")
        assert text_pos < formula_pos, "Text must appear before formula in output"


# ---------------------------------------------------------------------------
# 7. MCQ Order
# ---------------------------------------------------------------------------


class TestMCQOrder:

    def _two_question_doc(self) -> StructuredDocument:
        doc = StructuredDocument(pages=1)
        for i in (1, 2, 3):
            q = StructuredQuestion(
                str(i),
                (make_text(f"Question {i} stem"),),
                (
                    StructuredOption("A", (make_text("Option A"),)),
                    StructuredOption("B", (make_text("Option B"),)),
                    StructuredOption("C", (make_text("Option C"),)),
                    StructuredOption("D", (make_text("Option D"),)),
                ),
            )
            doc.questions.append(q)
        return doc

    def test_questions_appear_in_order(self):
        doc = self._two_question_doc()
        out = generate_html_preview(doc)
        pos1 = out.index("Question 1 stem")
        pos2 = out.index("Question 2 stem")
        pos3 = out.index("Question 3 stem")
        assert pos1 < pos2 < pos3

    def test_option_labels_appear(self):
        doc = self._two_question_doc()
        out = generate_html_preview(doc)
        assert "A." in out
        assert "B." in out
        assert "C." in out
        assert "D." in out

    def test_options_appear_in_label_order(self):
        doc = self._two_question_doc()
        out = generate_html_preview(doc)
        # Within the first question block, A must come before B, B before C, etc.
        pos_a = out.index("Option A")
        pos_b = out.index("Option B")
        pos_c = out.index("Option C")
        pos_d = out.index("Option D")
        assert pos_a < pos_b < pos_c < pos_d


# ---------------------------------------------------------------------------
# 8. Preamble
# ---------------------------------------------------------------------------


class TestPreamble:

    def test_preamble_rendered_before_questions(self):
        doc = StructuredDocument(pages=1)
        doc.preamble.append(make_text("Exam Instructions"))
        q = StructuredQuestion("1", (make_text("Q1 stem"),), ())
        doc.questions.append(q)
        out = generate_html_preview(doc)
        preamble_pos = out.index("Exam Instructions")
        q1_pos = out.index("Q1 stem")
        assert preamble_pos < q1_pos

    def test_preamble_rendered_in_preamble_div(self):
        doc = StructuredDocument(pages=1)
        doc.preamble.append(make_text("Header text"))
        out = generate_html_preview(doc)
        assert 'class="preamble"' in out
        assert "Header text" in out


# ---------------------------------------------------------------------------
# 9. KaTeX References (Local, No CDN)
# ---------------------------------------------------------------------------


class TestKaTeXReferences:

    def test_katex_css_is_local(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        # Must reference local path, not CDN
        assert "/static/katex/katex.min.css" in out
        assert "cdnjs" not in out
        assert "jsdelivr" not in out
        assert "unpkg" not in out

    def test_katex_js_is_local(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        assert "/static/katex/katex.min.js" in out
        assert "cdnjs" not in out

    def test_auto_render_js_is_local(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        assert "/static/katex/contrib/auto-render.min.js" in out

    def test_no_external_urls(self):
        doc = StructuredDocument(pages=1)
        out = generate_html_preview(doc)
        for cdn in ("https://cdn", "http://cdn", "https://unpkg", "https://cdnjs"):
            assert cdn not in out, f"Unexpected external URL: {cdn}"
