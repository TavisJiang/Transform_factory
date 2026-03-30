"""Stage 7: Image file handling — copy and optional AI descriptions."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AIConfig:
    """Configuration for AI-powered features (image descriptions, etc.)."""
    provider: str = "anthropic"         # anthropic | openai | openai-compatible
    model: str = ""                     # auto-selected per provider if empty
    api_key: str = ""
    base_url: str = ""                  # only for openai-compatible
    image_prompt: str = (
        "Describe this figure concisely in 1-2 sentences. "
        "Focus on what it shows (data, diagram type, key features)."
    )
    max_tokens: int = 300
    timeout: int = 60

    @property
    def effective_model(self) -> str:
        if self.model:
            return self.model
        defaults = {
            "anthropic": "claude-haiku-4-5-20251001",
            "openai": "gpt-4o-mini",
            "openai-compatible": "gpt-4o-mini",
        }
        return defaults.get(self.provider, "gpt-4o-mini")


def load_ai_config(
    config_dict: dict | None = None,
    cli_api_key: str | None = None,
) -> AIConfig:
    """Build AIConfig from config file dict, env vars, and CLI overrides.

    Priority: CLI flags > env vars > config file > defaults.
    """
    import os

    cfg = AIConfig()

    # Layer 1: config file
    if config_dict:
        ai_section = config_dict.get("ai", {})
        if ai_section:
            cfg.provider = ai_section.get("provider", cfg.provider)
            cfg.model = ai_section.get("model", cfg.model)
            cfg.api_key = ai_section.get("api_key", cfg.api_key)
            cfg.base_url = ai_section.get("base_url", cfg.base_url)
            cfg.timeout = ai_section.get("timeout", cfg.timeout)

    # Layer 2: env vars
    env_key = os.environ.get("LATEX2KB_API_KEY", "")
    if not env_key:
        provider_env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openai-compatible": "OPENAI_API_KEY",
        }
        env_name = provider_env.get(cfg.provider, "")
        env_key = os.environ.get(env_name, "") if env_name else ""
    if env_key:
        cfg.api_key = env_key

    # Layer 3: CLI override (highest priority)
    if cli_api_key:
        cfg.api_key = cli_api_key

    return cfg


def copy_figures(
    source_dirs: list[Path],
    project_dir: Path,
    output_figures_dir: Path,
    referenced_paths: set[str],
) -> dict[str, Path]:
    """Copy referenced image files to the output figures directory.

    Returns a mapping of {relative_name: output_path} for successfully copied files.
    """
    output_figures_dir.mkdir(parents=True, exist_ok=True)
    copied = {}

    for rel_path in referenced_paths:
        src = _find_image(rel_path, source_dirs, project_dir)
        if src is None:
            logger.warning("Image not found: %s", rel_path)
            continue

        dest = output_figures_dir / src.name
        try:
            shutil.copy2(src, dest)
            copied[rel_path] = dest
            logger.debug("Copied: %s -> %s", src, dest)
        except Exception as e:
            logger.warning("Failed to copy %s: %s", src, e)

    logger.info("Copied %d/%d referenced images", len(copied), len(referenced_paths))
    return copied


def _find_image(rel_path: str, source_dirs: list[Path], project_dir: Path) -> Path | None:
    """Find an image file in source directories."""
    candidates = [
        project_dir / rel_path,
        project_dir / 'figures' / rel_path,
    ]

    for d in source_dirs:
        candidates.append(d / rel_path)
        candidates.append(d / Path(rel_path).name)

    base_candidates = list(candidates)
    for c in base_candidates:
        if not c.suffix:
            for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.eps', '.svg']:
                candidates.append(c.with_suffix(ext))

    for c in candidates:
        if c.exists() and c.is_file():
            return c

    return None


def generate_image_description(image_path: Path, ai_config: AIConfig) -> str | None:
    """Call a multimodal AI API to generate a description of an image.

    Supports Anthropic, OpenAI, and OpenAI-compatible providers.
    Returns the description text, or None on failure.
    """
    try:
        import base64
        import httpx
    except ImportError:
        logger.warning("httpx not installed. Install with: pip install latex2kb[ai]")
        return None

    if image_path.suffix.lower() == '.pdf':
        logger.debug("Skipping AI description for PDF: %s", image_path)
        return None

    if not ai_config.api_key:
        logger.warning("No API key configured. Set via --api-key, env var, or config file.")
        return None

    try:
        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        media_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(image_path.suffix.lower(), 'image/png')

        provider = ai_config.provider.lower()
        if provider == "anthropic":
            return _call_anthropic(image_data, media_type, ai_config)
        elif provider in ("openai", "openai-compatible"):
            return _call_openai(image_data, media_type, ai_config)
        else:
            logger.warning("Unknown AI provider: %s", provider)
            return None

    except Exception as e:
        logger.warning("Failed to generate image description for %s: %s", image_path, e)
        return None


def call_ai_text(prompt: str, ai_config: AIConfig, max_tokens: int | None = None) -> str | None:
    """Call AI with a text-only prompt (no image). Used for synthesis."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed. Install with: pip install latex2kb[ai]")
        return None
    if not ai_config.api_key:
        return None
    tokens = max_tokens or ai_config.max_tokens
    provider = ai_config.provider.lower()
    try:
        if provider == "anthropic":
            response = httpx.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': ai_config.api_key, 'anthropic-version': '2023-06-01',
                         'content-type': 'application/json'},
                json={'model': ai_config.effective_model, 'max_tokens': tokens,
                      'messages': [{'role': 'user', 'content': prompt}]},
                timeout=ai_config.timeout,
            )
            response.raise_for_status()
            return response.json()['content'][0]['text'].strip()
        elif provider in ("openai", "openai-compatible"):
            base_url = ai_config.base_url or 'https://api.openai.com/v1'
            response = httpx.post(
                f'{base_url.rstrip("/")}/chat/completions',
                headers={'Authorization': f'Bearer {ai_config.api_key}',
                         'Content-Type': 'application/json'},
                json={'model': ai_config.effective_model, 'max_tokens': tokens,
                      'messages': [{'role': 'user', 'content': prompt}]},
                timeout=ai_config.timeout,
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            return None
    except Exception as e:
        logger.warning("AI text call failed: %s", e)
        return None


def _call_anthropic(image_data: str, media_type: str, cfg: AIConfig) -> str | None:
    """Call Anthropic Messages API."""
    import httpx

    response = httpx.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': cfg.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': cfg.effective_model,
            'max_tokens': cfg.max_tokens,
            'messages': [{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': image_data,
                        },
                    },
                    {
                        'type': 'text',
                        'text': cfg.image_prompt,
                    },
                ],
            }],
        },
        timeout=cfg.timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data['content'][0]['text'].strip()


def _call_openai(image_data: str, media_type: str, cfg: AIConfig) -> str | None:
    """Call OpenAI (or compatible) Chat Completions API."""
    import httpx

    base_url = cfg.base_url or 'https://api.openai.com/v1'
    url = f'{base_url.rstrip("/")}/chat/completions'

    response = httpx.post(
        url,
        headers={
            'Authorization': f'Bearer {cfg.api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': cfg.effective_model,
            'max_tokens': cfg.max_tokens,
            'messages': [{
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:{media_type};base64,{image_data}',
                        },
                    },
                    {
                        'type': 'text',
                        'text': cfg.image_prompt,
                    },
                ],
            }],
        },
        timeout=cfg.timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data['choices'][0]['message']['content'].strip()
