"""Stage 6: BibTeX parsing and references.md generation."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_bib_file(bib_path: Path) -> dict[str, dict]:
    """Parse a .bib file and return a dict of {key: entry_dict}.

    Uses bibtexparser for robust parsing.
    """
    import bibtexparser

    try:
        with open(bib_path, encoding='utf-8') as f:
            bib_text = f.read()
    except UnicodeDecodeError:
        with open(bib_path, encoding='latin-1') as f:
            bib_text = f.read()

    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    bib_db = bibtexparser.loads(bib_text, parser=parser)

    entries = {}
    for entry in bib_db.entries:
        key = entry.get('ID', '')
        if key:
            entries[key] = entry

    logger.info("Parsed %d bibliography entries from %s", len(entries), bib_path.name)
    return entries


def generate_references_md(
    bib_entries: dict[str, dict],
    cited_keys: set[str],
) -> str:
    """Generate references.md with all cited entries."""
    lines = ['# References', '']

    # Resolve cited keys (case-insensitive matching)
    resolved = _resolve_cited_keys(bib_entries, cited_keys)

    # Sort by key
    sorted_keys = sorted(resolved.keys(), key=str.lower)

    for key in sorted_keys:
        entry = resolved[key]
        lines.append(f'<a id="{key}"></a>')
        lines.append('')
        formatted = _format_entry(key, entry)
        lines.append(formatted)
        lines.append('')

    lines.append('---')
    lines.append(f'*{len(sorted_keys)} references cited.*')

    return '\n'.join(lines)


def _resolve_cited_keys(bib_entries: dict[str, dict], cited_keys: set[str]) -> dict[str, dict]:
    """Match cited keys to bib entries, with case-insensitive fallback."""
    resolved = {}
    lower_map = {k.lower(): k for k in bib_entries}

    for key in cited_keys:
        if key in bib_entries:
            resolved[key] = bib_entries[key]
        elif key.lower() in lower_map:
            actual = lower_map[key.lower()]
            resolved[actual] = bib_entries[actual]
            logger.debug("Citation key %s matched to %s (case mismatch)", key, actual)
        else:
            logger.warning("Citation key not found in .bib: %s", key)

    return resolved


def _format_entry(key: str, entry: dict) -> str:
    """Format a single bibliography entry as Markdown."""
    author = entry.get('author', 'Unknown')
    title = entry.get('title', '').strip('{}')
    year = entry.get('year', '')
    journal = entry.get('journal', '')
    booktitle = entry.get('booktitle', '')
    volume = entry.get('volume', '')
    number = entry.get('number', '')
    pages = entry.get('pages', '')
    doi = entry.get('doi', '')
    url = entry.get('url', '')
    publisher = entry.get('publisher', '')
    note = entry.get('note', '')
    entry_type = entry.get('ENTRYTYPE', 'misc')

    parts = [f'**[{_short_author(author)}, {year}]**']

    # Author list
    parts.append(f'{_clean_author(author)}.')

    # Title
    if title:
        parts.append(f'"{title}."')

    # Venue
    if entry_type == 'article' and journal:
        venue = f'*{journal}*'
        if volume:
            venue += f', {volume}'
            if number:
                venue += f'({number})'
        if pages:
            venue += f':{pages}'
        venue += f', {year}.'
        parts.append(venue)
    elif entry_type in ('inproceedings', 'incollection') and booktitle:
        parts.append(f'In *{booktitle}*, {year}.')
    elif entry_type == 'book':
        if publisher:
            parts.append(f'{publisher}, {year}.')
        else:
            parts.append(f'{year}.')
    elif entry_type in ('phdthesis', 'mastersthesis'):
        school = entry.get('school', '')
        thesis_type = 'PhD thesis' if entry_type == 'phdthesis' else "Master's thesis"
        parts.append(f'{thesis_type}, {school}, {year}.')
    else:
        if year:
            parts.append(f'{year}.')

    # DOI or URL
    if doi:
        doi_clean = doi.strip()
        if not doi_clean.startswith('http'):
            doi_clean = f'https://doi.org/{doi_clean}'
        parts.append(f'[DOI]({doi_clean})')
    elif url:
        parts.append(f'[URL]({url})')

    # Note
    if note:
        parts.append(f'*{note}*')

    return ' '.join(parts)


def _short_author(author: str) -> str:
    """Get short author representation for citation display."""
    authors = author.split(' and ')
    first = authors[0].strip()
    if ',' in first:
        last = first.split(',')[0].strip()
    else:
        words = first.split()
        last = words[-1] if words else first

    if len(authors) > 2:
        return f'{last} et al.'
    elif len(authors) == 2:
        second = authors[1].strip()
        if ',' in second:
            last2 = second.split(',')[0].strip()
        else:
            words2 = second.split()
            last2 = words2[-1] if words2 else second
        return f'{last} & {last2}'
    return last


def _clean_author(author: str) -> str:
    """Clean up BibTeX author field for display."""
    # Replace 'and' separators with commas, clean braces
    author = author.replace('{', '').replace('}', '')
    authors = [a.strip() for a in author.split(' and ')]
    if len(authors) <= 3:
        return ', '.join(authors)
    return ', '.join(authors[:3]) + ', et al.'
