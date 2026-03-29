"""Theorem-like environment converter: theorem, lemma, fact, proof, etc."""

from __future__ import annotations

# Default display names for theorem environments
THEOREM_DISPLAY_NAMES = {
    'theorem': 'Theorem',
    'lemma': 'Lemma',
    'proposition': 'Proposition',
    'corollary': 'Corollary',
    'definition': 'Definition',
    'example': 'Example',
    'remark': 'Remark',
    'fact': 'Fact',
    'assertion': 'Assertion',
    'axiom': 'Axiom',
    'assumption': 'Assumption',
    'conjecture': 'Conjecture',
    'property': 'Property',
    'observation': 'Observation',
    'claim': 'Claim',
    'notation': 'Notation',
    'problem': 'Problem',
    'exercise': 'Exercise',
    'solution': 'Solution',
}

PROOF_ENVS = {'proof'}


def convert_theorem(
    env_name: str,
    body_md: str,
    opt_title: str | None = None,
    number: str | None = None,
    label: str | None = None,
    custom_names: dict[str, str] | None = None,
) -> str:
    """Convert a theorem-like environment to a Markdown blockquote.

    Example output:
        > **Theorem 3.1** (LC equivalence graph criterion)
        >
        > Two graph states $|G\\rangle$ and $|G'\\rangle$ ...
    """
    names = {**THEOREM_DISPLAY_NAMES, **(custom_names or {})}
    display = names.get(env_name, env_name.capitalize())

    parts = []

    # Anchor for cross-references
    if label:
        anchor = label.replace(':', '-')
        parts.append(f'<a id="{anchor}"></a>')
        parts.append('')

    # Header line
    header = f'**{display}'
    if number:
        header += f' {number}'
    header += '**'
    if opt_title:
        header += f' ({opt_title})'

    # Format body as blockquote
    body_lines = body_md.strip().split('\n')
    quote_lines = [f'> {header}']
    quote_lines.append('>')
    for line in body_lines:
        if line.strip():
            quote_lines.append(f'> {line}')
        else:
            quote_lines.append('>')

    parts.extend(quote_lines)
    return '\n'.join(parts)


def convert_proof(body_md: str, opt_title: str | None = None) -> str:
    """Convert a proof environment to Markdown."""
    title = opt_title or 'Proof'
    lines = body_md.strip().split('\n')

    parts = [f'*{title}.*']
    parts.extend(lines)
    parts.append('$\\square$')  # QED marker
    parts.append('')
    return '\n'.join(parts)
