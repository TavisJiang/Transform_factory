"""Shared utilities: brace matching, path normalization, text helpers."""

from __future__ import annotations

import re
from pathlib import Path


def find_matching_brace(text: str, start: int) -> int:
    """Find the index of the closing brace matching the opening brace at `start`.

    Returns -1 if no match found.
    """
    if start >= len(text) or text[start] != '{':
        return -1
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '\\':
            i += 2  # skip escaped char
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_braced_arg(text: str, pos: int) -> tuple[str, int]:
    """Extract a {braced} argument starting at pos (skipping whitespace).

    Returns (content, end_pos) where end_pos is after the closing brace.
    """
    # skip whitespace
    while pos < len(text) and text[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(text) or text[pos] != '{':
        return ('', pos)
    end = find_matching_brace(text, pos)
    if end == -1:
        return (text[pos + 1:], len(text))
    return (text[pos + 1:end], end + 1)


def extract_optional_arg(text: str, pos: int) -> tuple[str | None, int]:
    """Extract an [optional] argument starting at pos (skipping whitespace).

    Returns (content, end_pos) or (None, pos) if no optional arg.
    """
    while pos < len(text) and text[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(text) or text[pos] != '[':
        return (None, pos)
    depth = 1
    i = pos + 1
    while i < len(text) and depth > 0:
        if text[i] == '\\':
            i += 2
            continue
        if text[i] == '[':
            depth += 1
        elif text[i] == ']':
            depth -= 1
        i += 1
    return (text[pos + 1:i - 1], i)


def strip_tex_comments(text: str) -> str:
    """Remove TeX line comments (% to end of line), preserving \\%."""
    lines = text.split('\n')
    result = []
    for line in lines:
        cleaned = []
        i = 0
        while i < len(line):
            if line[i] == '\\' and i + 1 < len(line):
                cleaned.append(line[i:i + 2])
                i += 2
                continue
            if line[i] == '%':
                break
            cleaned.append(line[i])
            i += 1
        result.append(''.join(cleaned))
    return '\n'.join(result)


def sanitize_anchor(label: str) -> str:
    """Convert a LaTeX label to a valid HTML anchor id."""
    return re.sub(r'[^a-zA-Z0-9_-]', '-', label)


def slugify(text: str, max_len: int = 60) -> str:
    """Create a URL-safe slug from text. Works with Chinese and mixed text."""
    # Extract all word-like parts (ASCII words and Chinese character runs)
    parts = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]+', text)
    if not parts:
        return f"chapter-{abs(hash(text)) % 10000:04d}"

    # Use ASCII parts if available
    ascii_parts = [p for p in parts if re.match(r'[a-zA-Z0-9]+', p)]
    if ascii_parts:
        slug = '-'.join(ascii_parts).lower()
    else:
        # For Chinese-only titles, use the Chinese characters directly
        # They are valid in URLs and filenames
        slug = '-'.join(parts)
    return slug[:max_len].rstrip('-')


def normalize_path(path: str) -> str:
    """Normalize path separators to forward slashes."""
    return path.replace('\\', '/')


def read_tex_file(path: Path, encoding: str = 'utf-8') -> str:
    """Read a .tex file with proper encoding handling."""
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        # Fallback encodings common in LaTeX files
        for enc in ['latin-1', 'gbk', 'gb2312']:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        raise
