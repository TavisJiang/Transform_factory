"""Integration test: run the full pipeline on the minimal project."""

from pathlib import Path

import pytest

from latex2kb.pipeline import PipelineConfig, run_pipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "minimal_project"


@pytest.fixture
def output_dir(tmp_path):
    """Temporary output directory."""
    return tmp_path / "output"


def test_full_pipeline(output_dir):
    """Should run the complete pipeline on the minimal project."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    # Check output structure
    assert (output_dir / "index.md").exists()
    assert (output_dir / "metadata.yaml").exists()
    assert (output_dir / "references.md").exists()
    assert (output_dir / "chapters").is_dir()
    assert (output_dir / "figures").is_dir()


def test_pipeline_produces_chapters(output_dir):
    """Should produce chapter .md files."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    chapters = list((output_dir / "chapters").glob("*.md"))
    assert len(chapters) == 2  # ch1 and ch2


def test_pipeline_copies_figures(output_dir):
    """Should copy referenced figures."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    figures = list((output_dir / "figures").glob("*"))
    assert len(figures) >= 1
    assert any(f.name == "test_image.png" for f in figures)


def test_pipeline_references_md(output_dir):
    """Should generate references with cited entries."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    refs = (output_dir / "references.md").read_text(encoding="utf-8")
    assert "Einstein" in refs
    assert "1905" in refs


def test_pipeline_index_md(output_dir):
    """Should generate index.md with metadata."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    index = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "A Minimal Test Document" in index
    assert "Test Author" in index


def test_pipeline_no_unresolved_placeholders(output_dir):
    """Should not leave unresolved <<REF:>> or <<CITE:>> tokens."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    for md_file in (output_dir / "chapters").glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        assert "<<REF:" not in content, f"Unresolved REF in {md_file.name}"
        assert "<<CITE:" not in content, f"Unresolved CITE in {md_file.name}"
        assert "<<EQREF:" not in content, f"Unresolved EQREF in {md_file.name}"


def test_pipeline_math_preserved(output_dir):
    """Should preserve math formulas."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
    )
    run_pipeline(config)

    # Check that inline math and display math are preserved
    all_content = ""
    for md_file in (output_dir / "chapters").glob("*.md"):
        all_content += md_file.read_text(encoding="utf-8")

    assert "$" in all_content  # Has math delimiters
    assert "e^{i\\pi}" in all_content  # Euler's identity preserved
    assert "$$" in all_content  # Has display math


def test_pipeline_dry_run(output_dir):
    """Dry run should not create files."""
    config = PipelineConfig(
        input_dir=FIXTURES_DIR,
        output_dir=output_dir,
        dry_run=True,
    )
    run_pipeline(config)
    assert not output_dir.exists() or not any(output_dir.iterdir())
