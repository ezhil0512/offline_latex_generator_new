"""HTML preview renderer — Phase 18.

Converts a :class:`~offline_latex_generator.structurer.models.StructuredDocument`
to a fully self-contained HTML string for offline local preview.

Design decisions
----------------
* **Input:**  ``StructuredDocument`` (Phase 15 canonical IR).
* **Output:** UTF-8 HTML string; no files are written to disk.
* **Text safety:** ``html.escape()`` is applied to every plain-text
  ``ContentItem``; formula and diagram items are never HTML-escaped.
* **Formula preservation:** formula ``latex`` strings are output verbatim
  inside ``\\( ... \\)`` (inline) or as-is when they already carry a
  display delimiter (``\\[``, ``$$``, ``\\begin{``).
* **Diagram embedding:** PIL images stored in ``StructuredDocument.diagrams``
  are converted to PNG Base64 data URLs in memory; zero filesystem writes.
* **Math rendering:** HTML references local KaTeX assets at
  ``/static/katex/`` (supplied separately; not downloaded by this module).
  If assets are absent the page still renders cleanly — formulas appear
  as raw ``\\(...\\)`` strings rather than typeset symbols.
* **KaTeX delimiters configured:**
  ``$...$`` and ``\\(...\\)`` for inline,
  ``$$...$$`` and ``\\[...\\]`` for display.
"""

from __future__ import annotations

import base64
import html
import io
from typing import Dict, Sequence

from PIL import Image

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)

# ---------------------------------------------------------------------------
# Display-delimiter detection helpers
# ---------------------------------------------------------------------------

_DISPLAY_PREFIXES = (r"\[", "$$", r"\begin{")


def _is_display_delimited(latex: str) -> bool:
    """Return True if *latex* already carries its own display delimiters."""
    s = latex.strip()
    return any(s.startswith(prefix) for prefix in _DISPLAY_PREFIXES)


# ---------------------------------------------------------------------------
# PIL → Base64 data URL
# ---------------------------------------------------------------------------


def _pil_to_data_url(img: Image.Image) -> str:
    """Convert a PIL image to a PNG Base64 data URL (in memory, no disk write)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# ContentItem renderer
# ---------------------------------------------------------------------------


def _render_content_item(
    item: ContentItem,
    diagrams: Dict[str, Image.Image],
) -> str:
    """Render a single ContentItem to an HTML fragment.

    Parameters
    ----------
    item:
        The content item to render.
    diagrams:
        Mapping of diagram IDs to in-memory PIL images, taken from
        ``StructuredDocument.diagrams``.

    Returns
    -------
    str
        An HTML fragment (no surrounding ``<p>`` or ``<div>``).
    """
    if item.kind == "text":
        escaped = html.escape(item.text or "")
        return f'<span class="text-content">{escaped}</span>'

    if item.kind == "formula":
        latex = item.latex or ""
        if _is_display_delimited(latex):
            # Already carries display delimiters — output verbatim so KaTeX
            # auto-render recognises them without double-wrapping.
            return f'<span class="formula-display">{latex}</span>'
        # Default: inline formula — wrap in \( ... \)
        return f'<span class="formula-inline">\\({latex}\\)</span>'

    if item.kind == "diagram":
        diag_id = item.diagram_id or ""
        img = diagrams.get(diag_id)
        if img is not None:
            data_url = _pil_to_data_url(img)
            return (
                f'<img class="diagram" src="{data_url}"'
                f' alt="{html.escape(diag_id)}" />'
            )
        # Diagram ID not found in the document's image map → safe placeholder
        label = html.escape(diag_id) if diag_id else "unknown"
        return f'<span class="diagram-missing">[diagram: {label}]</span>'

    # Unrecognised kind — render nothing (future-proof guard)
    return ""


# ---------------------------------------------------------------------------
# Sequence renderer
# ---------------------------------------------------------------------------


def _render_content_items(
    items: Sequence[ContentItem],
    diagrams: Dict[str, Image.Image],
) -> str:
    """Render an ordered sequence of ContentItems, preserving their order."""
    return "\n".join(_render_content_item(item, diagrams) for item in items)


# ---------------------------------------------------------------------------
# Option renderer
# ---------------------------------------------------------------------------


def _render_option(
    opt: StructuredOption,
    diagrams: Dict[str, Image.Image],
) -> str:
    """Render a single MCQ option."""
    label_html = f'<span class="option-label">{html.escape(opt.label)}.</span>'
    body_html = _render_content_items(opt.body, diagrams)
    return (
        f'<div class="option">\n'
        f"  {label_html}\n"
        f'  <span class="option-body">{body_html}</span>\n'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Question renderer
# ---------------------------------------------------------------------------


def _render_question(
    question: StructuredQuestion,
    diagrams: Dict[str, Image.Image],
) -> str:
    """Render a complete question (stem + options)."""
    number_html = (
        f'<div class="question-number">'
        f"{html.escape(str(question.question_number))}."
        f"</div>"
    )
    body_html = _render_content_items(question.body, diagrams)
    body_block = f'<div class="question-body">{body_html}</div>'

    options_html = ""
    if question.options:
        option_items = "\n".join(
            _render_option(opt, diagrams) for opt in question.options
        )
        options_html = f'<div class="options">\n{option_items}\n</div>'

    return (
        f'<div class="question">\n'
        f"  {number_html}\n"
        f"  {body_block}\n"
        f"  {options_html}\n"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# HTML head
# ---------------------------------------------------------------------------


def _html_head() -> str:
    """Return the full <head> block.

    KaTeX assets are referenced at ``/static/katex/``.
    If these files are absent the page still renders; formulas appear as
    raw ``\\(…\\)`` strings rather than typeset symbols.
    """
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Question Paper Preview</title>
  <!-- KaTeX for offline math rendering (supply assets at /static/katex/) -->
  <link rel="stylesheet" href="/static/katex/katex.min.css" />
  <style>
    body {
      font-family: Georgia, "Times New Roman", Times, serif;
      max-width: 860px;
      margin: 2rem auto;
      padding: 0 1rem;
      line-height: 1.6;
      color: #1a1a1a;
    }
    h1.doc-title {
      font-size: 1.4rem;
      text-align: center;
      margin-bottom: 1.5rem;
    }
    .question {
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid #e0e0e0;
    }
    .question-number {
      font-weight: bold;
      font-size: 1.05rem;
      margin-bottom: 0.3rem;
    }
    .question-body {
      margin-bottom: 0.6rem;
    }
    .options {
      margin-top: 0.5rem;
      margin-left: 1.5rem;
    }
    .option {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.35rem;
      align-items: flex-start;
    }
    .option-label {
      font-weight: bold;
      min-width: 1.8rem;
      flex-shrink: 0;
    }
    .option-body {
      flex: 1;
    }
    .text-content {
      /* plain text — inherits body font */
    }
    .formula-inline,
    .formula-display {
      font-family: "KaTeX_Main", Georgia, serif;
    }
    .diagram {
      max-width: 100%;
      height: auto;
      margin: 0.5rem 0;
      display: block;
      border: 1px solid #ddd;
      border-radius: 4px;
    }
    .diagram-missing {
      color: #888;
      font-style: italic;
      font-size: 0.9rem;
    }
    .preamble {
      margin-bottom: 1.5rem;
      padding: 0.8rem;
      background: #f8f8f8;
      border-left: 3px solid #aaa;
    }
  </style>
</head>"""


