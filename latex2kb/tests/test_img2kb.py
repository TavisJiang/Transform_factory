"""Tests for img2kb pipeline module."""

from pathlib import Path

import pytest

from latex2kb.img2kb_pipeline import (
    ImageAnalysis,
    _fallback_synthesis,
    _parse_analysis_response,
    _scan_images,
    is_image_folder,
)


@pytest.fixture
def image_dir(tmp_path):
    """Create a temp directory with fake image files."""
    for name in ['img1.png', 'img2.jpg', 'img3.jpeg']:
        (tmp_path / name).write_bytes(b'\x89PNG\r\n')
    return tmp_path


@pytest.fixture
def latex_dir(tmp_path):
    """Create a temp directory with .tex files."""
    (tmp_path / 'main.tex').write_text(r'\documentclass{article}')
    (tmp_path / 'fig.png').write_bytes(b'\x89PNG\r\n')
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path):
    """Create an empty temp directory."""
    return tmp_path


def test_is_image_folder_true(image_dir):
    """Pure image folder should be detected."""
    assert is_image_folder(image_dir) is True


def test_is_image_folder_false_latex(latex_dir):
    """Folder with .tex files should NOT be detected as image folder."""
    assert is_image_folder(latex_dir) is False


def test_is_image_folder_false_empty(empty_dir):
    """Empty folder should NOT be detected as image folder."""
    assert is_image_folder(empty_dir) is False


def test_scan_images(image_dir):
    """Should find all image files sorted by name."""
    images = _scan_images(image_dir)
    assert len(images) == 3
    assert images[0].name == 'img1.png'
    assert images[1].name == 'img2.jpg'
    assert images[2].name == 'img3.jpeg'


def test_scan_images_ignores_non_images(image_dir):
    """Should ignore non-image files."""
    (image_dir / 'notes.txt').write_text('hello')
    (image_dir / 'data.csv').write_text('a,b,c')
    images = _scan_images(image_dir)
    assert len(images) == 3  # only the 3 images


def test_parse_analysis_response_valid():
    """Should parse valid JSON response."""
    raw = '{"extracted_text": "E=mc^2", "visual_description": "equation", "is_textualizable": true, "category": "equation"}'
    result = _parse_analysis_response('test.png', raw)
    assert result.extracted_text == "E=mc^2"
    assert result.is_textualizable is True
    assert result.category == "equation"


def test_parse_analysis_response_with_fences():
    """Should handle JSON wrapped in markdown code fences."""
    raw = '```json\n{"extracted_text": "hello", "visual_description": "text", "is_textualizable": true, "category": "text"}\n```'
    result = _parse_analysis_response('test.png', raw)
    assert result.extracted_text == "hello"
    assert result.is_textualizable is True


def test_parse_analysis_response_invalid():
    """Should fallback gracefully on invalid JSON."""
    raw = "This is not JSON at all"
    result = _parse_analysis_response('test.png', raw)
    assert result.is_textualizable is False
    assert result.category == "other"
    assert raw in result.extracted_text


def test_fallback_synthesis():
    """Should produce basic markdown from analyses."""
    analyses = [
        ImageAnalysis("img1.png", "Hello world", "text screenshot", True, "text"),
        ImageAnalysis("img2.png", "", "a circuit diagram", False, "diagram"),
    ]
    md = _fallback_synthesis(analyses)
    assert "Hello world" in md
    assert "![a circuit diagram](figures/img2.png)" in md
    assert "img1.png" not in md.split("Hello world")[1] or "figures/img1.png" not in md
