"""Tests for crossref module."""

import pytest

from latex2kb.converter import LabelInfo
from latex2kb.crossref import resolve_citations, resolve_references


@pytest.fixture
def labels():
    """Sample label registry."""
    return {
        "fig:diagram": LabelInfo(
            key="fig:diagram",
            file="chapters/01-intro.md",
            anchor="fig-diagram",
            kind="fig",
            chapter_num=1,
            local_num=1,
        ),
        "eq:euler": LabelInfo(
            key="eq:euler",
            file="chapters/01-intro.md",
            anchor="eq-euler",
            kind="eq",
            chapter_num=1,
            local_num=1,
        ),
        "sec:methods": LabelInfo(
            key="sec:methods",
            file="chapters/02-methods.md",
            anchor="sec-methods",
            kind="sec",
            chapter_num=2,
            local_num=1,
        ),
    }


def test_resolve_same_file_ref(labels):
    """Should create same-file anchor link."""
    md = "See <<REF:fig:diagram>> for details."
    result = resolve_references(md, "chapters/01-intro.md", labels)
    assert "[Figure 1.1](#fig-diagram)" in result
    assert "<<REF:" not in result


def test_resolve_cross_file_ref(labels):
    """Should create cross-file link."""
    md = "See <<REF:sec:methods>> for the method."
    result = resolve_references(md, "chapters/01-intro.md", labels)
    assert "02-methods.md#sec-methods" in result
    assert "Section" in result


def test_resolve_eqref(labels):
    """Should resolve equation references."""
    md = "From <<EQREF:eq:euler>> we derive..."
    result = resolve_references(md, "chapters/01-intro.md", labels)
    assert "Eq." in result
    assert "#eq-euler" in result


def test_unresolved_ref(labels):
    """Should mark unresolved references."""
    md = "See <<REF:nonexistent>> here."
    result = resolve_references(md, "chapters/01-intro.md", labels)
    assert "[??nonexistent??]" in result


def test_resolve_citations():
    """Should expand citations to [Author, Year] links."""
    bib_entries = {
        "Einstein1905": {
            "author": "Albert Einstein",
            "year": "1905",
            "title": "On the Electrodynamics of Moving Bodies",
        },
        "Smith2020": {
            "author": "John Smith and Jane Doe",
            "year": "2020",
            "title": "A Novel Method",
        },
    }
    md = "As shown in <<CITE:Einstein1905>> and <<CITE:Smith2020>>."
    result = resolve_citations(md, bib_entries)
    assert "[Einstein, 1905]" in result
    assert "[Smith & Doe, 2020]" in result
    assert "references.md#Einstein1905" in result


def test_unresolved_citation():
    """Should handle missing citations gracefully."""
    md = "See <<CITE:missing_key>>."
    result = resolve_citations(md, {})
    assert "[missing_key]" in result
