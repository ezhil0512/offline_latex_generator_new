"""Unit tests for Phase 16: LaTeX Generation.

Covers:
1.  Normal text escaping (special characters &, %, $, #, _, {, }, ~, ^, \).
2.  Formula verbatim preservation (characters such as ^, _, \frac, \sqrt, \alpha, \rightarrow).
3.  Inline formulas (wrapped in $...$).
4.  Already-delimited display formulas (preserved verbatim, not double-wrapped).
5.  Diagram references (correct format, diagram ID underscore NOT escaped).
6.  Preamble rendering.
7.  Question structure and custom label styling (e.g. \item[\textbf{1.}]).
8.  Option structure and custom label styling (e.g. \item[\textbf{(A)}]).
9.  Diagram position (inside question body vs inside option body).
10. Multiple questions and options ordering.
11. Empty document rendering.
12. Science content formatting.
"""

from __future__ import annotations

import pytest
from PIL import Image

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)
from offline_latex_generator.generator import (
    escape_latex_text,
    render_content_item,
    generate_latex,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_item(text: str, source_page: int = 0) -> ContentItem:
    return ContentItem(
        kind="text",
        text=text,
        latex=None,
        diagram_id=None,
        bbox=(0.0, 0.0, 10.0, 10.0),
        block_index=0,
        source_page=source_page,
    )


def _formula_item(latex: str, source_page: int = 0) -> ContentItem:
    return ContentItem(
        kind="formula",
        text=None,
        latex=latex,
        diagram_id=None,
        bbox=(0.0, 0.0, 10.0, 10.0),
        block_index=0,
        source_page=source_page,
    )


def _diagram_item(diagram_id: str, source_page: int = 0) -> ContentItem:
    return ContentItem(
        kind="diagram",
        text=None,
        latex=None,
        diagram_id=diagram_id,
        bbox=(0.0, 0.0, 10.0, 10.0),
        block_index=None,
        source_page=source_page,
    )


def _option(label: str, text: str, extra_items: list = None) -> StructuredOption:
    body_list = [_text_item(text)]
    if extra_items:
        body_list.extend(extra_items)
    return StructuredOption(label=label, body=tuple(body_list))


# ===========================================================================
# 1. Normal Text Escaping
# ===========================================================================


class TestTextEscaping:

    def test_escaping_ampersand(self):
        assert escape_latex_text("A & B") == r"A \& B"

    def test_escaping_percent(self):
        assert escape_latex_text("100% pure") == r"100\% pure"

    def test_escaping_dollar(self):
        assert escape_latex_text("Price is $10") == r"Price is \$10"

    def test_escaping_hash(self):
        assert escape_latex_text("Issue #42") == r"Issue \#42"

    def test_escaping_underscore(self):
        assert escape_latex_text("variable_name") == r"variable\_name"

    def test_escaping_braces(self):
        assert escape_latex_text("{hello}") == r"\{hello\}"

    def test_escaping_tilde(self):
        assert escape_latex_text("approx ~ 5") == r"approx \textasciitilde{} 5"

    def test_escaping_caret(self):
        assert escape_latex_text("value^2") == r"value\textasciicircum{}2"

    def test_escaping_backslash(self):
        assert escape_latex_text(r"C:\path") == r"C:\textbackslash{}path"
        assert escape_latex_text("\\") == r"\textbackslash{}"

    def test_non_special_characters_remain_unchanged(self):
        text = "Hello World! 1234 - + = / [ ] ( ) ; : . ,"
        assert escape_latex_text(text) == text


# ===========================================================================
# 2. Formula Verbatim Preservation
# ===========================================================================


class TestFormulaPreservation:

    def test_formula_superscript_subscript_verbatim(self):
        item = _formula_item("x_1^2 + y_1^2")
        assert render_content_item(item) == "$x_1^2 + y_1^2$"

    def test_formula_fraction_integral_verbatim(self):
        item = _formula_item(r"\frac{\partial}{\partial x} \int_0^y f(t)\,dt")
        assert render_content_item(item) == r"$\frac{\partial}{\partial x} \int_0^y f(t)\,dt$"

    def test_formula_greek_verbatim(self):
        item = _formula_item(r"\alpha \beta \gamma \theta \pi")
        assert render_content_item(item) == r"$\alpha \beta \gamma \theta \pi$"

    def test_formula_arrows_verbatim(self):
        item = _formula_item(r"A \rightarrow B \rightleftharpoons C")
        assert render_content_item(item) == r"$A \rightarrow B \rightleftharpoons C$"


# ===========================================================================
# 3–4. Inline vs Display Delimiters
# ===========================================================================


class TestFormulaDelimiters:

    def test_standard_formula_default_is_inline(self):
        item = _formula_item("E = mc^2")
        assert render_content_item(item) == "$E = mc^2$"

    def test_already_delimited_double_dollar_is_verbatim(self):
        item = _formula_item("$$E = mc^2$$")
        assert render_content_item(item) == "$$E = mc^2$$"

    def test_already_delimited_brackets_is_verbatim(self):
        item = _formula_item(r"\[ \int x\,dx \]")
        assert render_content_item(item) == r"\[ \int x\,dx \]"

    def test_already_delimited_equation_is_verbatim(self):
        item = _formula_item(r"\begin{equation} y = mx + c \end{equation}")
        assert render_content_item(item) == r"\begin{equation} y = mx + c \end{equation}"

    def test_empty_formula_is_empty_string(self):
        assert render_content_item(_formula_item("")) == ""


# ===========================================================================
# 5. Diagram References
# ===========================================================================


class TestDiagramReferences:

    def test_diagram_generates_relative_includegraphics(self):
        item = _diagram_item("diagram_001")
        assert render_content_item(item) == r"\includegraphics[width=0.8\textwidth]{images/diagram_001.png}"

    def test_diagram_id_underscore_is_never_escaped(self):
        """Underscores inside graphicx commands must NOT be escaped."""
        item = _diagram_item("diagram_abc_123")
        rendered = render_content_item(item)
        assert r"images/diagram_abc_123.png" in rendered
        assert r"diagram\_abc\_123" not in rendered


# ===========================================================================
# 6. Preamble Rendering
# ===========================================================================


class TestPreambleRendering:

    def test_preamble_items_rendered_at_start(self):
        doc = StructuredDocument(pages=1)
        doc.preamble = [_text_item("EXAM TITLE"), _diagram_item("diagram_title")]
        doc.questions = []
        latex = generate_latex(doc)
        # Verify preamble text appears inside document body
        assert "EXAM TITLE" in latex
        assert r"\includegraphics[width=0.8\textwidth]{images/diagram_title.png}" in latex
        # Preamble must appear before \begin{document} terminates
        body_idx = latex.find(r"\begin{document}")
        preamble_idx = latex.find("EXAM TITLE")
        assert preamble_idx > body_idx


# ===========================================================================
# 7–8. MCQ/Question Structure & Custom Labels
# ===========================================================================


class TestQuestionMCQStructure:

    def test_question_uses_custom_item_label(self):
        q = StructuredQuestion(
            question_number="Q3:",
            body=(_text_item("What is the speed of light?"),),
            options=(),
        )
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)
        assert r"\item[\textbf{Q3:}]" in latex
        assert "What is the speed of light?" in latex

    def test_numeric_question_adds_dot_to_label(self):
        q = StructuredQuestion(
            question_number="5",
            body=(_text_item("Explain photosynthesis."),),
            options=(),
        )
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)
        assert r"\item[\textbf{5.}]" in latex

    def test_option_formatting_parentheses(self):
        opt = _option("A", "(A) Hydrogen")
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)
        # Parentheses style (A) preserved, duplicate prefix stripped
        assert r"\item[\textbf{(A)}]" in latex
        assert "Hydrogen" in latex
        assert "(A) Hydrogen" not in latex

    def test_option_formatting_closing_paren(self):
        opt = _option("B", "B) Helium")
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)
        assert r"\item[\textbf{B)}]" in latex
        assert "Helium" in latex
        assert "B) Helium" not in latex

    def test_option_formatting_period(self):
        opt = _option("C", "C. Lithium")
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)
        assert r"\item[\textbf{C.}]" in latex
        assert "Lithium" in latex
        assert "C. Lithium" not in latex

    def test_option_formatting_fallback(self):
        """If option first item is not text, fall back to standard labeling."""
        opt = StructuredOption(label="D", body=(_diagram_item("diagram_opt"),))
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)
        assert r"\item[\textbf{D.}]" in latex
        assert r"\includegraphics[width=0.8\textwidth]{images/diagram_opt.png}" in latex


