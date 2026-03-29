"""Pipeline orchestrator: runs all 8 stages in sequence."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from latex2kb.bibliography import generate_references_md, parse_bib_file
from latex2kb.converter import ConversionContext, convert_chapter
from latex2kb.crossref import resolve_citations, resolve_references
from latex2kb.figures import AIConfig, copy_figures, generate_image_description, load_ai_config
from latex2kb.macro_resolver import (
    MacroTable,
    build_macro_table,
    extract_newtheorems,
)
from latex2kb.metadata import ProjectMetadata, extract_metadata
from latex2kb.output_writer import write_output
from latex2kb.parser_core import build_context_db
from latex2kb.project_scanner import (
    FileRole,
    ProjectInfo,
    get_backmatter_entries,
    get_chapter_entries,
    scan_project,
)
from latex2kb.utils import read_tex_file, slugify

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    input_dir: Path
    output_dir: Path
    main_tex_override: str | None = None
    encoding: str = 'utf-8'
    copy_images: bool = True
    image_descriptions: bool = False
    api_key: str | None = None
    dry_run: bool = False
    config_dict: dict | None = None  # loaded from YAML config file


def run_pipeline(config: PipelineConfig) -> None:
    """Execute the full conversion pipeline."""
    logger.info("=== latex2kb conversion pipeline ===")
    logger.info("Input:  %s", config.input_dir)
    logger.info("Output: %s", config.output_dir)

    # Stage 1: Scan project
    logger.info("Stage 1: Scanning project structure...")
    project = scan_project(config.input_dir, config.main_tex_override)
    logger.info("  Main tex: %s", project.main_tex.name)
    logger.info("  Document class: %s", project.document_class)
    logger.info("  Graphics paths: %s", [str(p) for p in project.graphics_paths])
    logger.info("  Bibliography: %s", [str(p) for p in project.bib_paths])

    chapters = get_chapter_entries(project)
    backmatter = get_backmatter_entries(project)
    logger.info("  Chapters: %d, Backmatter: %d", len(chapters), len(backmatter))

    # Stage 2: Resolve macros
    logger.info("Stage 2: Resolving macros...")
    macro_table = build_macro_table(project.preamble_source, project.root_dir)
    theorem_names = extract_newtheorems(project.preamble_source)
    logger.info("  Theorem environments: %s", theorem_names)

    # Stage 3: Build parser context
    logger.info("Stage 3: Building parser context...")
    context_db = build_context_db(macro_table)

    # Stage 4: Convert chapters
    logger.info("Stage 4: Converting chapters to Markdown...")
    ctx = ConversionContext(
        macro_table=macro_table,
        theorem_names=theorem_names,
        graphics_paths=[str(p) for p in project.graphics_paths],
    )

    chapter_outputs = []
    all_entries = list(chapters) + list(backmatter)

    for i, entry in enumerate(all_entries):
        chapter_num = i + 1 if entry.role == FileRole.MAINMATTER else 0
        ctx.chapter_num = chapter_num
        ctx.reset_chapter_counters()

        source = read_tex_file(entry.path)

        # Derive output filename
        chapter_title = _extract_chapter_title(source)
        if entry.role == FileRole.MAINMATTER:
            slug = slugify(chapter_title or entry.path.stem)
            filename = f'{chapter_num:02d}-{slug}.md'
        else:
            slug = slugify(entry.path.stem)
            filename = f'{slug}.md'

        ctx.current_file = f'chapters/{filename}'

        logger.info("  Converting: %s -> %s", entry.path.name, filename)
        md_content = convert_chapter(source, ctx, context_db)

        chapter_outputs.append({
            'filename': filename,
            'title': chapter_title or entry.path.stem,
            'content': md_content,
            'role': entry.role,
        })

    # Stage 5: Resolve cross-references
    logger.info("Stage 5: Resolving cross-references...")
    logger.info("  Labels registered: %d", len(ctx.labels))
    for ch in chapter_outputs:
        ch['content'] = resolve_references(
            ch['content'],
            f'chapters/{ch["filename"]}',
            ctx.labels,
        )

    # Stage 6: Bibliography
    logger.info("Stage 6: Processing bibliography...")
    bib_entries: dict[str, dict] = {}
    for bib_path in project.bib_paths:
        entries = parse_bib_file(bib_path)
        bib_entries.update(entries)

    logger.info("  Citation keys found: %d", len(ctx.citation_keys))
    for ch in chapter_outputs:
        ch['content'] = resolve_citations(
            ch['content'],
            bib_entries,
            references_file='../references.md',
        )

    references_md = ''
    if bib_entries and ctx.citation_keys:
        references_md = generate_references_md(bib_entries, ctx.citation_keys)

    # Stage 7: Figures
    logger.info("Stage 7: Handling figures...")
    logger.info("  Referenced images: %d", len(ctx.figure_paths))
    if config.copy_images and not config.dry_run:
        figures_dir = config.output_dir / 'figures'
        copied = copy_figures(
            project.graphics_paths,
            project.root_dir,
            figures_dir,
            ctx.figure_paths,
        )

        # Optional AI descriptions
        if config.image_descriptions:
            ai_cfg = load_ai_config(config.config_dict, config.api_key)
            if ai_cfg.api_key:
                logger.info("  Generating AI image descriptions (provider: %s, model: %s)...",
                            ai_cfg.provider, ai_cfg.effective_model)
                for rel_path, abs_path in copied.items():
                    desc = generate_image_description(abs_path, ai_cfg)
                    if desc:
                        _inject_image_description(chapter_outputs, rel_path, desc)
            else:
                logger.warning("  AI descriptions enabled but no API key found. "
                               "Set ANTHROPIC_API_KEY / OPENAI_API_KEY env var, "
                               "or use --api-key, or configure in YAML config file.")

    # Stage 8: Write output
    logger.info("Stage 8: Writing output...")
    metadata = extract_metadata(project.preamble_source, project.class_options)
    metadata.document_class = project.document_class
    metadata.total_figures = len(ctx.figure_paths)
    metadata.total_references = len(ctx.citation_keys)
    metadata.chapters = [
        {'file': ch['filename'], 'title': ch['title']}
        for ch in chapter_outputs
    ]

    write_output(
        config.output_dir,
        chapter_outputs,
        references_md,
        metadata,
        dry_run=config.dry_run,
    )

    logger.info("=== Conversion complete! ===")
    logger.info("  Chapters: %d", len(chapter_outputs))
    logger.info("  Labels: %d", len(ctx.labels))
    logger.info("  Citations: %d", len(ctx.citation_keys))
    logger.info("  Figures: %d", len(ctx.figure_paths))


def _extract_chapter_title(source: str) -> str | None:
    """Extract the chapter title from source."""
    m = re.search(r'\\chapter\*?\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}', source)
    if m:
        return m.group(2).strip()
    return None


def _inject_image_description(
    chapter_outputs: list[dict],
    image_rel_path: str,
    description: str,
) -> None:
    """Inject an AI-generated image description into chapter content."""
    # Find the image reference and add description below it
    for ch in chapter_outputs:
        pattern = f'../figures/{re.escape(image_rel_path)}'
        if pattern in ch['content']:
            # Add description below the image line
            ch['content'] = ch['content'].replace(
                f'../figures/{image_rel_path})',
                f'../figures/{image_rel_path})\n\n> *AI Description: {description}*',
                1,
            )
            break
