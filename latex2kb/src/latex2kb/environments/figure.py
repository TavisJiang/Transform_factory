"""Figure environment converter."""

from __future__ import annotations


def convert_figure(
    image_path: str,
    caption: str | None = None,
    label: str | None = None,
    is_pdf: bool = False,
) -> str:
    """Convert a figure environment to Markdown.

    For PDF images, uses a link instead of inline image since most
    Markdown renderers can't display PDFs.
    """
    parts = []

    if label:
        anchor = label.replace(':', '-')
        parts.append(f'<a id="{anchor}"></a>')
        parts.append('')

    cap = caption or ''

    if is_pdf:
        # PDF: use link format
        parts.append(f'[{cap or "Figure"}](../figures/{image_path}) *(PDF figure)*')
    else:
        # Raster image: use inline image
        parts.append(f'![{cap}](../figures/{image_path})')

    if caption:
        parts.append('')

    return '\n'.join(parts)