# ===========================================================================
# 9. Diagram Position
# ===========================================================================


class TestDiagramPositioning:

    def test_diagram_between_question_text_and_options(self):
        """Diagram placed in body must render after question text and before enumerate."""
        q = StructuredQuestion(
            question_number="1",
            body=(_text_item("Look at the chart:"), _diagram_item("diagram_chart")),
            options=(_option("A", "High"), _option("B", "Low")),
        )
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)

        idx_text = latex.find("Look at the chart:")
        idx_diag = latex.find("diagram_chart")
        idx_enum = latex.find(r"\begin{enumerate}", idx_text)

        assert idx_text < idx_diag < idx_enum

    def test_diagram_inside_option(self):
        """Diagram embedded in option body must render inside that option's item block."""
        diag = _diagram_item("diagram_inside_opt")
        opt = _option("A", "Graph: ", [diag])
        q = StructuredQuestion(question_number="1", body=(), options=(opt,))
        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)

        idx_opt_start = latex.find(r"\item[\textbf{(A)}]")
        idx_diag = latex.find("diagram_inside_opt")
        idx_opt_end = latex.find(r"\item[\textbf{B.}]") # next item / enumerate end

        assert idx_opt_start < idx_diag
        if idx_opt_end != -1:
            assert idx_diag < idx_opt_end


