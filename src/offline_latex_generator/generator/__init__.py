"""LaTeX generation and compilation package — Phase 16 & 17.

Provides:
- escape_latex_text  : escapes special control characters in plain text.
- render_content_item: converts a single ContentItem to LaTeX string.
- generate_latex     : converts a StructuredDocument to compilable LaTeX string.
- LaTeXValidationError      : validation error DTO.
- validate_latex_syntax     : static syntax analysis.
- validate_latex_compilation: subprocess compilation check with diagram placeholders.
- validate_latex            : hybrid static + compilation validation.
"""

from offline_latex_generator.generator.latex_generator import (
    escape_latex_text,
    render_content_item,
    generate_latex,
)
from offline_latex_generator.generator.validator import (
    LaTeXValidationError,
    validate_latex_syntax,
    validate_latex_compilation,
    validate_latex,
)

__all__ = [
    # Generator
    "escape_latex_text",
    "render_content_item",
    "generate_latex",
    # Validator
    "LaTeXValidationError",
    "validate_latex_syntax",
    "validate_latex_compilation",
    "validate_latex",
]

