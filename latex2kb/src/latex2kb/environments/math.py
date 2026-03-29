"""Math environment converter: equation, align, multline, gather, etc."""

from __future__ import annotations


# Math environments whose content should be preserved as-is in $$ blocks
DISPLAY_MATH_ENVS = {
    'equation', 'equation*',
    'align', 'align*',
    'multline', 'multline*',
    'gather', 'gather*',
    'flalign', 'flalign*',
    'eqnarray', 'eqnarray*',
}

# Math sub-environments that stay inside $$ blocks
MATH_SUB_ENVS = {
    'split', 'cases', 'aligned', 'gathered',
    'pmatrix', 'bmatrix', 'vmatrix', 'Bmatrix', 'Vmatrix',
    'array', 'matrix', 'smallmatrix',
}

ALL_MATH_ENVS = DISPLAY_MATH_ENVS | MATH_SUB_ENVS


def convert_display_math(env_name: str, inner_latex: str, label: str | None = None) -> str:
    """Convert a display math environment to Markdown.

    Preserves the LaTeX content verbatim inside $$ blocks.
    For environments like align that have their own structure, we keep
    the \\begin/\\end wrapper inside the $$ block.
    """
    parts = []

    # Add anchor for labeled equations
    if label:
        anchor = label.replace(':', '-')
        parts.append(f'<a id="{anchor}"></a>')
        parts.append('')

    # For simple equation environments, just use $$ wrapper
    if env_name in ('equation', 'equation*'):
        # Strip the label from inner content (already extracted)
        inner = _strip_label(inner_latex).strip()
        parts.append('$$')
        parts.append(inner)
        parts.append('$$')
    else:
        # For align, multline, etc., keep the environment wrapper
        inner = _strip_label(inner_latex).strip()
        parts.append('$$')
        parts.append(f'\\begin{{{env_name}}}')
        parts.append(inner)
        parts.append(f'\\end{{{env_name}}}')
        parts.append('$$')

    return '\n'.join(parts)


def convert_inline_math(content: str) -> str:
    """Convert inline math — just preserve as-is with $ delimiters."""
    return f'${content}$'


def _strip_label(latex: str) -> str:
    """Remove \\label{...} from math content (label is handled separately)."""
    import re
    return re.sub(r'\\label\{[^}]*\}', '', latex)
