"""Stage 1: Discover LaTeX project structure and resolve \\input/\\include chains."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from latex2kb.utils import read_tex_file, strip_tex_comments

logger = logging.getLogger(__name__)


class FileRole(Enum):
    PREAMBLE = "preamble"
    FRONTMATTER = "frontmatter"
    MAINMATTER = "mainmatter"
    BACKMATTER = "backmatter"
    BIBLIOGRAPHY = "bibliography"


class IncludeType(Enum):
    INPUT = "input"       # \input{} - inline expansion
    INCLUDE = "include"   # \include{} - chapter boundary with \clearpage


@dataclass
class TexFileEntry:
    path: Path
    role: FileRole
    include_type: IncludeType
    order: int = 0


@dataclass
class ProjectInfo:
    root_dir: Path
    main_tex: Path
    entries: list[TexFileEntry] = field(default_factory=list)
    graphics_paths: list[Path] = field(default_factory=list)
    bib_paths: list[Path] = field(default_factory=list)
    preamble_source: str = ""
    document_class: str = ""
    class_options: dict[str, str] = field(default_factory=dict)


def find_main_tex(project_dir: Path, override: str | None = None) -> Path:
    """Find the main .tex file containing \\documentclass."""
    if override:
        p = project_dir / override
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified main tex not found: {p}")

    candidates = []
    for tex_file in project_dir.rglob('*.tex'):
        # Skip files in common non-source directories
        rel = tex_file.relative_to(project_dir)
        parts = rel.parts
        if any(p.startswith('.') or p in ('build', 'out', 'dist', '__pycache__') for p in parts):
            continue
        try:
            content = read_tex_file(tex_file)
        except Exception:
            continue
        if re.search(r'\\documentclass', content):
            candidates.append(tex_file)

    if not candidates:
        raise FileNotFoundError(f"No .tex file with \\documentclass found in {project_dir}")

    # Prefer common names
    for name in ['main.tex', 'thesis.tex', 'paper.tex', 'document.tex']:
        for c in candidates:
            if c.name == name:
                return c

    # Prefer files with \begin{document}
    for c in candidates:
        content = read_tex_file(c)
        if r'\begin{document}' in content:
            return c

    return candidates[0]


def _resolve_tex_path(base_dir: Path, ref: str) -> Path | None:
    """Resolve a \\input/\\include reference to an actual file path."""
    ref = ref.strip()
    # Remove quotes if present
    ref = ref.strip('"').strip("'")

    candidate = base_dir / ref
    if candidate.exists() and candidate.is_file():
        return candidate

    # Try appending .tex
    if not ref.endswith('.tex'):
        candidate = base_dir / (ref + '.tex')
        if candidate.exists():
            return candidate

    return None


def scan_project(project_dir: Path, main_tex_override: str | None = None) -> ProjectInfo:
    """Scan a LaTeX project and return its structure."""
    project_dir = Path(project_dir).resolve()
    main_tex = find_main_tex(project_dir, main_tex_override)

    info = ProjectInfo(root_dir=project_dir, main_tex=main_tex)
    main_source = read_tex_file(main_tex)

    # Extract document class
    m = re.search(r'\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}', main_source)
    if m:
        info.document_class = m.group(2)
        if m.group(1):
            for opt in m.group(1).split(','):
                opt = opt.strip()
                if '=' in opt:
                    k, v = opt.split('=', 1)
                    info.class_options[k.strip()] = v.strip()
                else:
                    info.class_options[opt] = 'true'

    # Split into preamble and document body
    doc_begin = main_source.find(r'\begin{document}')
    if doc_begin == -1:
        logger.warning("No \\begin{document} found in %s", main_tex)
        info.preamble_source = main_source
        return info

    preamble = main_source[:doc_begin]
    body = main_source[doc_begin:]
    info.preamble_source = preamble

    # Extract bibliography paths from body
    for m in re.finditer(r'\\bibliography\s*\{([^}]+)\}', body):
        for bib_ref in m.group(1).split(','):
            bib_ref = bib_ref.strip()
            if not bib_ref.endswith('.bib'):
                bib_ref += '.bib'
            bib_path = project_dir / bib_ref
            if bib_path.exists():
                info.bib_paths.append(bib_path)

    # Also check for biblatex \addbibresource in preamble
    for m in re.finditer(r'\\addbibresource\s*\{([^}]+)\}', preamble):
        bib_path = project_dir / m.group(1)
        if bib_path.exists() and bib_path not in info.bib_paths:
            info.bib_paths.append(bib_path)

    # Resolve preamble \input files (for macro definitions)
    _resolve_preamble_inputs(info, preamble, main_tex.parent)

    # Extract graphicspath from full preamble (including \input'd files)
    # \graphicspath{{path1/}{path2/}} — nested braces, need special handling
    from latex2kb.utils import find_matching_brace
    for m in re.finditer(r'\\graphicspath\s*\{', info.preamble_source):
        outer_start = m.end() - 1
        outer_end = find_matching_brace(info.preamble_source, outer_start)
        if outer_end == -1:
            continue
        inner = info.preamble_source[outer_start + 1:outer_end]
        for pm in re.finditer(r'\{([^}]+)\}', inner):
            info.graphics_paths.append(project_dir / pm.group(1))

    # Parse document body for includes
    _parse_document_body(info, body, main_tex.parent)

    return info


def _resolve_preamble_inputs(info: ProjectInfo, preamble: str, base_dir: Path) -> None:
    r"""Find and record \input files in the preamble (for macro extraction)."""
    clean = strip_tex_comments(preamble)
    for m in re.finditer(r'\\input\s*\{([^}]+)\}', clean):
        ref = m.group(1)
        resolved = _resolve_tex_path(base_dir, ref)
        if resolved:
            info.entries.append(TexFileEntry(
                path=resolved,
                role=FileRole.PREAMBLE,
                include_type=IncludeType.INPUT,
                order=0,
            ))
            # Read preamble input and append to preamble_source
            try:
                info.preamble_source += '\n' + read_tex_file(resolved)
            except Exception as e:
                logger.warning("Failed to read preamble input %s: %s", resolved, e)


def _parse_document_body(info: ProjectInfo, body: str, base_dir: Path) -> None:
    """Parse the document body for \\include/\\input directives and structure boundaries."""
    clean = strip_tex_comments(body)

    # Track current document region
    current_role = FileRole.MAINMATTER  # default if no \frontmatter/\mainmatter markers

    order = 1
    for line in clean.split('\n'):
        line_stripped = line.strip()

        # Detect region boundaries
        if line_stripped == r'\frontmatter':
            current_role = FileRole.FRONTMATTER
            continue
        elif line_stripped == r'\mainmatter':
            current_role = FileRole.MAINMATTER
            continue
        elif line_stripped == r'\backmatter':
            current_role = FileRole.BACKMATTER
            continue
        elif line_stripped == r'\appendix':
            current_role = FileRole.BACKMATTER
            continue

        # Match \include{path} or \input{path}
        m = re.match(r'\\(include|input)\s*\{([^}]+)\}', line_stripped)
        if m:
            cmd = m.group(1)
            ref = m.group(2)
            include_type = IncludeType.INCLUDE if cmd == 'include' else IncludeType.INPUT
            resolved = _resolve_tex_path(base_dir, ref)
            if resolved:
                info.entries.append(TexFileEntry(
                    path=resolved,
                    role=current_role,
                    include_type=include_type,
                    order=order,
                ))
                order += 1
            else:
                logger.warning("Could not resolve \\%s{%s} from %s", cmd, ref, base_dir)


def get_chapter_entries(info: ProjectInfo) -> list[TexFileEntry]:
    """Return only the mainmatter chapter entries, in order."""
    return sorted(
        [e for e in info.entries if e.role == FileRole.MAINMATTER],
        key=lambda e: e.order,
    )


def get_backmatter_entries(info: ProjectInfo) -> list[TexFileEntry]:
    """Return backmatter entries (acknowledgements, achievements, etc.)."""
    return sorted(
        [e for e in info.entries if e.role == FileRole.BACKMATTER],
        key=lambda e: e.order,
    )
