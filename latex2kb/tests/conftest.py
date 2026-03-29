"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MINIMAL_PROJECT = FIXTURES_DIR / "minimal_project"


@pytest.fixture
def minimal_project_dir():
    """Path to the minimal test LaTeX project."""
    return MINIMAL_PROJECT


@pytest.fixture
def sample_preamble():
    """A sample LaTeX preamble with custom commands."""
    return r"""
\documentclass{article}
\usepackage{amsmath}
\newcommand{\vect}[1]{\mathbf{#1}}
\newcommand{\highlight}[1]{\textbf{#1}}
\newcommand{\dif}{\mathrm{d}}
\DeclareRobustCommand\code[1]{\texttt{#1}}
\graphicspath{{figures/}}
\title{Test Document}
\author{Test Author}
"""
