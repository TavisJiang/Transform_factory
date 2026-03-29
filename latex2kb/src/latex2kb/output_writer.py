"""Stage 8: Write output directory structure."""

from __future__ import annotations

import logging
from pathlib import Path

from latex2kb.metadata import ProjectMetadata, metadata_to_yaml

logger = logging.getLogger(__name__)


def write_output(
    output_dir: Path,
    chapter_files: list[dict],  # [{filename, title, content}]
    references_md: str,
    metadata: ProjectMetadata,
    dry_run: bool = False,
) -> None:
    """Write the complete output directory."""
    if dry_run:
        logger.info("[DRY RUN] Would create output at: %s", output_dir)
        logger.info("[DRY RUN] Chapters: %d", len(chapter_files))
        for ch in chapter_files:
            logger.info("[DRY RUN]   - %s", ch['filename'])
        return

    # Create directories
    output_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = output_dir / 'chapters'
    chapters_dir.mkdir(exist_ok=True)
    figures_dir = output_dir / 'figures'
    figures_dir.mkdir(exist_ok=True)

    # Write chapter files
    for ch in chapter_files:
        path = chapters_dir / ch['filename']
        path.write_text(ch['content'], encoding='utf-8')
        logger.info("Written: %s", path)

    # Write references
    if references_md:
        ref_path = output_dir / 'references.md'
        ref_path.write_text(references_md, encoding='utf-8')
        logger.info("Written: %s", ref_path)

    # Write index.md
    index_md = generate_index(chapter_files, metadata)
    index_path = output_dir / 'index.md'
    index_path.write_text(index_md, encoding='utf-8')
    logger.info("Written: %s", index_path)

    # Write metadata.yaml
    yaml_content = metadata_to_yaml(metadata)
    yaml_path = output_dir / 'metadata.yaml'
    yaml_path.write_text(yaml_content, encoding='utf-8')
    logger.info("Written: %s", yaml_path)


def generate_index(
    chapter_files: list[dict],
    metadata: ProjectMetadata,
) -> str:
    """Generate the index.md knowledge base entry point."""
    lines = []

    # Title
    lines.append(f'# {metadata.title}')
    lines.append('')

    if metadata.title_en and metadata.title_zh:
        lines.append(f'*{metadata.title_en}*')
        lines.append('')

    # Metadata block
    if metadata.author:
        lines.append(f'**Author**: {metadata.author}')
    if metadata.supervisor_zh or metadata.supervisor_en:
        sup = metadata.supervisor_en or metadata.supervisor_zh
        lines.append(f'**Supervisor**: {sup}')
    if metadata.institution:
        lines.append(f'**Institution**: {metadata.institution}')
    if metadata.date:
        lines.append(f'**Date**: {metadata.date}')
    if metadata.degree:
        lines.append(f'**Degree**: {metadata.degree.capitalize()} Dissertation')
    if metadata.speciality_en or metadata.speciality_zh:
        spec = metadata.speciality_en or metadata.speciality_zh
        lines.append(f'**Field**: {spec}')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Table of Contents
    lines.append('## Table of Contents')
    lines.append('')
    for i, ch in enumerate(chapter_files, 1):
        title = ch.get('title', ch['filename'])
        lines.append(f'{i}. [{title}](chapters/{ch["filename"]})')
    lines.append('')

    # References link
    if metadata.total_references:
        lines.append(f'## References')
        lines.append('')
        lines.append(f'See [Full Bibliography](references.md) ({metadata.total_references} references cited)')
        lines.append('')

    # Footer
    lines.append('---')
    lines.append('')
    lines.append('*Converted by [latex2kb](https://github.com/latex2kb)*')

    return '\n'.join(lines)
