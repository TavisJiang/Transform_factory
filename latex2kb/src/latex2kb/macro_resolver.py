"""Stage 2: Discover and resolve custom LaTeX macro definitions."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from latex2kb.utils import find_matching_brace, read_tex_file, strip_tex_comments

logger = logging.getLogger(__name__)


@dataclass
class MacroDef:
    name: str           # e.g., "red"
    num_args: int       # number of arguments
    default_opt: str | None  # default for optional first arg
    body: str           # expansion template with #1, #2, etc.
    is_math: bool       # whether this macro is math-mode only
    source: str = ""    # where it was defined


@dataclass
class MacroTable:
    macros: dict[str, MacroDef] = field(default_factory=dict)

    def add(self, macro: MacroDef) -> None:
        self.macros[macro.name] = macro

    def get(self, name: str) -> MacroDef | None:
        return self.macros.get(name)

    def has(self, name: str) -> bool:
        return name in self.macros


# Patterns for \newcommand, \renewcommand, \providecommand, \DeclareRobustCommand
_CMD_DEF_RE = re.compile(
    r'\\(?:new|renew|provide)command\*?\s*'
    r'\{?(\\[a-zA-Z@]+)\}?'
    r'|'
    r'\\DeclareRobustCommand\*?\s*'
    r'\{?(\\[a-zA-Z@]+)\}?'
    r'|'
    r'\\DeclareMathOperator\*?\s*'
    r'\{(\\[a-zA-Z@]+)\}'
)

# Math-mode indicators in macro body
_MATH_INDICATORS = re.compile(
    r'\\math|\\symup|\\mathrm|\\mathop|\\mathbb|\\mathcal|\\mathfrak|\\boldsymbol'
    r'|\\frac|\\sqrt|\\sum|\\prod|\\int|\\lim'
    r'|\\left|\\right|\\big|\\Big'
    r'|\\ket|\\bra|\\braket|\\ketbra'
)


def _extract_command_def(source: str, match_start: int, cmd_name: str) -> MacroDef | None:
    """Extract a full command definition starting after the command name."""
    pos = match_start

    # Skip to after the command name in the source
    # Find where the command name ends
    name_pos = source.find(cmd_name, pos)
    if name_pos == -1:
        return None
    pos = name_pos + len(cmd_name)

    # Skip closing brace if the name was in braces
    while pos < len(source) and source[pos] in ' \t\n\r':
        pos += 1
    if pos < len(source) and source[pos] == '}':
        pos += 1

    # Check for [num_args]
    num_args = 0
    while pos < len(source) and source[pos] in ' \t\n\r':
        pos += 1
    if pos < len(source) and source[pos] == '[':
        end_bracket = source.find(']', pos)
        if end_bracket != -1:
            try:
                num_args = int(source[pos + 1:end_bracket].strip())
            except ValueError:
                pass
            pos = end_bracket + 1

    # Check for [default] for optional first arg
    default_opt = None
    while pos < len(source) and source[pos] in ' \t\n\r':
        pos += 1
    if pos < len(source) and source[pos] == '[':
        end_bracket = source.find(']', pos)
        if end_bracket != -1:
            default_opt = source[pos + 1:end_bracket]
            pos = end_bracket + 1

    # Extract body {....}
    while pos < len(source) and source[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(source) or source[pos] != '{':
        return None
    end_brace = find_matching_brace(source, pos)
    if end_brace == -1:
        return None
    body = source[pos + 1:end_brace]

    # Determine if math-mode
    clean_name = cmd_name.lstrip('\\')
    is_math = bool(_MATH_INDICATORS.search(body))

    return MacroDef(
        name=clean_name,
        num_args=num_args,
        default_opt=default_opt,
        body=body,
        is_math=is_math,
    )


def extract_newcommands(source: str, source_name: str = "") -> list[MacroDef]:
    """Extract all \\newcommand-style definitions from LaTeX source."""
    results = []
    # Work on comment-stripped source to avoid picking up commented definitions
    clean = strip_tex_comments(source)

    for m in _CMD_DEF_RE.finditer(clean):
        # Get the command name from whichever group matched
        cmd_name = m.group(1) or m.group(2) or m.group(3)
        if not cmd_name:
            continue

        macro = _extract_command_def(clean, m.start(), cmd_name)
        if macro:
            macro.source = source_name
            results.append(macro)
            logger.debug("Found macro: \\%s[%d] from %s", macro.name, macro.num_args, source_name)

    return results


def extract_newtheorems(source: str) -> dict[str, str]:
    """Extract \\newtheorem definitions. Returns {env_name: display_name}."""
    results = {}
    clean = strip_tex_comments(source)
    # \newtheorem{env_name}{Display Name}
    for m in re.finditer(r'\\newtheorem\*?\s*\{([^}]+)\}\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}', clean):
        env_name = m.group(1)
        display_name = m.group(3)
        results[env_name] = display_name
    return results


def build_macro_table(
    preamble_source: str,
    project_dir: Path,
    builtin_macros: dict[str, MacroDef] | None = None,
) -> MacroTable:
    """Build a complete macro table from project sources and builtins."""
    table = MacroTable()

    # Add builtins first (can be overridden by project macros)
    if builtin_macros:
        for macro in builtin_macros.values():
            table.add(macro)

    # Extract from preamble (includes \input'd setup files)
    for macro in extract_newcommands(preamble_source, "preamble"):
        table.add(macro)

    # Scan .cls and .sty files in the project for additional macros
    for pattern in ['*.cls', '*.sty']:
        for f in project_dir.glob(pattern):
            try:
                source = read_tex_file(f)
                for macro in extract_newcommands(source, f.name):
                    # Only add if not already defined by the user
                    if not table.has(macro.name):
                        table.add(macro)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", f, e)

    logger.info("Macro table: %d macros resolved", len(table.macros))
    return table


def expand_macro(macro: MacroDef, args: list[str]) -> str:
    """Expand a macro with the given arguments."""
    body = macro.body
    for i, arg in enumerate(args, 1):
        body = body.replace(f'#{i}', arg)
    return body
