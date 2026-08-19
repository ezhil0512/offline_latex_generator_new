"""LaTeX generation implementation — Phase 16.

Provides character escaping for normal text, rendering of content items
(preserving formula LaTeX verbatim and outputting relative diagram references),
and assembly of compile-ready LaTeX documents.
"""

from __future__ import annotations

import re
from typing import Sequence, Union

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)

# ---------------------------------------------------------------------------
# Character escaping
# ---------------------------------------------------------------------------

_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex_text(text: str) -> str:
    """Escape LaTeX special control characters in a normal text string.

    Single-pass mapping to avoid double-escaping or corrupting already
    replaced sequences.
    """
    return "".join(_ESCAPE_MAP.get(c, c) for c in text)


# ---------------------------------------------------------------------------
# ContentItem rendering
# ---------------------------------------------------------------------------


def render_content_item(item: ContentItem) -> str:
    """Render a single ContentItem to its corresponding LaTeX markup.

    - "text"   : escaped text.
    - "formula": math formula, wrapped in inline math $...$ unless already delimited.
    - "diagram": relative image reference \\includegraphics{images/diagram_NNN.png}.
    """
    if item.kind == "text":
        return escape_latex_text(item.text or "")

    if item.kind == "formula":
        latex = (item.latex or "").strip()
        if not latex:
            return ""
        # Check if already delimited with display math or environment delimiters
        if (
            latex.startswith("$$") and latex.endswith("$$")
        ) or (
            latex.startswith(r"\[") and latex.endswith(r"\]")
        ) or (
            latex.startswith(r"\begin{") and latex.endswith(r"}")
        ):
            return latex
        return f"${latex}$"

    if item.kind == "diagram":
        d_id = item.diagram_id or "diagram_000"
        return rf"\includegraphics[width=0.8\textwidth]{{images/{d_id}.png}}"

    return ""


# ---------------------------------------------------------------------------
# Option and Question rendering
# ---------------------------------------------------------------------------

_RE_STRIP_LABEL = re.compile(
    r"^\s*(?:\([A-Za-z]\)|[A-Za-z][).])\s*",
)


def _render_option(opt: StructuredOption) -> str:
    """Render a StructuredOption, stripping duplicate label prefixes if present.

    Regardless of the OCR-detected delimiter style ((a), a), a.), the option label
    is always emitted in the canonical parenthesized form (label) so that all options
    in the generated LaTeX are consistently styled.
    """
    # Canonical label: always parenthesized, original case preserved
    label_fmt = f"({opt.label})"

    if not opt.body:
        return rf"\item[{label_fmt}]"

    first_item = opt.body[0]
    if first_item.kind == "text" and first_item.text:
        cleaned_text = _RE_STRIP_LABEL.sub("", first_item.text)
        cleaned_item = ContentItem(
            kind="text",
            text=cleaned_text,
            latex=first_item.latex,
            diagram_id=first_item.diagram_id,
            bbox=first_item.bbox,
            block_index=first_item.block_index,
            source_page=first_item.source_page,
            confidence=first_item.confidence,
        )
        rendered_items = [render_content_item(cleaned_item)] + [
            render_content_item(ci) for ci in opt.body[1:]
        ]
        body_str = " ".join(parts for parts in rendered_items if parts).strip()
        return rf"\item[{label_fmt}] {body_str}"

    # Fallback if the first item is a formula or diagram
    body_str = " ".join(
        parts for parts in (render_content_item(ci) for ci in opt.body) if parts
    ).strip()
    return rf"\item[{label_fmt}] {body_str}"


def _render_body(items: Sequence[ContentItem]) -> str:
    """Render a sequence of ContentItems (body or preamble) into a space-joined string."""
    parts = []
    for item in items:
        rendered = render_content_item(item)
        if not rendered:
            continue
        parts.append(rendered)
    return " ".join(parts)


def _render_question(q: StructuredQuestion) -> str:
    """Render a StructuredQuestion into a LaTeX item block with optional nested options."""
    body_str = _render_body(q.body)
    question_label = q.question_number
    # Format custom label cleanly
    if question_label.isdigit():
        q_item = rf"\item[{question_label}.] {body_str}"
    else:
        # If it already has formatting (e.g. "Q1:"), keep as-is
        q_item = rf"\item[{question_label}] {body_str}"

    if not q.options:
        return q_item

    # Add options block
    options_lines = [r"  \begin{enumerate}"]
    for opt in q.options:
        options_lines.append(f"    {_render_option(opt)}")
    options_lines.append(r"  \end{enumerate}")
    options_str = "\n".join(options_lines)

    return f"{q_item}\n{options_str}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_latex(doc: StructuredDocument) -> str:
    """Generate a fully compile-ready LaTeX document from a StructuredDocument.

    Args:
        doc: The assembled StructuredDocument from Phase 15.

    Returns:
        A compilable LaTeX document string.
    """
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{graphicx}",
        r"\usepackage{amsmath}",
        r"\usepackage{amssymb}",
        r"\usepackage{enumitem}",
        "",
        r"\begin{document}",
    ]

    # Render preamble if present
    if doc.preamble:
        preamble_str = _render_body(doc.preamble)
        if preamble_str:
            lines.append(preamble_str)
            lines.append("")

    # Render questions if present
    if doc.questions:
        lines.append(r"\begin{enumerate}")
        for q in doc.questions:
            lines.append(_render_question(q))
        lines.append(r"\end{enumerate}")

    lines.append(r"\end{document}")
    lines.append("")  # trailing newline

    return "\n".join(lines)


__all__ = [
    "escape_latex_text",
    "render_content_item",
    "generate_latex",
]
