"""Algorithm2e environment converter."""

from __future__ import annotations

import re


def convert_algorithm(inner_latex: str, caption: str | None = None, label: str | None = None) -> str:
    """Convert an algorithm2e environment to a Markdown blockquote with pseudo-code.

    Applies line-by-line regex transformations for algorithm2e keywords.
    """
    parts = []

    # Anchor
    if label:
        anchor = label.replace(':', '-')
        parts.append(f'<a id="{anchor}"></a>')
        parts.append('')

    # Caption
    if caption:
        parts.append(f'> **Algorithm**: {caption}')
        parts.append('>')

    # Transform algorithm2e commands
    transformed = _transform_algo_body(inner_latex)

    for line in transformed.split('\n'):
        line = line.rstrip()
        if line:
            parts.append(f'> {line}')
        else:
            parts.append('>')

    return '\n'.join(parts)


_ALGO_RULES: list[tuple[re.Pattern, str]] = [
    # Keywords
    (re.compile(r'\\KwIn\{(.+?)\}', re.DOTALL), r'**Input**: \1'),
    (re.compile(r'\\KwOut\{(.+?)\}', re.DOTALL), r'**Output**: \1'),
    (re.compile(r'\\KwData\{(.+?)\}', re.DOTALL), r'**Data**: \1'),
    (re.compile(r'\\KwResult\{(.+?)\}', re.DOTALL), r'**Result**: \1'),
    (re.compile(r'\\Return\{(.+?)\}', re.DOTALL), r'**return** \1'),
    (re.compile(r'\\KwRet\{(.+?)\}', re.DOTALL), r'**return** \1'),
    # Control flow
    (re.compile(r'\\ForAll\{(.+?)\}', re.DOTALL), r'**for all** \1 **do**'),
    (re.compile(r'\\ForEach\{(.+?)\}', re.DOTALL), r'**for each** \1 **do**'),
    (re.compile(r'\\For\{(.+?)\}', re.DOTALL), r'**for** \1 **do**'),
    (re.compile(r'\\While\{(.+?)\}', re.DOTALL), r'**while** \1 **do**'),
    (re.compile(r'\\If\{(.+?)\}', re.DOTALL), r'**if** \1 **then**'),
    (re.compile(r'\\ElseIf\{(.+?)\}', re.DOTALL), r'**else if** \1 **then**'),
    (re.compile(r'\\uIf\{(.+?)\}', re.DOTALL), r'**if** \1 **then**'),
    (re.compile(r'\\uElseIf\{(.+?)\}', re.DOTALL), r'**else if** \1 **then**'),
    (re.compile(r'\\lIf\{(.+?)\}\{(.+?)\}', re.DOTALL), r'**if** \1 **then** \2'),
    (re.compile(r'\\Else\b'), r'**else**'),
    (re.compile(r'\\uElse\b'), r'**else**'),
    # Comments
    (re.compile(r'\\tcc\*?\{(.+?)\}', re.DOTALL), r'// \1'),
    (re.compile(r'\\tcp\*?\{(.+?)\}', re.DOTALL), r'// \1'),
    # Line terminators and spacing
    (re.compile(r'\\;'), ''),
    (re.compile(r'\\medskip'), ''),
    (re.compile(r'\\smallskip'), ''),
    (re.compile(r'\\bigskip'), ''),
    # Assignment arrow
    (re.compile(r'\\leftarrow'), '←'),
    (re.compile(r'\\gets'), '←'),
    (re.compile(r'\\rightarrow'), '→'),
    # Block endings (algorithm2e uses implicit blocks)
    (re.compile(r'\\BlankLine'), ''),
    # Caption inside algorithm
    (re.compile(r'\\caption\{(.+?)\}', re.DOTALL), ''),
]


def _transform_algo_body(latex: str) -> str:
    """Apply algorithm2e keyword transformations."""
    text = latex

    # Apply all rules
    for pattern, replacement in _ALGO_RULES:
        text = pattern.sub(replacement, text)

    # Clean up: remove leading/trailing whitespace per line, collapse blank lines
    lines = text.split('\n')
    cleaned = []
    prev_blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not prev_blank:
                cleaned.append('')
                prev_blank = True
            continue
        prev_blank = False
        cleaned.append(stripped)

    return '\n'.join(cleaned)
