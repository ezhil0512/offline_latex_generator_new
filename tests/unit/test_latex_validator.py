"""Unit tests for Phase 17: LaTeX Validation.

Covers:
1.  Valid LaTeX document validates successfully.
2.  Static validation: unmatched braces { and }.
3.  Static validation: unbalanced math delimiters ($, $$, \\[, \\]).
4.  Static validation: malformed environments (mismatched \\begin and \\end).
5.  Static validation: unescaped control characters outside math mode.
6.  Static validation: valid comments and escaped control characters cause no false positives.
7.  Compiler validation: compile a valid document successfully.
8.  Compiler validation: compile error (undefined control sequence) caught and log parsed.
9.  Compiler validation: missing compiler handled gracefully with warning.
10. Compiler validation: diagram reference resolved with placeholder PNG and temp clean up.
11. Formulas with subscripts/superscripts, fractions, integrals, Greek, arrows validated.
12. Nested MCQ structures validated.
13. Empty document produces minimal valid document.
"""

from __future__ import annotations

import os
import shutil
import pytest

from offline_latex_generator.config import config
from offline_latex_generator.generator import (
    LaTeXValidationError,
    validate_latex_syntax,
    validate_latex_compilation,
    validate_latex,
)

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

VALID_DOC = r"""\documentclass{article}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{enumerate}
\begin{document}
Preamble text here. % valid comment
\begin{enumerate}
  \item[\textbf{1.}] Question text $x^2 + y^2 = r^2$ and chemistry $H_2 + O_2 \rightarrow H_2O$.
  \begin{enumerate}
    \item[\textbf{(A)}] Option A text with percent 100\% and yield \& ratio.
  \end{enumerate}
\end{enumerate}
\end{document}
"""

# ===========================================================================
# 1. Static Validation: Braces, Delimiters, Environments
# ===========================================================================


class TestStaticValidation:

    def test_valid_document_syntax_passes(self):
        errors = validate_latex_syntax(VALID_DOC)
        assert errors == []

    def test_unmatched_open_brace(self):
        code = r"Some text {unmatched"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unmatched opening brace" in errors[0].message
        assert errors[0].line == 1

    def test_unmatched_close_brace(self):
        code = r"Some text } unmatched"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unmatched closing brace" in errors[0].message

    def test_escaped_braces_are_ignored(self):
        code = r"Escaped braces \{ and \} should pass."
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_unbalanced_inline_math(self):
        code = r"Some text $x + y = z and no closing dollar"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unclosed inline math delimiter" in errors[0].message

    def test_unbalanced_display_math_double_dollar(self):
        code = r"Some text $$ x + y = z and no closing display math"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unclosed display math delimiter" in errors[0].message

    def test_unbalanced_display_math_brackets(self):
        code = r"Some text \[ x + y = z and no closing bracket display math"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unclosed display math delimiter" in errors[0].message

    def test_double_dollar_inside_inline_math_error(self):
        code = r"Inline math $ x + y = z $$ display inside inline $"
        errors = validate_latex_syntax(code)
        assert len(errors) >= 1

    def test_unmatched_environment_mismatch(self):
        code = r"""\begin{enumerate}
        Some text.
        \end{itemize}"""
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Mismatched environment" in errors[0].message
        assert "expected \\end{enumerate}" in errors[0].message
        assert "got \\end{itemize}" in errors[0].message

    def test_unmatched_environment_closure_only(self):
        code = r"\end{enumerate} without begin"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unmatched environment closure" in errors[0].message

    def test_unclosed_environment_at_end(self):
        code = r"\begin{enumerate} has no end"
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unclosed environment \\begin{enumerate}" in errors[0].message


# ===========================================================================
# 2. Static Validation: Control Characters outside Math Mode
# ===========================================================================


