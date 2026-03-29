"""Stage 4: Convert pylatexenc AST nodes to Markdown.

This is the core converter that walks the AST and dispatches to
environment-specific handlers. It emits placeholder tokens for
cross-references and citations that are resolved in later stages.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
)

from latex2kb.environments.algorithm import convert_algorithm
from latex2kb.environments.figure import convert_figure
from latex2kb.environments.math import (
    ALL_MATH_ENVS,
    DISPLAY_MATH_ENVS,
    convert_display_math,
)
from latex2kb.environments.table import convert_table_float, convert_tabular
from latex2kb.environments.theorem import (
    PROOF_ENVS,
    THEOREM_DISPLAY_NAMES,
    convert_proof,
    convert_theorem,
)
from latex2kb.macro_resolver import MacroTable, expand_macro
from latex2kb.parser_core import get_macro_arg, get_macro_opt_arg, get_node_text

logger = logging.getLogger(__name__)


@dataclass
class LabelInfo:
    key: str
    file: str
    anchor: str
    kind: str       # fig, eq, sec, chap, tab, thm
    chapter_num: int = 0
    local_num: int = 0

    @property
    def display(self) -> str:
        """Generate display text like 'Figure 2.3'."""
        kind_names = {
            'fig': 'Figure',
            'eq': 'Eq.',
            'sec': 'Section',
            'subsec': 'Section',
            'chap': 'Chapter',
            'tab': 'Table',
            'thm': 'Theorem',
            'alg': 'Algorithm',
        }
        name = kind_names.get(self.kind, self.kind)
        if self.kind == 'chap':
            return f'{name} {self.chapter_num}'
        if self.kind == 'eq':
            return f'{name} ({self.chapter_num}.{self.local_num})'
        return f'{name} {self.chapter_num}.{self.local_num}'


@dataclass
class ConversionContext:
    """Tracks state during AST-to-Markdown conversion."""
    current_file: str = ""
    chapter_num: int = 0
    # Counters for numbering
    section_counter: int = 0
    subsection_counter: int = 0
    figure_counter: int = 0
    table_counter: int = 0
    equation_counter: int = 0
    theorem_counters: dict[str, int] = field(default_factory=dict)
    footnote_counter: int = 0
    # Registries
    labels: dict[str, LabelInfo] = field(default_factory=dict)
    citation_keys: set[str] = field(default_factory=set)
    figure_paths: set[str] = field(default_factory=set)
    footnotes: list[tuple[int, str]] = field(default_factory=list)
    # Configuration
    macro_table: MacroTable = field(default_factory=MacroTable)
    theorem_names: dict[str, str] = field(default_factory=dict)
    graphics_paths: list[str] = field(default_factory=list)

    def next_equation(self) -> str:
        self.equation_counter += 1
        return f'{self.chapter_num}.{self.equation_counter}'

    def next_figure(self) -> str:
        self.figure_counter += 1
        return f'{self.chapter_num}.{self.figure_counter}'

    def next_table(self) -> str:
        self.table_counter += 1
        return f'{self.chapter_num}.{self.table_counter}'

    def next_theorem(self, env_name: str) -> str:
        # All theorem-like envs share one counter per chapter
        if 'theorem' not in self.theorem_counters:
            self.theorem_counters['theorem'] = 0
        self.theorem_counters['theorem'] += 1
        return f'{self.chapter_num}.{self.theorem_counters["theorem"]}'

    def next_footnote(self) -> int:
        self.footnote_counter += 1
        return self.footnote_counter

    def register_label(self, key: str, kind: str, local_num: int = 0) -> LabelInfo:
        anchor = key.replace(':', '-')
        info = LabelInfo(
            key=key,
            file=self.current_file,
            anchor=anchor,
            kind=kind,
            chapter_num=self.chapter_num,
            local_num=local_num,
        )
        self.labels[key] = info
        return info

    def reset_chapter_counters(self) -> None:
        self.section_counter = 0
        self.subsection_counter = 0
        self.figure_counter = 0
        self.table_counter = 0
        self.equation_counter = 0
        self.theorem_counters.clear()
        self.footnote_counter = 0
        self.footnotes.clear()


def convert_nodes(nodes: list, ctx: ConversionContext) -> str:
    """Convert a list of pylatexenc nodes to Markdown text."""
    parts = []
    for node in nodes:
        md = convert_node(node, ctx)
        if md is not None:
            parts.append(md)
    return ''.join(parts)


def convert_node(node, ctx: ConversionContext) -> str:
    """Convert a single AST node to Markdown."""
    if node is None:
        return ''

    if isinstance(node, LatexCharsNode):
        return _convert_chars(node, ctx)

    if isinstance(node, LatexCommentNode):
        return ''

    if isinstance(node, LatexMathNode):
        return _convert_math(node, ctx)

    if isinstance(node, LatexMacroNode):
        return _convert_macro(node, ctx)

    if isinstance(node, LatexEnvironmentNode):
        return _convert_environment(node, ctx)

    if isinstance(node, LatexGroupNode):
        return convert_nodes(node.nodelist or [], ctx)

    # Handle LatexSpecialsNode (---, --, ``, etc.)
    if hasattr(node, 'specials_chars'):
        sc = node.specials_chars
        if sc == '---':
            return '\u2014'
        if sc == '--':
            return '\u2013'
        if sc == '``':
            return '\u201c'
        if sc == "''":
            return '\u201d'
        return sc

    # Fallback: try to get node list
    if hasattr(node, 'nodelist') and node.nodelist:
        return convert_nodes(node.nodelist, ctx)

    return ''


def _convert_chars(node: LatexCharsNode, ctx: ConversionContext) -> str:
    """Convert plain text characters."""
    text = node.chars
    # Clean up common LaTeX-isms
    text = text.replace('~', ' ')  # non-breaking space
    text = text.replace('``', '\u201c')  # left double quote
    text = text.replace("''", '\u201d')  # right double quote
    # Em/en dash: must check --- before -- to avoid partial match
    text = text.replace('---', '\u2014')  # em dash
    text = text.replace('--', '\u2013')   # en dash
    return text


def _convert_math(node: LatexMathNode, ctx: ConversionContext) -> str:
    """Convert math nodes. Preserve LaTeX content verbatim."""
    delimiters = node.delimiters
    inner = ''.join(get_node_text(n) for n in (node.nodelist or []))

    # Check for labels inside math
    label_match = re.search(r'\\label\{([^}]+)\}', inner)
    label_key = None
    if label_match:
        label_key = label_match.group(1)
        inner = inner.replace(label_match.group(0), '').strip()
        num = ctx.next_equation()
        kind = _detect_label_kind(label_key)
        ctx.register_label(label_key, kind, ctx.equation_counter)

    if delimiters[0] in ('$',):
        # Inline math
        return f'${inner}$'
    else:
        # Display math (\[...\] or $$...$$)
        parts = []
        if label_key:
            anchor = label_key.replace(':', '-')
            parts.append(f'<a id="{anchor}"></a>')
            parts.append('')
        parts.append('$$')
        parts.append(inner)
        parts.append('$$')
        return '\n' + '\n'.join(parts) + '\n'


def _convert_macro(node: LatexMacroNode, ctx: ConversionContext) -> str:
    """Convert a LaTeX macro to Markdown."""
    name = node.macroname

    # Section commands
    if name == 'chapter':
        title = get_macro_arg(node, _find_brace_arg_index(node))
        ctx.section_counter = 0
        ctx.subsection_counter = 0
        return f'\n# {title}\n\n'

    if name == 'section':
        title = get_macro_arg(node, _find_brace_arg_index(node))
        ctx.section_counter += 1
        ctx.subsection_counter = 0
        # Check for label in the source right after
        return f'\n## {title}\n\n'

    if name == 'subsection':
        title = get_macro_arg(node, _find_brace_arg_index(node))
        ctx.subsection_counter += 1
        return f'\n### {title}\n\n'

    if name == 'subsubsection':
        title = get_macro_arg(node, _find_brace_arg_index(node))
        return f'\n#### {title}\n\n'

    if name == 'paragraph':
        title = get_macro_arg(node, 0)
        return f'\n##### {title}\n\n'

    # Text formatting
    if name == 'textbf':
        inner = _convert_macro_arg_nodes(node, ctx, _find_brace_arg_index(node))
        return f'**{inner}**'

    if name in ('textit', 'emph'):
        inner = _convert_macro_arg_nodes(node, ctx, _find_brace_arg_index(node))
        return f'*{inner}*'

    if name == 'underline':
        inner = _convert_macro_arg_nodes(node, ctx, _find_brace_arg_index(node))
        return f'<u>{inner}</u>'

    if name == 'texttt':
        inner = get_macro_arg(node, _find_brace_arg_index(node))
        return f'`{inner}`'

    if name in ('textrm', 'textsf', 'textnormal'):
        return _convert_macro_arg_nodes(node, ctx, _find_brace_arg_index(node))

    if name == 'textcolor':
        # \textcolor{color}{text} → just the text
        return _convert_macro_arg_nodes(node, ctx, _find_brace_arg_index(node, start=1))

    if name == 'red':
        return _convert_macro_arg_nodes(node, ctx, 0)

    # Footnotes
    if name == 'footnote':
        fn_num = ctx.next_footnote()
        fn_text = _convert_macro_arg_nodes(node, ctx, _find_brace_arg_index(node))
        ctx.footnotes.append((fn_num, fn_text))
        return f'[^{fn_num}]'

    # Labels
    if name == 'label':
        key = get_macro_arg(node, 0)
        kind = _detect_label_kind(key)
        # Determine current counter for this kind
        local_num = _get_current_counter(kind, ctx)
        ctx.register_label(key, kind, local_num)
        anchor = key.replace(':', '-')
        return f'<a id="{anchor}"></a>'

    # References
    if name == 'ref':
        key = get_macro_arg(node, 0)
        return f'<<REF:{key}>>'

    if name == 'eqref':
        key = get_macro_arg(node, 0)
        return f'<<EQREF:{key}>>'

    # Citations (natbib + biblatex)
    if name in ('cite', 'citep', 'citet', 'autocite', 'parencite',
                'textcite', 'fullcite', 'footcite', 'nocite',
                'Cite', 'Citep', 'Citet', 'Autocite', 'Parencite', 'Textcite'):
        keys_str = get_macro_arg(node, _find_brace_arg_index(node))
        keys = [k.strip() for k in keys_str.split(',')]
        ctx.citation_keys.update(keys)
        placeholders = [f'<<CITE:{k}>>' for k in keys]
        return '; '.join(placeholders)

    # Figures (standalone \includegraphics outside figure env)
    if name == 'includegraphics':
        path = get_macro_arg(node, _find_brace_arg_index(node))
        path = _clean_image_path(path)
        ctx.figure_paths.add(path)
        is_pdf = path.lower().endswith('.pdf')
        if is_pdf:
            return f'[Figure](../figures/{path}) *(PDF)*'
        return f'![](../figures/{path})'

    # URL/links
    if name == 'url':
        url = get_macro_arg(node, 0)
        return f'<{url}>'

    if name == 'href':
        url = get_macro_arg(node, 0)
        text = _convert_macro_arg_nodes(node, ctx, 1)
        return f'[{text}]({url})'

    if name == 'nolinkurl':
        return f'`{get_macro_arg(node, 0)}`'

    # Caption (inside figure/table — handled by parent env)
    if name == 'caption':
        # If we reach here, it's a caption outside a known float
        return get_macro_arg(node, 0)

    if name == 'bicaption':
        # Bilingual caption: use both
        zh = get_macro_arg(node, 0)
        en = get_macro_arg(node, 1)
        if en:
            return f'{zh} / {en}'
        return zh

    # Spacing and layout commands (ignore)
    if name in ('centering', 'raggedright', 'raggedleft', 'noindent',
                'clearpage', 'newpage', 'pagebreak', 'linebreak',
                'smallskip', 'medskip', 'bigskip', 'vspace', 'hspace',
                'vfill', 'hfill', 'quad', 'qquad', 'enspace',
                'phantom', 'hphantom', 'vphantom',
                'maketitle', 'tableofcontents', 'listoffigures',
                'listoftables', 'listoffiguresandtables',
                'frontmatter', 'mainmatter', 'backmatter',
                'appendix', 'copyrightpage',
                'bibliographystyle', 'graphicspath',
                'makeatletter', 'makeatother',
                'protect', 'relax'):
        return ''

    # Special characters
    if name == 'LaTeX':
        return 'LaTeX'
    if name == 'TeX':
        return 'TeX'
    if name == 'ie':
        return 'i.e.'
    if name == 'eg':
        return 'e.g.'
    if name in ('ldots', 'dots', 'cdots'):
        return '...'
    if name == 'textbackslash':
        return '\\'
    if name == 'textasciitilde':
        return '~'
    if name == 'textasciicircum':
        return '^'
    if name in ('lbrace', 'textbraceleft'):
        return '{'
    if name in ('rbrace', 'textbraceright'):
        return '}'
    if name == 'textdegree':
        return '\u00b0'
    if name == 'copyright':
        return '\u00a9'
    if name == 'times':
        return '\u00d7'

    # Try custom macro expansion
    macro_def = ctx.macro_table.get(name)
    if macro_def:
        if macro_def.is_math:
            # Math-mode macro: preserve as LaTeX
            return get_node_text(node)
        else:
            # Text-mode macro: expand and convert
            args = []
            if node.nodeargd and node.nodeargd.argnlist:
                for arg in node.nodeargd.argnlist:
                    if arg is not None:
                        args.append(get_node_text(arg).strip('{}'))
            expanded = expand_macro(macro_def, args)
            # Simple text extraction from expanded result
            return _simple_latex_to_text(expanded)

    # Unknown macro: preserve verbatim for math-like commands, extract args otherwise
    if node.nodeargd and node.nodeargd.argnlist:
        # Has arguments: try to extract the last braced arg as content
        args = node.nodeargd.argnlist
        for arg in reversed(args):
            if arg and isinstance(arg, LatexGroupNode) and arg.nodelist:
                if arg.delimiters and arg.delimiters[0] == '{':
                    return convert_nodes(arg.nodelist, ctx)
        return ''

    # No arguments: might be a symbol/spacing command — skip
    logger.debug("Unknown macro \\%s with no args, skipping", name)
    return ''


def _convert_environment(node: LatexEnvironmentNode, ctx: ConversionContext) -> str:
    """Convert a LaTeX environment to Markdown."""
    env_name = node.environmentname

    # Display math environments
    if env_name in DISPLAY_MATH_ENVS:
        inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
        # Extract label
        label = _extract_label(inner)
        if label:
            num = ctx.next_equation()
            ctx.register_label(label, 'eq', ctx.equation_counter)
        return '\n' + convert_display_math(env_name, inner, label) + '\n'

    # Math sub-environments (shouldn't appear at top level, but handle gracefully)
    if env_name in ALL_MATH_ENVS:
        inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
        return f'\n$$\n\\begin{{{env_name}}}\n{inner}\n\\end{{{env_name}}}\n$$\n'

    # Figure environment
    if env_name in ('figure', 'figure*'):
        return '\n' + _convert_figure_env(node, ctx) + '\n'

    # Table environment
    if env_name in ('table', 'table*'):
        return '\n' + _convert_table_env(node, ctx) + '\n'

    # Tabular (standalone, not inside table float)
    if env_name in ('tabular', 'tabular*', 'longtable'):
        inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
        col_spec = ''
        if node.nodeargd and node.nodeargd.argnlist:
            for arg in node.nodeargd.argnlist:
                if arg:
                    col_spec = get_node_text(arg)
                    break
        return '\n' + convert_tabular(inner, col_spec) + '\n'

    # Theorem environments
    if env_name in THEOREM_DISPLAY_NAMES or env_name in ctx.theorem_names:
        return '\n' + _convert_theorem_env(node, ctx) + '\n'

    # Proof
    if env_name in PROOF_ENVS:
        body = convert_nodes(node.nodelist or [], ctx)
        opt = get_macro_opt_arg(node) if hasattr(node, 'nodeargd') else None
        # Try to get optional arg from environment args
        opt_title = None
        if node.nodeargd and node.nodeargd.argnlist:
            for arg in node.nodeargd.argnlist:
                if arg and isinstance(arg, LatexGroupNode):
                    if arg.delimiters and arg.delimiters[0] == '[':
                        opt_title = ''.join(get_node_text(n) for n in (arg.nodelist or []))
        return '\n' + convert_proof(body, opt_title) + '\n'

    # Algorithm
    if env_name in ('algorithm', 'algorithm2e'):
        inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
        caption = _extract_caption(inner)
        label = _extract_label(inner)
        if label:
            ctx.register_label(label, 'alg', 0)
        return '\n' + convert_algorithm(inner, caption, label) + '\n'

    # Lists
    if env_name in ('itemize', 'enumerate', 'description'):
        return '\n' + _convert_list_env(node, ctx, env_name) + '\n'

    # mdframed / framed: just convert contents
    if env_name in ('mdframed', 'framed'):
        body = convert_nodes(node.nodelist or [], ctx)
        lines = body.strip().split('\n')
        quoted = '\n'.join(f'> {line}' if line.strip() else '>' for line in lines)
        return '\n' + quoted + '\n'

    # Quoting environments
    if env_name in ('quote', 'quotation'):
        body = convert_nodes(node.nodelist or [], ctx)
        lines = body.strip().split('\n')
        quoted = '\n'.join(f'> {line}' if line.strip() else '>' for line in lines)
        return '\n' + quoted + '\n'

    # Center and alignment (just pass through content)
    if env_name in ('center', 'flushleft', 'flushright'):
        return convert_nodes(node.nodelist or [], ctx)

    # Minipage (pass through)
    if env_name in ('minipage',):
        return convert_nodes(node.nodelist or [], ctx)

    # Abstract
    if env_name in ('abstract', 'abstract*', 'enabstract'):
        body = convert_nodes(node.nodelist or [], ctx)
        return f'\n## Abstract\n\n{body}\n'

    # threeparttable: pass through (caption and tabular inside)
    if env_name == 'threeparttable':
        return convert_nodes(node.nodelist or [], ctx)

    if env_name == 'tablenotes':
        body = convert_nodes(node.nodelist or [], ctx)
        return f'\n*Notes:* {body}\n'

    # Code listing environments
    if env_name in ('minted', 'lstlisting', 'verbatim', 'Verbatim', 'listing'):
        inner = ''.join(get_node_text(n) for n in (node.nodelist or []))
        # Try to detect language from minted arg
        lang = ''
        if env_name == 'minted' and node.nodeargd and node.nodeargd.argnlist:
            for arg in node.nodeargd.argnlist:
                if arg and isinstance(arg, LatexGroupNode):
                    if not arg.delimiters or arg.delimiters[0] == '{':
                        lang = ''.join(get_node_text(n) for n in (arg.nodelist or []))
        return f'\n```{lang}\n{inner.strip()}\n```\n'

    # Beamer frame
    if env_name == 'frame':
        body = convert_nodes(node.nodelist or [], ctx)
        # Extract frame title if present
        inner_text = ''.join(get_node_text(n) for n in (node.nodelist or []))
        title_m = re.search(r'\\frametitle\{([^}]+)\}', inner_text)
        if title_m:
            return f'\n---\n\n### {title_m.group(1)}\n\n{body}\n'
        return f'\n---\n\n{body}\n'

    if env_name == 'block':
        title = ''
        if node.nodeargd and node.nodeargd.argnlist:
            for arg in node.nodeargd.argnlist:
                if arg and isinstance(arg, LatexGroupNode):
                    title = ''.join(get_node_text(n) for n in (arg.nodelist or []))
        body = convert_nodes(node.nodelist or [], ctx)
        if title:
            return f'\n**{title}**\n\n{body}\n'
        return body

    # Beamer columns: pass through
    if env_name in ('columns', 'column'):
        return convert_nodes(node.nodelist or [], ctx)

    # Unknown environment: convert contents with a note
    logger.debug("Unknown environment: %s, converting contents", env_name)
    body = convert_nodes(node.nodelist or [], ctx)
    return body


def _convert_figure_env(node: LatexEnvironmentNode, ctx: ConversionContext) -> str:
    """Convert a figure environment, extracting caption, label, and image path."""
    inner_nodes = node.nodelist or []

    # Extract from inner content
    inner_text = ''.join(get_node_text(n) for n in inner_nodes)
    caption = _extract_caption(inner_text)
    bicaption = _extract_bicaption(inner_text)
    if bicaption:
        caption = bicaption
    label = _extract_label(inner_text)
    image_path = _extract_includegraphics(inner_text)

    if label:
        num = ctx.next_figure()
        ctx.register_label(label, 'fig', ctx.figure_counter)

    if image_path:
        image_path = _clean_image_path(image_path)
        ctx.figure_paths.add(image_path)
        is_pdf = image_path.lower().endswith('.pdf')
        return convert_figure(image_path, caption, label, is_pdf)
    else:
        # Figure without includegraphics (might be tikz or other)
        parts = []
        if label:
            anchor = label.replace(':', '-')
            parts.append(f'<a id="{anchor}"></a>')
        if caption:
            parts.append(f'**Figure**: {caption}')
        body = convert_nodes(inner_nodes, ctx)
        parts.append(body)
        return '\n'.join(parts)


def _convert_table_env(node: LatexEnvironmentNode, ctx: ConversionContext) -> str:
    """Convert a table environment."""
    inner_text = ''.join(get_node_text(n) for n in (node.nodelist or []))
    caption = _extract_caption(inner_text)
    bicaption = _extract_bicaption(inner_text)
    if bicaption:
        caption = bicaption
    label = _extract_label(inner_text)

    if label:
        num = ctx.next_table()
        ctx.register_label(label, 'tab', ctx.table_counter)

    # Extract and convert the tabular content
    tabular_match = re.search(
        r'\\begin\{(tabular\*?|longtable)\}(\{[^}]*\})?(.*?)\\end\{\1\}',
        inner_text, re.DOTALL,
    )
    if tabular_match:
        col_spec = tabular_match.group(2) or ''
        tabular_body = tabular_match.group(3)
        table_md = convert_tabular(tabular_body, col_spec)
    else:
        table_md = convert_nodes(node.nodelist or [], ctx)

    return convert_table_float(table_md, caption, label)


def _convert_theorem_env(node: LatexEnvironmentNode, ctx: ConversionContext) -> str:
    """Convert a theorem-like environment."""
    env_name = node.environmentname

    # Get optional title
    opt_title = None
    if node.nodeargd and node.nodeargd.argnlist:
        for arg in node.nodeargd.argnlist:
            if arg and isinstance(arg, LatexGroupNode):
                if arg.delimiters and arg.delimiters[0] == '[':
                    opt_title = ''.join(get_node_text(n) for n in (arg.nodelist or []))

    # Get body content
    body = convert_nodes(node.nodelist or [], ctx)

    # Check for label in body
    inner_text = ''.join(get_node_text(n) for n in (node.nodelist or []))
    label = _extract_label(inner_text)

    num = ctx.next_theorem(env_name)
    if label:
        ctx.register_label(label, 'thm', ctx.theorem_counters.get('theorem', 0))

    return convert_theorem(
        env_name, body, opt_title, num, label,
        custom_names=ctx.theorem_names,
    )


def _convert_list_env(node: LatexEnvironmentNode, ctx: ConversionContext, list_type: str) -> str:
    """Convert itemize/enumerate to Markdown lists."""
    inner_nodes = node.nodelist or []
    inner_text = ''.join(get_node_text(n) for n in inner_nodes)

    # Split by \item, extracting each item's content
    # Use findall to get content after each \item
    item_contents = re.split(r'\\item\b\s*(?:\[[^\]]*\])?\s*', inner_text)

    result_lines = []
    item_num = 0

    # First element (before first \item) is usually whitespace — skip
    for item_text in item_contents[1:]:
        if item_text is None:
            continue
        item_text = item_text.strip()
        if not item_text:
            continue
        item_num += 1

        # Convert item text (basic LaTeX to markdown)
        item_md = _simple_latex_to_md(item_text)

        if list_type == 'enumerate':
            result_lines.append(f'{item_num}. {item_md}')
        else:
            result_lines.append(f'- {item_md}')

    return '\n'.join(result_lines)


# --- Extraction helpers ---

def _extract_label(latex: str) -> str | None:
    m = re.search(r'\\label\{([^}]+)\}', latex)
    return m.group(1) if m else None


def _extract_caption(latex: str) -> str | None:
    m = re.search(r'\\caption\{', latex)
    if not m:
        return None
    # Find matching brace
    from latex2kb.utils import find_matching_brace
    end = find_matching_brace(latex, m.end() - 1)
    if end == -1:
        return None
    return latex[m.end():end]


def _extract_bicaption(latex: str) -> str | None:
    m = re.search(r'\\bicaption\{', latex)
    if not m:
        return None
    from latex2kb.utils import find_matching_brace, extract_braced_arg
    zh, pos = extract_braced_arg(latex, m.end() - 1)
    en, _ = extract_braced_arg(latex, pos)
    if en:
        return f'{zh} / {en}'
    return zh


def _extract_includegraphics(latex: str) -> str | None:
    m = re.search(r'\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}', latex)
    return m.group(1).strip() if m else None


def _clean_image_path(path: str) -> str:
    """Clean up image path: remove 'figures/' prefix if present, normalize."""
    path = path.strip()
    # Remove leading figures/ since we'll add it back in output
    for prefix in ('figures/', 'figures\\', './figures/', './figures\\'):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    return path


def _detect_label_kind(key: str) -> str:
    """Detect label kind from its prefix."""
    prefixes = {
        'fig:': 'fig',
        'tab:': 'tab',
        'eq:': 'eq',
        'sec:': 'sec',
        'subsec:': 'subsec',
        'chap:': 'chap',
        'thm:': 'thm',
        'lem:': 'thm',
        'prop:': 'thm',
        'def:': 'thm',
        'cor:': 'thm',
        'alg:': 'alg',
    }
    for prefix, kind in prefixes.items():
        if key.startswith(prefix):
            return kind
    return 'sec'  # default


def _get_current_counter(kind: str, ctx: ConversionContext) -> int:
    """Get the current counter value for a label kind."""
    if kind == 'fig':
        return ctx.figure_counter
    if kind == 'tab':
        return ctx.table_counter
    if kind == 'eq':
        return ctx.equation_counter
    if kind == 'sec':
        return ctx.section_counter
    if kind == 'subsec':
        return ctx.subsection_counter
    if kind == 'thm':
        return ctx.theorem_counters.get('theorem', 0)
    if kind == 'chap':
        return ctx.chapter_num
    return 0


def _find_brace_arg_index(node: LatexMacroNode, start: int = 0) -> int:
    """Find the index of the first brace-delimited argument (skipping * and [] args)."""
    if not node.nodeargd or not node.nodeargd.argnlist:
        return 0
    for i, arg in enumerate(node.nodeargd.argnlist):
        if i < start:
            continue
        if arg is None:
            continue
        if isinstance(arg, LatexGroupNode):
            if not arg.delimiters or arg.delimiters[0] == '{':
                return i
    return start


def _convert_macro_arg_nodes(node: LatexMacroNode, ctx: ConversionContext, arg_index: int) -> str:
    """Convert the content of a macro argument at the given index."""
    if not node.nodeargd or not node.nodeargd.argnlist:
        return ''
    if arg_index >= len(node.nodeargd.argnlist):
        return ''
    arg = node.nodeargd.argnlist[arg_index]
    if arg is None:
        return ''
    if isinstance(arg, LatexGroupNode) and arg.nodelist:
        return convert_nodes(arg.nodelist, ctx)
    return get_node_text(arg)


def _simple_latex_to_text(latex: str) -> str:
    """Very basic LaTeX to text conversion for macro expansion results."""
    text = latex
    text = re.sub(r'\\textbf\{([^}]*)\}', r'**\1**', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'*\1*', text)
    text = re.sub(r'\\emph\{([^}]*)\}', r'*\1*', text)
    text = re.sub(r'\\texttt\{([^}]*)\}', r'`\1`', text)
    text = re.sub(r'\\textsf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textrm\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textcolor\{[^}]*\}\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\nolinkurl\{([^}]*)\}', r'`\1`', text)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)  # fallback: extract arg
    return text


def _simple_latex_to_md(latex: str) -> str:
    """Convert simple LaTeX in list items, etc. to Markdown."""
    text = latex
    # References FIRST (before formatting, to avoid corruption)
    text = re.sub(r'\\ref\{([^}]*)\}', r'<<REF:\1>>', text)
    text = re.sub(r'\\eqref\{([^}]*)\}', r'<<EQREF:\1>>', text)
    text = re.sub(r'\\cite[tp]?\{([^}]*)\}', lambda m: _cite_placeholder(m.group(1)), text)
    # Labels
    text = re.sub(r'\\label\{([^}]*)\}', '', text)
    # Section symbol
    text = re.sub(r'\\S\b', '\u00a7', text)
    # Formatting
    text = re.sub(r'\\textbf\{([^}]*)\}', r'**\1**', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'*\1*', text)
    text = re.sub(r'\\emph\{([^}]*)\}', r'*\1*', text)
    text = re.sub(r'\\texttt\{([^}]*)\}', r'`\1`', text)
    # Math: preserve
    # Tildes
    text = text.replace('~', ' ')
    # Cleanup
    text = re.sub(r'\\(?:centering|noindent|raggedright)\s*', '', text)
    return text.strip()


def _cite_placeholder(keys_str: str) -> str:
    keys = [k.strip() for k in keys_str.split(',')]
    return '; '.join(f'<<CITE:{k}>>' for k in keys)


def convert_chapter(
    source: str,
    ctx: ConversionContext,
    context_db,
) -> str:
    """Convert a complete chapter .tex file to Markdown.

    Returns the Markdown text with placeholder tokens for refs/cites.
    """
    from latex2kb.parser_core import parse_latex

    nodes = parse_latex(source, context_db)
    md = convert_nodes(nodes, ctx)

    # Append footnotes at the end
    if ctx.footnotes:
        md += '\n\n---\n\n'
        for num, text in ctx.footnotes:
            md += f'[^{num}]: {text}\n'

    # Clean up excessive blank lines
    md = re.sub(r'\n{4,}', '\n\n\n', md)

    return md