# ===========================================================================
# 10. Ordering
# ===========================================================================


class TestQuestionsOrdering:

    def test_multiple_questions_ordered_correctly(self):
        q1 = StructuredQuestion(question_number="1", body=(_text_item("First question"),), options=())
        q2 = StructuredQuestion(question_number="2", body=(_text_item("Second question"),), options=())
        q3 = StructuredQuestion(question_number="3", body=(_text_item("Third question"),), options=())

        doc = StructuredDocument(pages=1)
        doc.questions = [q1, q2, q3]
        latex = generate_latex(doc)

        idx1 = latex.find("First question")
        idx2 = latex.find("Second question")
        idx3 = latex.find("Third question")

        assert idx1 < idx2 < idx3


# ===========================================================================
# 11. Empty Document
# ===========================================================================


class TestEmptyDocument:

    def test_empty_document_generates_valid_structure(self):
        doc = StructuredDocument(pages=0)
        latex = generate_latex(doc)
        assert r"\documentclass{article}" in latex
        assert r"\begin{document}" in latex
        assert r"\end{document}" in latex
        # No enumerate or preamble tags if not present
        assert r"\begin{enumerate}" not in latex


# ===========================================================================
# 12. Special/Scientific Content
# ===========================================================================


class TestScienceContent:

    def test_science_text_escaped_but_formulas_verbatim(self):
        """Mixed chemistry text and formula preserves science formula markup."""
        # Text contains '&' and '%'; formula contains subscripts and chemical arrow
        text_ci = _text_item("Reaction yield & percentage: 98% yield.")
        formula_ci = _formula_item(r"H_2 + O_2 \rightarrow H_2O")
        q = StructuredQuestion(question_number="1", body=(text_ci, formula_ci), options=())

        doc = StructuredDocument(pages=1)
        doc.questions = [q]
        latex = generate_latex(doc)

        # Escaped text
        assert r"yield \& percentage" in latex
        assert r"98\% yield" in latex
        # Verbatim formula
        assert r"$H_2 + O_2 \rightarrow H_2O$" in latex
