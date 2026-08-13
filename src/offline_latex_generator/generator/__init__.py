"""LaTeX generation and compilation package — Phase 16.

Provides:
- escape_latex_text  : escapes special control characters in plain text.
- render_content_item: converts a single ContentItem to LaTeX string.
- generate_latex     : converts a StructuredDocument to compilable LaTeX string.
"""

from offline_latex_generator.generator.latex_generator import (
    escape_latex_text,
    render_content_item,
    generate_latex,
)

__all__ = [
    "escape_latex_text",
    "render_content_item",
    "generate_latex",
]
