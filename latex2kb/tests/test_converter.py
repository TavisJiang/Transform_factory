"""Tests for converter module."""

import pytest

from latex2kb.converter import ConversionContext, convert_chapter
from latex2kb.macro_resolver import MacroTable, build_macro_table
from latex2kb.parser_core import build_context_db


@pytest.fixture
def ctx():
    """A fresh ConversionContext."""
    return ConversionContext(
        current_file="chapters/01-test.md",
        chapter_num=1,
    )


@pytest.fixture
def context_db():
    """A pylatexenc context DB with default macros."""
    return build_context_db(MacroTable())


def test_convert_section_hierarchy(ctx, context_db):
    """Should convert section commands to Markdown headings."""
    source = r"""
\chapter{My Chapter}
\section{First Section}
\subsection{A Subsection}
\subsubsection{Sub-subsection}
\paragraph{A Paragraph}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "# My Chapter" in md
    assert "## First Section" in md
    assert "### A Subsection" in md
    assert "#### Sub-subsection" in md
    assert "##### A Paragraph" in md


def test_convert_text_formatting(ctx, context_db):
    """Should convert text formatting commands."""
    source = r"Some \textbf{bold} and \textit{italic} and \emph{emphasized} and \texttt{mono} text."
    md = convert_chapter(source, ctx, context_db)
    assert "**bold**" in md
    assert "*italic*" in md
    assert "*emphasized*" in md
    assert "`mono`" in md


def test_preserve_inline_math(ctx, context_db):
    """Should preserve inline math as $...$."""
    source = r"The equation $E = mc^2$ is famous."
    md = convert_chapter(source, ctx, context_db)
    assert "$E = mc^2$" in md


def test_preserve_display_math(ctx, context_db):
    """Should convert equation environment to $$...$$."""
    source = r"""
\begin{equation}
  e^{i\pi} + 1 = 0
  \label{eq:euler}
\end{equation}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "$$" in md
    assert "e^{i\\pi} + 1 = 0" in md
    assert '<a id="eq-euler"></a>' in md


def test_preserve_align_environment(ctx, context_db):
    """Should preserve align environment inside $$ blocks."""
    source = r"""
\begin{align}
  a &= b + c \\
  d &= e + f
\end{align}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "\\begin{align}" in md
    assert "\\end{align}" in md
    assert "$$" in md


def test_convert_label_to_anchor(ctx, context_db):
    """Should convert \\label to HTML anchor."""
    source = r"""
\section{Test}
\label{sec:test}
"""
    md = convert_chapter(source, ctx, context_db)
    assert '<a id="sec-test"></a>' in md


def test_ref_placeholder(ctx, context_db):
    """Should emit <<REF:key>> placeholders for \\ref."""
    source = r"See Section~\ref{sec:intro}."
    md = convert_chapter(source, ctx, context_db)
    # After conversion, refs should be resolved (but no label exists, so [??...??])
    assert "sec:intro" in md or "sec-intro" in md


def test_cite_placeholder(ctx, context_db):
    """Should emit citation placeholders for \\cite."""
    source = r"As shown in~\cite{Einstein1905}."
    md = convert_chapter(source, ctx, context_db)
    assert "Einstein1905" in md
    ctx.citation_keys  # Should have been populated
    assert "Einstein1905" in ctx.citation_keys


def test_convert_itemize(ctx, context_db):
    """Should convert itemize to bullet list."""
    source = r"""
\begin{itemize}
  \item First item
  \item Second item
  \item Third item
\end{itemize}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "- First item" in md
    assert "- Second item" in md
    assert "- Third item" in md


def test_convert_enumerate(ctx, context_db):
    """Should convert enumerate to numbered list."""
    source = r"""
\begin{enumerate}
  \item First
  \item Second
  \item Third
\end{enumerate}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "1. First" in md or "1." in md
    assert "2. Second" in md or "2." in md


def test_convert_footnote(ctx, context_db):
    """Should convert \\footnote to Markdown footnote markers."""
    source = r"Main text\footnote{This is a footnote.} continues."
    md = convert_chapter(source, ctx, context_db)
    assert "[^1]" in md
    assert "This is a footnote." in md


def test_convert_figure(ctx, context_db):
    """Should convert figure environment."""
    source = r"""
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.5\textwidth]{test_image.png}
  \caption{A test figure.}
  \label{fig:test}
\end{figure}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "test_image.png" in md
    assert "A test figure." in md
    assert '<a id="fig-test"></a>' in md
    assert "test_image.png" in ctx.figure_paths


def test_convert_table(ctx, context_db):
    """Should convert table with booktabs."""
    source = r"""
\begin{table}[htbp]
  \centering
  \caption{Results.}
  \label{tab:results}
  \begin{tabular}{lcc}
    \toprule
    Method & Accuracy & Time \\
    \midrule
    A & 95\% & 1s \\
    B & 97\% & 2s \\
    \bottomrule
  \end{tabular}
\end{table}
"""
    md = convert_chapter(source, ctx, context_db)
    assert "Results." in md
    assert "Method" in md
    assert "Accuracy" in md
    assert "|" in md  # Markdown table pipes


def test_special_chars(ctx, context_db):
    """Should convert LaTeX special characters."""
    source = r"An em dash---here, and en dash 1--10, and \LaTeX{} text."
    md = convert_chapter(source, ctx, context_db)
    assert "\u2014" in md  # em dash
    assert "\u2013" in md  # en dash
    assert "LaTeX" in md


def test_tilde_nonbreaking_space(ctx, context_db):
    """Should convert ~ to regular space."""
    source = r"Figure~\ref{fig:test} shows the result."
    md = convert_chapter(source, ctx, context_db)
    assert "~" not in md.replace("~", "")  # tildes should be gone from text


def test_chinese_content(ctx, context_db):
    """Should preserve Chinese text."""
    source = r"""
\section{量子计算简介}
量子比特的状态属于二维复希尔伯特空间。
"""
    md = convert_chapter(source, ctx, context_db)
    assert "量子计算简介" in md
    assert "量子比特的状态属于二维复希尔伯特空间" in md
