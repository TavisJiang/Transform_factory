"""CLI entry point for latex2kb."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from latex2kb import __version__


@click.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument('output_dir', type=click.Path(path_type=Path))
@click.option('--config', 'config_file', type=click.Path(exists=True, path_type=Path), default=None,
              help='YAML config file (see latex2kb.example.yaml).')
@click.option('--main-tex', default=None, help='Override auto-detected main .tex file name.')
@click.option('--image-descriptions', is_flag=True, help='Enable AI-powered image descriptions.')
@click.option('--provider', default=None, type=click.Choice(['anthropic', 'openai', 'openai-compatible']),
              help='AI provider for image descriptions.')
@click.option('--api-key', default=None,
              help='API key (or set ANTHROPIC_API_KEY / OPENAI_API_KEY env var).')
@click.option('--no-copy-images', is_flag=True, help='Skip copying images, just reference paths.')
@click.option('--encoding', default='utf-8', help='Source file encoding (default: utf-8).')
@click.option('-v', '--verbose', is_flag=True, help='Verbose logging.')
@click.option('--dry-run', is_flag=True, help='Show what would be generated without writing.')
@click.version_option(__version__)
def main(
    input_dir: Path,
    output_dir: Path,
    config_file: Path | None,
    main_tex: str | None,
    image_descriptions: bool,
    provider: str | None,
    api_key: str | None,
    no_copy_images: bool,
    encoding: str,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Convert a LaTeX project into a structured Markdown knowledge base.

    INPUT_DIR is the LaTeX project folder (containing main.tex).
    OUTPUT_DIR is where the Markdown knowledge base will be written.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s',
    )

    # Load config file
    config_dict = None
    if config_file:
        config_dict = _load_config_file(config_file)
        if config_dict:
            click.echo(f"Loaded config: {config_file}")
    else:
        # Auto-detect latex2kb.yaml in input dir or current dir
        for candidate in [input_dir / 'latex2kb.yaml', Path('latex2kb.yaml')]:
            if candidate.exists():
                config_dict = _load_config_file(candidate)
                if config_dict:
                    click.echo(f"Auto-loaded config: {candidate}")
                break

    # Apply config file defaults (CLI flags override)
    if config_dict:
        if main_tex is None:
            main_tex = config_dict.get('main_tex')
        if encoding == 'utf-8' and 'encoding' in config_dict:
            encoding = config_dict['encoding']
        if not no_copy_images and config_dict.get('copy_images') is False:
            no_copy_images = True
        if not image_descriptions and config_dict.get('image_descriptions'):
            image_descriptions = True

    # Override provider in config if specified via CLI
    if provider and config_dict:
        config_dict.setdefault('ai', {})['provider'] = provider
    elif provider:
        config_dict = {'ai': {'provider': provider}}

    # Auto-generate subfolder: {input_folder_name}_2kb
    actual_output = output_dir.resolve() / (input_dir.resolve().name + '_2kb')

    from latex2kb.pipeline import run_pipeline, PipelineConfig

    config = PipelineConfig(
        input_dir=input_dir.resolve(),
        output_dir=actual_output,
        main_tex_override=main_tex,
        encoding=encoding,
        copy_images=not no_copy_images,
        image_descriptions=image_descriptions,
        api_key=api_key,
        dry_run=dry_run,
        config_dict=config_dict,
    )

    try:
        run_pipeline(config)
    except Exception as e:
        if verbose:
            logging.exception("Pipeline failed")
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not dry_run:
        click.echo(f"Done! Knowledge base written to: {actual_output}")
    else:
        click.echo("Dry run complete. No files written.")


def _load_config_file(path: Path) -> dict | None:
    """Load and parse a YAML config file."""
    try:
        import yaml
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logging.warning("Failed to load config %s: %s", path, e)
        return None
