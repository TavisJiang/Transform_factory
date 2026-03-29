"""Stage 5: Cross-reference resolution across output files.

Replaces placeholder tokens <<REF:key>>, <<EQREF:key>>, <<CITE:key>>
with proper Markdown links.
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath

from latex2kb.converter import LabelInfo

logger = logging.getLogger(__name__)


def resolve_references(
    md_text: str,
    current_file: str,
    labels: dict[str, LabelInfo],
) -> str:
    """Replace all <<REF:key>> and <<EQREF:key>> placeholders with Markdown links."""

    def _replace_ref(match: re.Match) -> str:
        key = match.group(1)
        entry = labels.get(key)
        if entry is None:
            logger.warning("Unresolved reference: \\ref{%s}", key)
            return f'[??{key}??]'
        return _make_link(entry, current_file)

    def _replace_eqref(match: re.Match) -> str:
        key = match.group(1)
        entry = labels.get(key)
        if entry is None:
            logger.warning("Unresolved equation reference: \\eqref{%s}", key)
            return f'[??{key}??]'
        return _make_link(entry, current_file)

    md_text = re.sub(r'<<REF:(.+?)>>', _replace_ref, md_text)
    md_text = re.sub(r'<<EQREF:(.+?)>>', _replace_eqref, md_text)

    return md_text


def resolve_citations(
    md_text: str,
    bib_entries: dict[str, dict],
    references_file: str = 'references.md',
) -> str:
    """Replace <<CITE:key>> placeholders with [Author, Year](references.md#key) links."""

    def _replace_cite(match: re.Match) -> str:
        key = match.group(1)
        entry = bib_entries.get(key)
        if entry is None:
            # Try case-insensitive lookup
            for k, v in bib_entries.items():
                if k.lower() == key.lower():
                    entry = v
                    key = k
                    break
        if entry is None:
            logger.warning("Unresolved citation: \\cite{%s}", key)
            return f'[{key}]'

        display = _format_citation_display(entry)
        anchor = key
        return f'[{display}]({references_file}#{anchor})'

    return re.sub(r'<<CITE:(.+?)>>', _replace_cite, md_text)


def _make_link(entry: LabelInfo, current_file: str) -> str:
    """Create a Markdown link to a label entry."""
    display = entry.display

    if entry.file == current_file:
        return f'[{display}](#{entry.anchor})'
    else:
        rel_path = _relative_path(current_file, entry.file)
        return f'[{display}]({rel_path}#{entry.anchor})'


def _relative_path(from_file: str, to_file: str) -> str:
    """Compute relative path from one output file to another."""
    from_parts = PurePosixPath(from_file).parent.parts
    to_parts = PurePosixPath(to_file).parts

    # Find common prefix
    common = 0
    for a, b in zip(from_parts, to_parts):
        if a == b:
            common += 1
        else:
            break

    # Build relative path
    up = len(from_parts) - common
    remaining = to_parts[common:]
    parts = ['..'] * up + list(remaining)
    return '/'.join(parts) if parts else PurePosixPath(to_file).name


def _format_citation_display(entry: dict) -> str:
    """Format a citation for inline display: Author, Year."""
    author = entry.get('author', '')
    year = entry.get('year', '')

    if author:
        # Extract first author's last name
        # Handle "Last, First and Last2, First2" format
        first_author = author.split(' and ')[0].strip()
        if ',' in first_author:
            last_name = first_author.split(',')[0].strip()
        else:
            # "First Last" format
            parts = first_author.split()
            last_name = parts[-1] if parts else first_author

        if len(author.split(' and ')) > 2:
            return f'{last_name} et al., {year}'
        elif len(author.split(' and ')) == 2:
            second = author.split(' and ')[1].strip()
            if ',' in second:
                last2 = second.split(',')[0].strip()
            else:
                parts2 = second.split()
                last2 = parts2[-1] if parts2 else second
            return f'{last_name} & {last2}, {year}'
        else:
            return f'{last_name}, {year}'

    return year or '??'
