"""LaTeX validation package — Phase 17.

Provides hybrid LaTeX validation:
- Static syntax validation (linter) for unmatched brackets, unbalanced math delimiters,
  unbalanced environments, and unescaped special characters.
- Compiler-based compilation validation using local pdflatex (or configured compiler)
  in a temporary workspace, supporting referenced diagrams using temporary PNG placeholders.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from offline_latex_generator.config import config


# ---------------------------------------------------------------------------
# DTO Definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaTeXValidationError:
    """Represents a single syntax or compilation error/warning.

    Attributes
    ----------
    severity:
        "error"   — block compiler compilation.
        "warning" — compiler warning or syntax concern.
    message:
        Human-readable explanation of the validation failure.
    line:
        One-based line number where the issue occurs, if known.
    column:
        One-based column offset where the issue occurs, if known.
    """

    severity: Literal["error", "warning"]
    message: str
    line: Optional[int] = None
    column: Optional[int] = None


# ---------------------------------------------------------------------------
# Static Syntax Validation
# ---------------------------------------------------------------------------


def _is_escaped(s: str, idx: int) -> bool:
    """Check if character at index in string s is escaped by odd number of backslashes."""
    count = 0
    i = idx - 1
    while i >= 0 and s[i] == "\\":
        count += 1
        i -= 1
    return count % 2 == 1


def validate_latex_syntax(latex_code: str) -> List[LaTeXValidationError]:
    """Perform fast, in-memory static linting on a LaTeX code string.

    Checks:
    - Balanced curly braces { and }.
    - Balanced inline ($) and display ($$, \\[ \\]) math delimiters.
    - Balanced environment blocks (\\begin{env} ... \\end{env}).
    - Unescaped control characters (_, ^, &, #) outside math/alignment environments.
    """
    if not latex_code:
        return []

    # 1. Clean lines by removing comments (unescaped %) to prevent false positives
    clean_lines: List[str] = []
    for line in latex_code.splitlines():
        comment_start = -1
        for idx, char in enumerate(line):
            if char == "%" and not _is_escaped(line, idx):
                comment_start = idx
                break
        if comment_start != -1:
            clean_lines.append(line[:comment_start])
        else:
            clean_lines.append(line)

    clean_text = "\n".join(clean_lines)

    # 2. Character-by-character scan
    i = 0
    n = len(clean_text)
    line_num = 1
    col_num = 1

    errors: List[LaTeXValidationError] = []
    brace_stack: List[tuple[int, int]] = []

    in_inline = False
    inline_start: Optional[tuple[int, int]] = None

    in_display_dollar = False
    display_dollar_start: Optional[tuple[int, int]] = None

    in_display_bracket = False
    display_bracket_start: Optional[tuple[int, int]] = None

    env_stack: List[tuple[str, int, int]] = []

    def is_in_math_mode() -> bool:
        if in_inline or in_display_dollar or in_display_bracket:
            return True
        math_envs = {
            "equation",
            "equation*",
            "align",
            "align*",
            "gather",
            "gather*",
            "multline",
            "multline*",
            "array",
        }
        if env_stack:
            if env_stack[-1][0] in math_envs:
                return True
        return False

    def is_in_alignment_mode() -> bool:
        align_envs = {
            "tabular",
            "array",
            "align",
            "align*",
            "matrix",
            "pmatrix",
            "bmatrix",
            "vmatrix",
            "Vmatrix",
        }
        if env_stack:
            if env_stack[-1][0] in align_envs:
                return True
        return False

    while i < n:
        char = clean_text[i]

        if char == "\n":
            line_num += 1
            col_num = 1
            i += 1
            continue

        # Check backslashes to determine escaping
        backslashes = 0
        k = i - 1
        while k >= 0 and clean_text[k] == "\\":
            backslashes += 1
            k -= 1
        escaped = backslashes % 2 == 1

        if not escaped:
            if char == "{":
                brace_stack.append((line_num, col_num))
            elif char == "}":
                if brace_stack:
                    brace_stack.pop()
                else:
                    errors.append(
                        LaTeXValidationError(
                            "error",
                            "Unmatched closing brace '}'",
                            line_num,
                            col_num,
                        )
                    )

            elif char == "$":
                if i + 1 < n and clean_text[i + 1] == "$":
                    # Double dollar display math
                    if in_inline:
                        errors.append(
                            LaTeXValidationError(
                                "error",
                                "Cannot start display math '$$' inside inline math '$'",
                                line_num,
                                col_num,
                            )
                        )
                    else:
                        if in_display_dollar:
                            in_display_dollar = False
                            display_dollar_start = None
                        else:
                            in_display_dollar = True
                            display_dollar_start = (line_num, col_num)
                    i += 2
                    col_num += 2
                    continue
                else:
                    # Single dollar inline math
                    if in_display_dollar or in_display_bracket:
                        errors.append(
                            LaTeXValidationError(
                                "error",
                                "Cannot start inline math '$' inside display math",
                                line_num,
                                col_num,
                            )
                        )
                    else:
                        if in_inline:
                            in_inline = False
                            inline_start = None
                        else:
                            in_inline = True
                            inline_start = (line_num, col_num)

            elif char == "\\":
                if i + 1 < n:
                    next_char = clean_text[i + 1]
                    if next_char == "[":
                        if in_inline or in_display_dollar:
                            errors.append(
                                LaTeXValidationError(
                                    "error",
                                    r"Cannot start display math '\[' inside other math mode",
                                    line_num,
                                    col_num,
                                )
                            )
                        elif in_display_bracket:
                            errors.append(
                                LaTeXValidationError(
                                    "error",
                                    r"Nested display math '\[' is not allowed",
                                    line_num,
                                    col_num,
                                )
                            )
                        else:
                            in_display_bracket = True
                            display_bracket_start = (line_num, col_num)
                        i += 2
                        col_num += 2
                        continue
                    elif next_char == "]":
                        if in_display_bracket:
                            in_display_bracket = False
                            display_bracket_start = None
                        else:
                            errors.append(
                                LaTeXValidationError(
                                    "error",
                                    r"Unmatched closing display math '\]'",
                                    line_num,
                                    col_num,
                                )
                            )
                        i += 2
                        col_num += 2
                        continue

                    # Check for environment blocks
                    match_begin = re.match(
                        r"^begin\{([a-zA-Z*]+)\}", clean_text[i + 1 :]
                    )
                    if match_begin:
                        env_name = match_begin.group(1)
                        env_stack.append((env_name, line_num, col_num))
                        skip_len = 1 + len(match_begin.group(0))
                        i += skip_len
                        col_num += skip_len
                        continue

                    match_end = re.match(
                        r"^end\{([a-zA-Z*]+)\}", clean_text[i + 1 :]
                    )
                    if match_end:
                        env_name = match_end.group(1)
                        if env_stack:
                            expected_env, eline, ecol = env_stack[-1]
                            if expected_env == env_name:
                                env_stack.pop()
                            else:
                                errors.append(
                                    LaTeXValidationError(
                                        "error",
                                        f"Mismatched environment: expected \\end{{{expected_env}}} "
                                        f"(started at line {eline}), got \\end{{{env_name}}}",
                                        line_num,
                                        col_num,
                                    )
                                )
                                env_stack.pop()
                        else:
                            errors.append(
                                LaTeXValidationError(
                                    "error",
                                    f"Unmatched environment closure \\end{{{env_name}}}",
                                    line_num,
                                    col_num,
                                )
                            )
                        skip_len = 1 + len(match_end.group(0))
                        i += skip_len
                        col_num += skip_len
                        continue

            elif char in ("_", "^"):
                if not is_in_math_mode():
                    errors.append(
                        LaTeXValidationError(
                            "error",
                            f"Subscript/superscript '{char}' is only allowed in math mode",
                            line_num,
                            col_num,
                        )
                    )

            elif char == "&":
                if not is_in_alignment_mode() and not is_in_math_mode():
                    errors.append(
                        LaTeXValidationError(
                            "error",
                            "Unescaped alignment tab character '&' outside table or math alignment",
                            line_num,
                            col_num,
                        )
                    )

            elif char == "#":
                errors.append(
                    LaTeXValidationError(
                        "error",
                        "Unescaped macro parameter character '#'",
                        line_num,
                        col_num,
                    )
                )

        i += 1
        col_num += 1

    # Check for unclosed structures
    for line_n, col_n in brace_stack:
        errors.append(
            LaTeXValidationError(
                "error", "Unmatched opening brace '{'", line_n, col_n
            )
        )
    if in_inline:
        errors.append(
            LaTeXValidationError(
                "error",
                "Unclosed inline math delimiter '$'",
                inline_start[0],
                inline_start[1],
            )
        )
    if in_display_dollar:
        errors.append(
            LaTeXValidationError(
                "error",
                "Unclosed display math delimiter '$$'",
                display_dollar_start[0],
                display_dollar_start[1],
            )
        )
    if in_display_bracket:
        errors.append(
            LaTeXValidationError(
                "error",
                "Unclosed display math delimiter '\['",
                display_bracket_start[0],
                display_bracket_start[1],
            )
        )
    for env_name, line_n, col_n in env_stack:
        errors.append(
            LaTeXValidationError(
                "error", f"Unclosed environment \\begin{{{env_name}}}", line_n, col_n
            )
        )

    return errors


# ---------------------------------------------------------------------------
# Compiler-based Validation
# ---------------------------------------------------------------------------

_RE_GRAPHICS = re.compile(r"\\includegraphics(?:\[.*?\])?\{images/(diagram_.*?\.png)\}")

def _get_tiny_png() -> bytes:
    """Generate a standard valid 1x1 transparent PNG using PIL to ensure correct headers."""
    import io
    from PIL import Image
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def validate_latex_compilation(
    latex_code: str,
) -> List[LaTeXValidationError]:
    """Compile the LaTeX code in a temporary directory and parse warnings/errors.

    Parses the generated `.log` file for compile errors.
    If the compiler binary is missing, skips validation gracefully and returns a warning.
    Uses temporary transparent placeholder images for all diagram files referenced
    to satisfy compiler dependencies.
    """
    compiler = config.get("latex.compiler", "pdflatex")
    compiler_path = config.get("latex.compiler_path")

    # Resolve compiler binary
    compiler_bin = None
    if compiler_path:
        # Check explicit path
        candidate = os.path.join(compiler_path, compiler)
        if os.path.isfile(candidate) or os.path.isfile(candidate + ".exe"):
            compiler_bin = candidate
    if not compiler_bin:
        # Fallback to system path
        compiler_bin = shutil.which(compiler)

    if not compiler_bin:
        return [
            LaTeXValidationError(
                "warning",
                f"LaTeX compiler '{compiler}' not found on system PATH. "
                "Skipping compiler validation.",
            )
        ]

    errors: List[LaTeXValidationError] = []

    with tempfile.TemporaryDirectory() as temp_path:
        # 1. Detect diagram references and create dummy placeholder PNG files
        diagram_matches = _RE_GRAPHICS.findall(latex_code)
        if diagram_matches:
            images_dir = os.path.join(temp_path, "images")
            os.makedirs(images_dir, exist_ok=True)
            tiny_png_bytes = _get_tiny_png()
            for d_filename in set(diagram_matches):
                with open(os.path.join(images_dir, d_filename), "wb") as pf:
                    pf.write(tiny_png_bytes)

        # 2. Write LaTeX document to disk
        tex_file = os.path.join(temp_path, "document.tex")
        with open(tex_file, "w", encoding="utf-8") as tf:
            tf.write(latex_code)

        # 3. Execute compilation subprocess
        cmd = [compiler_bin, "-interaction=nonstopmode", "document.tex"]
        try:
            result = subprocess.run(
                cmd,
                cwd=temp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=12,
            )
        except subprocess.TimeoutExpired:
            return [
                LaTeXValidationError(
                    "error",
                    f"LaTeX compiler execution timed out after 12 seconds.",
                )
            ]
        except Exception as exc:
            return [
                LaTeXValidationError(
                    "error",
                    f"Subprocess failed to run LaTeX compiler: {exc}",
                )
            ]

        # 4. Parse compile log if return code is non-zero
        if result.returncode != 0:
            log_file = os.path.join(temp_path, "document.log")
            if os.path.isfile(log_file):
                with open(log_file, "r", encoding="utf-8", errors="replace") as lf:
                    lines = lf.readlines()

                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line.startswith("!"):
                        # Found an error message block
                        msg = line[1:].strip()
                        line_num = None
                        # Search forward for line reference (l.XX)
                        for j in range(i + 1, min(i + 6, len(lines))):
                            next_line = lines[j].strip()
                            match = re.match(r"^l\.(\d+)", next_line)
                            if match:
                                line_num = int(match.group(1))
                                break
                        errors.append(
                            LaTeXValidationError(
                                "error", f"LaTeX compile error: {msg}", line_num
                            )
                        )
                    i += 1

            if not errors:
                # Subprocess error fallback
                errors.append(
                    LaTeXValidationError(
                        "error",
                        f"LaTeX compilation failed with exit code {result.returncode}. "
                        f"Stderr: {result.stderr}",
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Combined Validation
# ---------------------------------------------------------------------------


def validate_latex(latex_code: str) -> List[LaTeXValidationError]:
    """Perform hybrid validation on a LaTeX string.

    First executes fast static validation. If blocking static syntax errors are found,
    skips compilation and returns the syntax errors. Otherwise, runs compiler-based
    validation and merges warnings/errors.
    """
    syntax_errors = validate_latex_syntax(latex_code)

    # If syntax errors containing "error" severity are present, do not compile
    has_blocking_errors = any(e.severity == "error" for e in syntax_errors)
    if has_blocking_errors:
        return syntax_errors

    compile_errors = validate_latex_compilation(latex_code)
    return syntax_errors + compile_errors


__all__ = [
    "LaTeXValidationError",
    "validate_latex_syntax",
    "validate_latex_compilation",
    "validate_latex",
]
