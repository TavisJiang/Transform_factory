"""Stage 3: LaTeX parser using pylatexenc 2.x + custom handling.

Parses LaTeX source into a stream of content nodes that the converter can walk.
Uses pylatexenc for proper brace/environment matching and a custom layer for
conversion-specific node types.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
    LatexWalker,
    get_default_latex_context_db,
)
from pylatexenc.macrospec import (
    EnvironmentSpec,
    LatexContextDb,
    MacroSpec,
)

from latex2kb.macro_resolver import MacroTable

logger = logging.getLogger(__name__)


def build_context_db(macro_table: MacroTable) -> LatexContextDb:
    """Build a pylatexenc context database with custom macros registered."""
    db = get_default_latex_context_db()

    # Register common physics/math macros
    extra_macros = [
        MacroSpec('ket', '{'),
        MacroSpec('bra', '{'),
        MacroSpec('braket', '{{'),
        MacroSpec('ketbra', '{{'),
        MacroSpec('proj', '{'),
        MacroSpec('mel', '{{{'),
        MacroSpec('ev', '{'),
        MacroSpec('expval', '{'),
        MacroSpec('abs', '{'),
        MacroSpec('norm', '{'),
        MacroSpec('qty', '{'),
        MacroSpec('dv', '{{'),
        MacroSpec('pdv', '{{'),
        MacroSpec('dd', '{'),
        MacroSpec('comm', '{{'),
        MacroSpec('acomm', '{{'),
        # Text formatting
        MacroSpec('textbf', '{'),
        MacroSpec('textit', '{'),
        MacroSpec('textrm', '{'),
        MacroSpec('texttt', '{'),
        MacroSpec('textsf', '{'),
        MacroSpec('emph', '{'),
        MacroSpec('underline', '{'),
        MacroSpec('textcolor', '{{'),
        # References
        MacroSpec('ref', '{'),
        MacroSpec('eqref', '{'),
        MacroSpec('cite', '[{'),
        MacroSpec('citep', '[{'),
        MacroSpec('citet', '[{'),
        # biblatex citation commands
        MacroSpec('autocite', '[{'),
        MacroSpec('parencite', '[{'),
        MacroSpec('textcite', '[{'),
        MacroSpec('fullcite', '{'),
        MacroSpec('footcite', '[{'),
        MacroSpec('nocite', '{'),
        MacroSpec('Autocite', '[{'),
        MacroSpec('Parencite', '[{'),
        MacroSpec('Textcite', '[{'),
        MacroSpec('label', '{'),
        MacroSpec('caption', '{'),
        MacroSpec('bicaption', '{{'),
        # Sections
        MacroSpec('chapter', '*[{'),
        MacroSpec('section', '*[{'),
        MacroSpec('subsection', '*[{'),
        MacroSpec('subsubsection', '*[{'),
        MacroSpec('paragraph', '{'),
        # Figures
        MacroSpec('includegraphics', '[{'),
        MacroSpec('graphicspath', '{'),
        # Footnotes
        MacroSpec('footnote', '{'),
        # Math
        MacroSpec('frac', '{{'),
        MacroSpec('sqrt', '[{'),
        MacroSpec('mathrm', '{'),
        MacroSpec('mathbf', '{'),
        MacroSpec('mathbb', '{'),
        MacroSpec('mathcal', '{'),
        MacroSpec('boldsymbol', '{'),
        MacroSpec('hat', '{'),
        MacroSpec('tilde', '{'),
        MacroSpec('bar', '{'),
        MacroSpec('vec', '{'),
        MacroSpec('dot', '{'),
        MacroSpec('ddot', '{'),
        MacroSpec('overline', '{'),
        MacroSpec('overbrace', '{'),
        MacroSpec('underbrace', '{'),
        # SI units
        MacroSpec('SI', '{{'),
        MacroSpec('si', '{'),
        MacroSpec('num', '{'),
        MacroSpec('qty', '{{'),
        # Misc
        MacroSpec('url', '{'),
        MacroSpec('href', '{{'),
        MacroSpec('nolinkurl', '{'),
        MacroSpec('red', '{'),
        MacroSpec('hyperref', '[{'),
    ]

    extra_envs = [
        EnvironmentSpec('figure', '['),
        EnvironmentSpec('figure*', '['),
        EnvironmentSpec('table', '['),
        EnvironmentSpec('table*', '['),
        EnvironmentSpec('tabular', '{'),
        EnvironmentSpec('tabular*', '{{'),
        EnvironmentSpec('longtable', '{'),
        EnvironmentSpec('equation', ''),
        EnvironmentSpec('equation*', ''),
        EnvironmentSpec('align', ''),
        EnvironmentSpec('align*', ''),
        EnvironmentSpec('multline', ''),
        EnvironmentSpec('multline*', ''),
        EnvironmentSpec('gather', ''),
        EnvironmentSpec('gather*', ''),
        EnvironmentSpec('split', ''),
        EnvironmentSpec('cases', ''),
        EnvironmentSpec('pmatrix', ''),
        EnvironmentSpec('bmatrix', ''),
        EnvironmentSpec('vmatrix', ''),
        EnvironmentSpec('Bmatrix', ''),
        EnvironmentSpec('Vmatrix', ''),
        EnvironmentSpec('array', '{'),
        EnvironmentSpec('itemize', ''),
        EnvironmentSpec('enumerate', '['),
        EnvironmentSpec('description', ''),
        EnvironmentSpec('theorem', '['),
        EnvironmentSpec('lemma', '['),
        EnvironmentSpec('proposition', '['),
        EnvironmentSpec('corollary', '['),
        EnvironmentSpec('definition', '['),
        EnvironmentSpec('example', '['),
        EnvironmentSpec('remark', '['),
        EnvironmentSpec('fact', '['),
        EnvironmentSpec('proof', '['),
        EnvironmentSpec('algorithm', '['),
        EnvironmentSpec('algorithm2e', '['),
        EnvironmentSpec('mdframed', '['),
        EnvironmentSpec('framed', ''),
        EnvironmentSpec('abstract', ''),
        EnvironmentSpec('quotation', ''),
        EnvironmentSpec('quote', ''),
        EnvironmentSpec('center', ''),
        EnvironmentSpec('flushleft', ''),
        EnvironmentSpec('flushright', ''),
        EnvironmentSpec('minipage', '[{'),
        EnvironmentSpec('threeparttable', ''),
        EnvironmentSpec('tablenotes', '['),
        # Code listing environments
        EnvironmentSpec('minted', '[{'),
        EnvironmentSpec('listing', '['),
        EnvironmentSpec('lstlisting', '['),
        EnvironmentSpec('verbatim', ''),
        EnvironmentSpec('Verbatim', '['),
        # Beamer
        EnvironmentSpec('frame', '['),
        EnvironmentSpec('block', '{'),
        EnvironmentSpec('columns', '['),
        EnvironmentSpec('column', '{'),
    ]

    # Register macros from the project's macro table
    for name, macro_def in macro_table.macros.items():
        arg_spec = '{' * macro_def.num_args
        if macro_def.default_opt is not None:
            arg_spec = '[' + arg_spec
        extra_macros.append(MacroSpec(name, arg_spec))

    db.add_context_category(
        'latex2kb-custom',
        macros=extra_macros,
        environments=extra_envs,
    )

    return db


def parse_latex(source: str, context_db: LatexContextDb) -> list:
    """Parse LaTeX source into a pylatexenc node list.

    Returns a list of pylatexenc nodes. Handles parse errors gracefully
    by logging warnings and returning partial results.
    """
    try:
        walker = LatexWalker(source, latex_context=context_db)
        nodes, _, _ = walker.get_latex_nodes()
        return nodes
    except Exception as e:
        logger.warning("pylatexenc parse error: %s — falling back to raw text", e)
        return [LatexCharsNode(
            parsing_state=None,
            chars=source,
            pos=0,
            len=len(source),
        )]


def get_node_text(node) -> str:
    """Extract raw LaTeX text from a node (for math content preservation)."""
    if node is None:
        return ''
    if hasattr(node, 'latex_verbatim'):
        return node.latex_verbatim() or ''
    if isinstance(node, LatexCharsNode):
        return node.chars
    if isinstance(node, LatexGroupNode):
        return '{' + ''.join(get_node_text(n) for n in (node.nodelist or [])) + '}'
    if isinstance(node, LatexMacroNode):
        return _reconstruct_macro_latex(node)
    if isinstance(node, LatexEnvironmentNode):
        return _reconstruct_env_latex(node)
    if isinstance(node, LatexMathNode):
        delimiters = node.delimiters
        inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
        return f'{delimiters[0]}{inner}{delimiters[1]}'
    if isinstance(node, LatexCommentNode):
        return ''
    if hasattr(node, 'nodelist') and node.nodelist:
        return ''.join(get_node_text(n) for n in node.nodelist)
    return ''


def _reconstruct_macro_latex(node: LatexMacroNode) -> str:
    """Reconstruct LaTeX source for a macro node."""
    result = '\\' + node.macroname
    if node.nodeargd and node.nodeargd.argnlist:
        for arg_node in node.nodeargd.argnlist:
            if arg_node is None:
                continue
            if isinstance(arg_node, LatexGroupNode):
                inner = ''.join(get_node_text(n) for n in (arg_node.nodelist or []))
                if arg_node.delimiters and arg_node.delimiters[0] == '[':
                    result += f'[{inner}]'
                else:
                    result += f'{{{inner}}}'
            else:
                result += get_node_text(arg_node)
    return result


def _reconstruct_env_latex(node: LatexEnvironmentNode) -> str:
    """Reconstruct LaTeX source for an environment node."""
    name = node.environmentname
    inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
    args = ''
    if node.nodeargd and node.nodeargd.argnlist:
        for arg_node in node.nodeargd.argnlist:
            if arg_node is None:
                continue
            args += get_node_text(arg_node)
    return f'\\begin{{{name}}}{args}{inner}\\end{{{name}}}'


def get_macro_arg(node: LatexMacroNode, index: int) -> str:
    """Get the text content of a macro's argument by index."""
    if not node.nodeargd or not node.nodeargd.argnlist:
        return ''
    args = node.nodeargd.argnlist
    if index >= len(args) or args[index] is None:
        return ''
    arg = args[index]
    if isinstance(arg, LatexGroupNode):
        return ''.join(get_node_text(n) for n in (arg.nodelist or []))
    return get_node_text(arg)


def get_macro_opt_arg(node: LatexMacroNode) -> str | None:
    """Get the optional argument of a macro, if present."""
    if not node.nodeargd or not node.nodeargd.argnlist:
        return None
    for arg in node.nodeargd.argnlist:
        if arg is None:
            continue
        if isinstance(arg, LatexGroupNode) and arg.delimiters and arg.delimiters[0] == '[':
            return ''.join(get_node_text(n) for n in (arg.nodelist or []))
    return None
