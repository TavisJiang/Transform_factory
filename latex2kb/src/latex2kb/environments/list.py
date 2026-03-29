"""List environment converter: itemize, enumerate, description."""

from __future__ import annotations


def format_list_item(content: str, list_type: str, index: int = 0, indent: int = 0) -> str:
    """Format a single list item."""
    prefix = '  ' * indent
    if list_type == 'enumerate':
        return f'{prefix}{index}. {content}'
    elif list_type == 'description':
        return f'{prefix}- {content}'
    else:  # itemize
        return f'{prefix}- {content}'
