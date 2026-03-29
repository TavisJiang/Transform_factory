"""Table environment converter: tabular, booktabs, longtable."""

from __future__ import annotations

import re


def convert_tabular(inner_latex: str, col_spec: str = '') -> str:
    """Convert a tabular/longtable environment to a Markdown table.

    Handles booktabs commands (\\toprule, \\midrule, \\bottomrule).
    """
    # Clean up the inner content
    text = inner_latex.strip()

    # Remove booktabs rules (we'll add markdown separators)
    text = re.sub(r'\\toprule\s*', '', text)
    text = re.sub(r'\\midrule\s*', '', text)
    text = re.sub(r'\\bottomrule\s*', '', text)
    text = re.sub(r'\\hline\s*', '', text)
    text = re.sub(r'\\cline\{[^}]*\}\s*', '', text)

    # Remove \resizebox and similar wrappers
    text = re.sub(r'\\resizebox\{[^}]*\}\{[^}]*\}\{', '', text)
    text = re.sub(r'\\renewcommand\{\\arraystretch\}\{[^}]*\}', '', text)
    text = re.sub(r'\\setlength\{\\tabcolsep\}\{[^}]*\}', '', text)
    text = re.sub(r'\\centering\s*', '', text)

    # Split into rows by \\
    rows_raw = re.split(r'\\\\', text)
    rows = []
    for row in rows_raw:
        row = row.strip()
        if not row:
            continue
        # Split cells by &
        cells = [cell.strip() for cell in row.split('&')]
        if any(c for c in cells):  # skip empty rows
            rows.append(cells)

    if not rows:
        return '_[Empty table]_'

    # Normalize column count
    max_cols = max(len(r) for r in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append('')

    # Handle \multicolumn (best-effort: just extract text)
    for row in rows:
        for i, cell in enumerate(row):
            m = re.match(r'\\multicolumn\{(\d+)\}\{[^}]*\}\{(.+)\}', cell.strip())
            if m:
                row[i] = m.group(2).strip()

    # Build markdown table
    lines = []

    # Header row
    header = '| ' + ' | '.join(rows[0]) + ' |'
    separator = '| ' + ' | '.join('---' for _ in rows[0]) + ' |'
    lines.append(header)
    lines.append(separator)

    # Data rows
    for row in rows[1:]:
        lines.append('| ' + ' | '.join(row) + ' |')

    return '\n'.join(lines)


def convert_table_float(
    body_md: str,
    caption: str | None = None,
    label: str | None = None,
) -> str:
    """Wrap a converted tabular in a table float with caption."""
    parts = []

    if label:
        anchor = label.replace(':', '-')
        parts.append(f'<a id="{anchor}"></a>')
        parts.append('')

    if caption:
        parts.append(f'**Table**: {caption}')
        parts.append('')

    parts.append(body_md)
    parts.append('')

    return '\n'.join(parts)
