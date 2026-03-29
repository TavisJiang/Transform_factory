"""Tests for bibliography module."""

from pathlib import Path

import pytest

from latex2kb.bibliography import generate_references_md, parse_bib_file

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "minimal_project"


def test_parse_bib_file():
    """Should parse .bib file into entries dict."""
    bib_path = FIXTURES_DIR / "refs.bib"
    entries = parse_bib_file(bib_path)
    assert "Einstein1905" in entries
    assert "Smith2020" in entries
    assert "Jones2021" in entries
    assert entries["Einstein1905"]["author"] == "Albert Einstein"
    assert entries["Einstein1905"]["year"] == "1905"


def test_parse_bib_entry_types():
    """Should handle different entry types."""
    bib_path = FIXTURES_DIR / "refs.bib"
    entries = parse_bib_file(bib_path)
    assert entries["Einstein1905"]["ENTRYTYPE"] == "article"
    assert entries["Jones2021"]["ENTRYTYPE"] == "inproceedings"


def test_generate_references_md():
    """Should generate formatted references markdown."""
    entries = {
        "Einstein1905": {
            "ID": "Einstein1905",
            "ENTRYTYPE": "article",
            "author": "Albert Einstein",
            "title": "On the Electrodynamics of Moving Bodies",
            "journal": "Annalen der Physik",
            "year": "1905",
            "volume": "322",
            "pages": "891--921",
            "doi": "10.1002/andp.19053221004",
        },
    }
    cited = {"Einstein1905"}
    md = generate_references_md(entries, cited)

    assert "# References" in md
    assert "Einstein" in md
    assert "1905" in md
    assert "Annalen der Physik" in md
    assert "DOI" in md
    assert '<a id="Einstein1905"></a>' in md


def test_generate_references_only_cited():
    """Should only include cited entries."""
    entries = {
        "Used2020": {
            "ID": "Used2020",
            "ENTRYTYPE": "article",
            "author": "A Author",
            "title": "Used Paper",
            "year": "2020",
        },
        "Unused2021": {
            "ID": "Unused2021",
            "ENTRYTYPE": "article",
            "author": "B Author",
            "title": "Unused Paper",
            "year": "2021",
        },
    }
    cited = {"Used2020"}
    md = generate_references_md(entries, cited)
    assert "Used Paper" in md
    assert "Unused Paper" not in md


def test_generate_references_multiple_authors():
    """Should format multiple authors correctly."""
    entries = {
        "Multi2021": {
            "ID": "Multi2021",
            "ENTRYTYPE": "article",
            "author": "Alice One and Bob Two and Charlie Three and Dave Four",
            "title": "Multi Author Paper",
            "year": "2021",
        },
    }
    md = generate_references_md(entries, {"Multi2021"})
    assert "et al." in md
