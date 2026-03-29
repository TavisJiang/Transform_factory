"""Tests for macro_resolver module."""

import pytest

from latex2kb.macro_resolver import (
    MacroDef,
    build_macro_table,
    expand_macro,
    extract_newcommands,
    extract_newtheorems,
)


def test_extract_simple_newcommand():
    """Should extract a simple \\newcommand with one argument."""
    source = r"\newcommand{\highlight}[1]{\textbf{#1}}"
    macros = extract_newcommands(source)
    assert len(macros) == 1
    assert macros[0].name == "highlight"
    assert macros[0].num_args == 1
    assert r"\textbf{#1}" in macros[0].body


def test_extract_zero_arg_command():
    """Should extract a \\newcommand with no arguments."""
    source = r"\newcommand{\dif}{\mathrm{d}}"
    macros = extract_newcommands(source)
    assert len(macros) == 1
    assert macros[0].name == "dif"
    assert macros[0].num_args == 0
    assert macros[0].is_math is True  # contains \mathrm


def test_extract_declare_robust():
    """Should extract \\DeclareRobustCommand."""
    source = r"\DeclareRobustCommand\code[1]{\texttt{#1}}"
    macros = extract_newcommands(source)
    assert len(macros) == 1
    assert macros[0].name == "code"
    assert macros[0].num_args == 1


def test_extract_renewcommand():
    """Should extract \\renewcommand."""
    source = r"\renewcommand{\vec}[1]{\boldsymbol{#1}}"
    macros = extract_newcommands(source)
    assert len(macros) == 1
    assert macros[0].name == "vec"


def test_is_math_detection():
    """Should detect math-mode macros by body content."""
    math_source = r"\newcommand{\eu}{{\symup{e}}}"
    text_source = r"\newcommand{\red}[1]{\textcolor{red}{#1}}"

    math_macros = extract_newcommands(math_source)
    text_macros = extract_newcommands(text_source)

    assert math_macros[0].is_math is True
    assert text_macros[0].is_math is False


def test_expand_macro():
    """Should expand macro with arguments."""
    macro = MacroDef(name="highlight", num_args=1, default_opt=None,
                     body=r"\textbf{#1}", is_math=False)
    result = expand_macro(macro, ["hello"])
    assert result == r"\textbf{hello}"


def test_expand_macro_multiple_args():
    """Should expand macro with multiple arguments."""
    macro = MacroDef(name="frac", num_args=2, default_opt=None,
                     body=r"\frac{#1}{#2}", is_math=True)
    result = expand_macro(macro, ["a", "b"])
    assert result == r"\frac{a}{b}"


def test_extract_newtheorems():
    """Should extract \\newtheorem definitions."""
    source = r"""
    \newtheorem{theorem}{Theorem}
    \newtheorem{fact}{Fact}
    \newtheorem*{remark}{Remark}
    """
    theorems = extract_newtheorems(source)
    assert "theorem" in theorems
    assert theorems["theorem"] == "Theorem"
    assert "fact" in theorems
    assert theorems["fact"] == "Fact"
    assert "remark" in theorems


def test_skip_commented_definitions():
    """Should skip commented-out \\newcommand lines."""
    source = r"""
    % \newcommand{\old}[1]{\textit{#1}}
    \newcommand{\active}[1]{\textbf{#1}}
    """
    macros = extract_newcommands(source)
    names = {m.name for m in macros}
    assert "active" in names
    assert "old" not in names


def test_build_macro_table(minimal_project_dir):
    """Should build a macro table from preamble source."""
    from latex2kb.project_scanner import scan_project
    info = scan_project(minimal_project_dir)
    table = build_macro_table(info.preamble_source, info.root_dir)
    assert table.has("vect")
    assert table.has("highlight")