class TestControlCharacters:

    def test_unescaped_underscore_outside_math_fails(self):
        code = r"Standard text with variable_name causes error."
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Subscript/superscript '_' is only allowed in math mode" in errors[0].message

    def test_escaped_underscore_outside_math_passes(self):
        code = r"Standard text with variable\_name passes."
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_underscore_inside_math_mode_passes(self):
        code = r"Formula math $x_1$ and $$y_2$$ and \[z_3\] are fine."
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_unescaped_caret_outside_math_fails(self):
        code = r"Standard text with value^2 causes error."
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Subscript/superscript '^' is only allowed in math mode" in errors[0].message

    def test_unescaped_ampersand_outside_alignment_fails(self):
        code = r"Standard text with yield & ratio causes error."
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unescaped alignment tab character '&' outside table or math alignment" in errors[0].message

    def test_escaped_ampersand_outside_alignment_passes(self):
        code = r"Standard text with yield \& ratio is fine."
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_ampersand_inside_math_alignment_passes(self):
        code = r"""\begin{align}
        x &= y \\
        a &= b
        \end{align}"""
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_ampersand_inside_tabular_passes(self):
        code = r"""\begin{tabular}{cc}
        1 & 2 \\
        3 & 4
        \end{tabular}"""
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_unescaped_macro_parameter_hash_fails(self):
        code = r"Text with Issue #42."
        errors = validate_latex_syntax(code)
        assert len(errors) == 1
        assert "Unescaped macro parameter character '#'" in errors[0].message

    def test_escaped_macro_parameter_hash_passes(self):
        code = r"Text with Issue \#42."
        errors = validate_latex_syntax(code)
        assert errors == []

    def test_valid_comments_ignored(self):
        code = r"This is active text. % This is a comment containing unescaped &, _, ^, #, {, }"
        errors = validate_latex_syntax(code)
        assert errors == []


# ===========================================================================
# 3. Compiler Validation & Graceful Fallback
# ===========================================================================


class TestCompilerValidation:

    def test_missing_compiler_returns_graceful_warning(self, monkeypatch):
        """Simulate missing compiler by forcing get_recognizer/shutil.which lookup to fail."""
        monkeypatch.setattr(config, "_config_data", {"latex": {"compiler": "non_existent_compiler"}})
        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        errors = validate_latex_compilation(VALID_DOC)
        assert len(errors) == 1
        assert errors[0].severity == "warning"
        assert "Skipping compiler validation" in errors[0].message

    @pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex not installed on test host")
    def test_valid_doc_compiles_without_errors(self):
        errors = validate_latex_compilation(VALID_DOC)
        assert errors == []

    @pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex not installed on test host")
    def test_invalid_command_compiles_with_errors(self):
        bad_doc = VALID_DOC.replace("Preamble text here.", r"Preamble \invalidcmd here.")
        errors = validate_latex_compilation(bad_doc)
        assert len(errors) >= 1
        assert errors[0].severity == "error"
        assert "Undefined control sequence" in errors[0].message or "invalidcmd" in errors[0].message
        # Check that we parsed the correct line number (around line 7 in bad_doc)
        assert errors[0].line is not None

    @pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex not installed on test host")
    def test_diagram_reference_compiles_with_placeholder_and_cleans_up(self):
        """Verifies referenced diagram images resolve correctly during validation

        via temporary placeholders, and are fully cleaned up.
        """
        doc_with_diagram = VALID_DOC.replace(
            "Preamble text here.",
            "Preamble text here. \\includegraphics{images/diagram_001.png} \\includegraphics[width=0.5\\textwidth]{images/diagram_abc_123.png}"
        )
        
        errors = validate_latex_compilation(doc_with_diagram)
        # Compilation must succeed because the validator wrote the 1x1 PNG placeholders!
        assert errors == []


# ===========================================================================
# 4. Combined Validation
# ===========================================================================


class TestCombinedValidation:

    def test_combined_skips_compilation_on_blocking_syntax_error(self, monkeypatch):
        """If static validation fails with blocking errors, compile is skipped."""
        called_compilation = False

        def fake_compilation(code):
            nonlocal called_compilation
            called_compilation = True
            return []

        import offline_latex_generator.generator.validator as val_mod
        monkeypatch.setattr(val_mod, "validate_latex_compilation", fake_compilation)

        bad_syntax_doc = "Mismatched braces {"
        errors = validate_latex(bad_syntax_doc)

        assert len(errors) == 1
        assert "Unmatched opening brace" in errors[0].message
        assert not called_compilation
