"""img2kb pipeline: convert an image folder into a structured Markdown document.

Two-round AI approach:
  Round 1 — Per-image analysis: extract text, describe visuals, classify
  Round 2 — Synthesis: combine all analyses into a coherent Markdown document
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from latex2kb.figures import AIConfig, call_ai_text, generate_image_description, load_ai_config

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.tif'}


@dataclass
class Img2kbConfig:
    input_dir: Path
    output_dir: Path
    api_key: str | None = None
    dry_run: bool = False
    config_dict: dict | None = None


@dataclass
class ImageAnalysis:
    filename: str
    extracted_text: str       # OCR / text content from the image
    visual_description: str   # what the image shows visually
    is_textualizable: bool    # True = content can be fully represented as text
    category: str             # e.g. "text/table", "diagram", "photo", "chart", "screenshot"


def run_img2kb(config: Img2kbConfig) -> None:
    """Execute the image-to-knowledge-base pipeline."""
    logger.info("=== img2kb conversion pipeline ===")
    logger.info("Input:  %s", config.input_dir)
    logger.info("Output: %s", config.output_dir)

    # Build AI config
    ai_cfg = load_ai_config(config.config_dict, config.api_key)
    if not ai_cfg.api_key:
        raise RuntimeError(
            "img2kb requires an API key. Set ANTHROPIC_API_KEY / OPENAI_API_KEY env var, "
            "use --api-key, or configure in latex2kb.yaml."
        )
    logger.info("AI provider: %s, model: %s", ai_cfg.provider, ai_cfg.effective_model)

    # Stage 1: Scan images
    logger.info("Stage 1: Scanning images...")
    images = _scan_images(config.input_dir)
    if not images:
        raise RuntimeError(f"No image files found in {config.input_dir}")
    logger.info("  Found %d images", len(images))

    if config.dry_run:
        for img in images:
            logger.info("  [DRY RUN] Would process: %s", img.name)
        logger.info("Dry run complete.")
        return

    # Stage 2: Per-image AI analysis (Round 1)
    logger.info("Stage 2: Analyzing images (Round 1)...")
    analyses = []
    for i, img_path in enumerate(images, 1):
        logger.info("  [%d/%d] %s", i, len(images), img_path.name)
        analysis = _analyze_image(img_path, ai_cfg)
        analyses.append(analysis)
        logger.info("    category=%s, textualizable=%s", analysis.category, analysis.is_textualizable)

    # Stage 3: Synthesize into Markdown (Round 2)
    logger.info("Stage 3: Synthesizing document (Round 2)...")
    # Use a more capable model for synthesis if available
    synth_cfg = _get_synthesis_config(ai_cfg)
    markdown = _synthesize_document(analyses, synth_cfg)

    # Stage 4: Determine which images need to be referenced
    referenced_images = [a for a in analyses if not a.is_textualizable]
    logger.info("Stage 4: %d/%d images need visual reference", len(referenced_images), len(analyses))

    # Stage 5: Write output
    logger.info("Stage 5: Writing output...")
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Copy only non-textualizable images
    if referenced_images:
        figures_dir = config.output_dir / 'figures'
        figures_dir.mkdir(exist_ok=True)
        for analysis in referenced_images:
            src = config.input_dir / analysis.filename
            if src.exists():
                shutil.copy2(src, figures_dir / analysis.filename)
                logger.info("  Copied: %s", analysis.filename)

    # Write markdown
    md_path = config.output_dir / 'document.md'
    md_path.write_text(markdown, encoding='utf-8')
    logger.info("  Written: %s", md_path)

    logger.info("=== img2kb complete! ===")
    logger.info("  Images analyzed: %d", len(analyses))
    logger.info("  Images referenced (in figures/): %d", len(referenced_images))
    logger.info("  Images textualized (no copy needed): %d", len(analyses) - len(referenced_images))


def _scan_images(directory: Path) -> list[Path]:
    """Find all image files in a directory, sorted by name."""
    images = []
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(f)
    return images


def _analyze_image(image_path: Path, ai_cfg: AIConfig) -> ImageAnalysis:
    """Round 1: Analyze a single image with AI."""
    prompt = (
        "Analyze this image and respond in the following JSON format ONLY "
        "(no markdown fences, no extra text):\n"
        "{\n"
        '  "extracted_text": "all text/equations visible in the image, verbatim",\n'
        '  "visual_description": "concise description of what the image shows",\n'
        '  "is_textualizable": true/false,\n'
        '  "category": "text|table|diagram|chart|photo|screenshot|equation|other"\n'
        "}\n\n"
        "Rules for is_textualizable:\n"
        "- true: the image is purely text, a table of numbers/text, or equations "
        "that can be fully represented in Markdown (including LaTeX math $...$)\n"
        "- false: the image contains visual information (diagrams, plots, photos, "
        "charts, circuits, schematics) that cannot be adequately described by text alone\n\n"
        "For extracted_text: reproduce ALL text faithfully. "
        "For math/equations, use LaTeX notation like $E=mc^2$ or $$...$$."
    )

    # Temporarily override the image_prompt
    original_prompt = ai_cfg.image_prompt
    ai_cfg.image_prompt = prompt
    original_max_tokens = ai_cfg.max_tokens
    ai_cfg.max_tokens = 2000

    try:
        from latex2kb.figures import generate_image_description
        raw = generate_image_description(image_path, ai_cfg)
    finally:
        ai_cfg.image_prompt = original_prompt
        ai_cfg.max_tokens = original_max_tokens

    if not raw:
        return ImageAnalysis(
            filename=image_path.name,
            extracted_text="",
            visual_description="[AI analysis failed]",
            is_textualizable=False,
            category="other",
        )

    return _parse_analysis_response(image_path.name, raw)


def _parse_analysis_response(filename: str, raw: str) -> ImageAnalysis:
    """Parse the JSON response from Round 1 AI call."""
    # Strip markdown fences if AI added them despite instructions
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    if text.startswith('json'):
        text = text[4:].strip()

    try:
        data = json.loads(text)
        return ImageAnalysis(
            filename=filename,
            extracted_text=data.get('extracted_text', ''),
            visual_description=data.get('visual_description', ''),
            is_textualizable=bool(data.get('is_textualizable', False)),
            category=data.get('category', 'other'),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse AI response for %s: %s", filename, e)
        logger.debug("Raw response: %s", raw[:500])
        return ImageAnalysis(
            filename=filename,
            extracted_text=raw,
            visual_description="",
            is_textualizable=False,
            category="other",
        )


def _get_synthesis_config(ai_cfg: AIConfig) -> AIConfig:
    """Get AI config for synthesis, preferring a more capable model."""
    # For synthesis we need a model with larger context and better reasoning.
    # Upgrade from haiku to sonnet if user didn't explicitly set a model.
    synth = AIConfig(
        provider=ai_cfg.provider,
        model=ai_cfg.model,
        api_key=ai_cfg.api_key,
        base_url=ai_cfg.base_url,
        image_prompt=ai_cfg.image_prompt,
        max_tokens=8000,
        timeout=120,
    )
    # Auto-upgrade for synthesis if using default cheap models
    if not ai_cfg.model or ai_cfg.model in ('claude-haiku-4-5-20251001', 'gpt-4o-mini'):
        upgrades = {
            'anthropic': 'claude-sonnet-4-6-20250514',
            'openai': 'gpt-4o',
            'openai-compatible': 'gpt-4o',
        }
        upgraded = upgrades.get(ai_cfg.provider, '')
        if upgraded:
            synth.model = upgraded
            logger.info("  Upgraded model for synthesis: %s → %s", ai_cfg.effective_model, upgraded)
    return synth


def _synthesize_document(analyses: list[ImageAnalysis], ai_cfg: AIConfig) -> str:
    """Round 2: Synthesize all image analyses into a coherent Markdown document."""
    # Build the context for AI
    parts = []
    for i, a in enumerate(analyses, 1):
        parts.append(f"--- Image {i}: {a.filename} ---")
        parts.append(f"Category: {a.category}")
        parts.append(f"Textualizable: {a.is_textualizable}")
        if a.extracted_text:
            parts.append(f"Extracted text:\n{a.extracted_text}")
        if a.visual_description:
            parts.append(f"Visual description: {a.visual_description}")
        parts.append("")

    image_context = '\n'.join(parts)

    # Build list of images that need referencing
    ref_images = [a for a in analyses if not a.is_textualizable]
    ref_list = ', '.join(a.filename for a in ref_images) if ref_images else '(none)'

    prompt = (
        "You are given analyses of multiple images from a folder. "
        "Your task is to synthesize them into a single, coherent Markdown document.\n\n"
        "RULES:\n"
        "1. Organize the content logically with headings (##, ###) and sections.\n"
        "2. For TEXTUALIZABLE images: incorporate their content directly as text. "
        "Reproduce tables as Markdown tables. Reproduce equations as LaTeX ($...$ or $$...$$). "
        "Do NOT reference these images — their content is fully represented in text.\n"
        "3. For NON-TEXTUALIZABLE images: embed them using ![description](figures/filename). "
        f"These images will be in figures/: {ref_list}\n"
        "4. Write in the same language as the source content. "
        "If content is in Chinese, write in Chinese. If English, write in English.\n"
        "5. Make the document flow naturally — add transitions, context, and structure. "
        "This should read as a coherent document, not a list of image descriptions.\n"
        "6. Preserve ALL technical details, numbers, equations, and data faithfully.\n"
        "7. Output ONLY the Markdown content, no preamble or explanation.\n\n"
        f"IMAGE ANALYSES ({len(analyses)} images):\n\n"
        f"{image_context}"
    )

    result = call_ai_text(prompt, ai_cfg, max_tokens=ai_cfg.max_tokens)

    if not result:
        logger.warning("Synthesis failed, falling back to simple concatenation")
        return _fallback_synthesis(analyses)

    return result


def _fallback_synthesis(analyses: list[ImageAnalysis]) -> str:
    """Fallback: simple concatenation if AI synthesis fails."""
    lines = ["# Document\n"]
    for i, a in enumerate(analyses, 1):
        lines.append(f"## Image {i}: {a.filename}\n")
        if a.extracted_text:
            lines.append(a.extracted_text)
            lines.append("")
        if not a.is_textualizable:
            lines.append(f"![{a.visual_description}](figures/{a.filename})")
            lines.append("")
        elif a.visual_description:
            lines.append(f"*{a.visual_description}*")
            lines.append("")
    return '\n'.join(lines)


def is_image_folder(directory: Path) -> bool:
    """Check if a directory looks like a pure image folder (no .tex files)."""
    has_tex = any(directory.rglob('*.tex'))
    has_images = any(
        f.suffix.lower() in IMAGE_EXTENSIONS
        for f in directory.iterdir()
        if f.is_file()
    )
    return has_images and not has_tex