# ---------------------------------------------------------------------------
# HTML foot (KaTeX scripts)
# ---------------------------------------------------------------------------


def _html_foot() -> str:
    """Return the closing script block and </body></html>."""
    return """\
  <!-- KaTeX auto-render (requires /static/katex/ assets to be available) -->
  <script src="/static/katex/katex.min.js"></script>
  <script src="/static/katex/contrib/auto-render.min.js"></script>
  <script>
    document.addEventListener("DOMContentLoaded", function () {
      if (typeof renderMathInElement === "function") {
        renderMathInElement(document.body, {
          delimiters: [
            { left: "$$",   right: "$$",   display: true  },
            { left: "\\\\[",  right: "\\\\]",  display: true  },
            { left: "$",    right: "$",    display: false },
            { left: "\\\\(", right: "\\\\)", display: false }
          ],
          throwOnError: false
        });
      }
    });
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_html_preview(doc: StructuredDocument) -> str:
    """Convert a StructuredDocument to a self-contained HTML preview string.

    Parameters
    ----------
    doc:
        The structured document produced by Phase 15.

    Returns
    -------
    str
        A complete UTF-8 HTML document string.  No files are written to
        disk.  Diagram PIL images are embedded as Base64 data URLs.

    Notes
    -----
    The returned HTML references KaTeX assets at ``/static/katex/``.
    If those files are not served by the host application, the page still
    renders correctly — formulas are visible as raw ``\\(…\\)`` strings.
    """
    diagrams = doc.diagrams  # Dict[str, PIL.Image.Image]

    parts: list[str] = [_html_head(), "<body>"]

    # --- Preamble (content before the first question) ---------------------
    if doc.preamble:
        preamble_html = _render_content_items(doc.preamble, diagrams)
        parts.append(f'<div class="preamble">\n{preamble_html}\n</div>')

    # --- Questions ---------------------------------------------------------
    for question in doc.questions:
        parts.append(_render_question(question, diagrams))

    # --- Foot (scripts + close tags) --------------------------------------
    parts.append(_html_foot())

    return "\n".join(parts)


__all__ = ["generate_html_preview"]
