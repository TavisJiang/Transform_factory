"""Tests for project_scanner module."""

from pathlib import Path

import pytest

from latex2kb.project_scanner import (
    FileRole,
    IncludeType,
    find_main_tex,
    get_chapter_entries,
    scan_project,
)


def test_find_main_tex(minimal_project_dir):
    """Should find main.tex containing \\documentclass."""
    main = find_main_tex(minimal_project_dir)
    assert main.name == "main.tex"
    assert main.exists()


def test_find_main_tex_override(minimal_project_dir):
    """Should use the override path if provided."""
    main = find_main_tex(minimal_project_dir, "main.tex")
    assert main.name == "main.tex"


def test_find_main_tex_missing(tmp_path):
    """Should raise FileNotFoundError if no main tex found."""
    (tmp_path / "empty.tex").write_text("no documentclass here")
    with pytest.raises(FileNotFoundError):
        find_main_tex(tmp_path)


def test_scan_project_structure(minimal_project_dir):
    """Should discover project structure correctly."""
    info = scan_project(minimal_project_dir)
    assert info.document_class == "article"
    assert info.main_tex.name == "main.tex"


def test_scan_project_entries(minimal_project_dir):
    """Should find \\input chapter entries."""
    info = scan_project(minimal_project_dir)
    # Should find ch1.tex and ch2.tex via \input
    mainmatter = [e for e in info.entries if e.role == FileRole.MAINMATTER]
    assert len(mainmatter) == 2
    names = {e.path.stem for e in mainmatter}
    assert "ch1" in names
    assert "ch2" in names


def test_scan_project_include_type(minimal_project_dir):
    """\\input entries should have INPUT include type."""
    info = scan_project(minimal_project_dir)
    mainmatter = [e for e in info.entries if e.role == FileRole.MAINMATTER]
    for entry in mainmatter:
        assert entry.include_type == IncludeType.INPUT


def test_scan_project_graphics_path(minimal_project_dir):
    """Should detect \\graphicspath."""
    info = scan_project(minimal_project_dir)
    assert len(info.graphics_paths) >= 1
    assert any("figures" in str(p) for p in info.graphics_paths)


def test_scan_project_bibliography(minimal_project_dir):
    """Should detect \\bibliography path."""
    info = scan_project(minimal_project_dir)
    assert len(info.bib_paths) == 1
    assert info.bib_paths[0].stem == "refs"


def test_get_chapter_entries(minimal_project_dir):
    """get_chapter_entries should return ordered mainmatter entries."""
    info = scan_project(minimal_project_dir)
    chapters = get_chapter_entries(info)
    assert len(chapters) == 2
    assert chapters[0].order < chapters[1].order


def test_preamble_source_includes_inputs(minimal_project_dir):
    """preamble_source should contain custom commands from main.tex preamble."""
    info = scan_project(minimal_project_dir)
    assert r"\newcommand{\vect}" in info.preamble_source
    assert r"\newcommand{\highlight}" in info.preamble_source
