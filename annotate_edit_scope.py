"""Annotate each served card with the SCOPE OF THE EDIT the authors made.

This is deliberately not a severity label. Severity -- whether a flaw changes
the paper's conclusions -- cannot be read off a card: it needs the physics
re-derived, and the evidence here shows size is no proxy. Three of the
smallest edits in this corpus are a spurious factor removed, an inequality
turned into an equality, and m|phi|^2 corrected to m^2|phi|^2. Each is one or
two characters and none is a typo.

What CAN be read off a card is what the authors' confirmed edit touched:
prose, a bounded symbol, or a rewritten derivation. That is observable from
two fields anyone can re-read, so the label is checkable rather than trusted.

The result is advisory. It is written to its own file, it never enters the
model-facing cards, and it never fills human_severity_label -- that field
waits for a physicist.

    python annotate_edit_scope.py --gold data/precutoff/error_cards_gold.jsonl \
        --output data/precutoff/annotations_edit_scope.jsonl
"""
from __future__ import annotations

import argparse
import collections
import difflib
import re
from pathlib import Path

from jsonl_io import read_jsonl, write_jsonl

# Three attempts at this, each refuted by hand-auditing the output, and the
# failures were all the same mistake: diffing LaTeX character by character.
# difflib splits inside tokens, so \beta -> \gamma surfaces as 'bet' -> 'gamm',
# which any prose-word test reads as prose. A minus sign and a prime surface as
# punctuation, when a minus sign is the most consequential character in physics.
# So tokenise first, LaTeX-aware, and diff the token lists.
TOKEN = re.compile(r"\\[A-Za-z]+|\d+(?:\.\d+)?|[A-Za-z]+|\s+|.", re.S)

SIGN = frozenset("+-=<>") | {r"\pm", r"\mp", r"\neq", r"\leq", r"\geq"}
# Punctuation that carries no mathematics on its own. Note what is absent:
# - and = and ' are mathematics, never punctuation.
# Braces and parentheses group mathematics, and a missing one is a real error a
# referee reported here ("commutator brackets ... seems to be missing"), so they
# are symbolic. What is left is punctuation that never carries mathematics.
NEUTRAL_PUNCTUATION = frozenset(".,;:!?`\"~&%#")
PROSE_WORD = re.compile(r"^[A-Za-z]{3,}$")
# Typesetting commands carry no mathematical content. Spotted by a spot-check:
# "eqs (9,10) should have only one equation number", answered by adding
# \nonumber, was being counted as a symbolic correction.
FORMATTING = frozenset({
    "IDENTIFIERGROUP",
    r"\nonumber", r"\label", r"\ref", r"\eqref", r"\cite", r"\qquad", r"\quad",
    r"\hspace", r"\vspace", r"\text", r"\textrm", r"\mathrm", r"\rm", r"\it",
    r"\bf", r"\mbox", r"\left", r"\right", r"\big", r"\Big", r"\bigg", r"\Bigg",
    r"\displaystyle", r"\notag", r"\\", r"\noindent", r"\emph", r"\textbf",
})
GREEK = re.compile(
    r"^\\(?:alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|iota|kappa"
    r"|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|varphi|chi|psi|omega"
    r"|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega)$"
)
# A new or removed display environment means the argument itself was reworked.
DISPLAY_ENV = re.compile(r"\\(?:begin|end)\{(?:equation|align|gather|multline|eqnarray)")
SAYS_TYPOGRAPHICAL = re.compile(
    r"\b(?:typo|typographical|misprint|printing error|spelling|grammar|"
    r"capitali[sz]ation|a word is missing)\b", re.I,
)
SAYS_PRESENTATIONAL = re.compile(
    r"\b(?:should be defined|should be explained|should be spelled out|"
    r"should be recalled|should be improved|notation|I would add|please add|"
    r"would be (?:helpful|clearer)|for clarity|formatted)\b", re.I,
)

BOUNDED_TOKENS = 8       # a sign, factor, exponent, index, prime, coefficient
RESTRUCTURED_TOKENS = 60


# The argument of \label/\ref/\cite is an identifier, not mathematics. A
# spot-check caught "\label{eq:overlap}" scoring as a symbolic edit, because
# the fragment "eq" is short enough to look like a variable.
IDENTIFIER_GROUP = re.compile(r"\\(?:label|ref|eqref|cite|citep|onlinecite)\{[^{}]*\}")


def tokenise(text: str) -> list[str]:
    """LaTeX commands, numbers, words and single characters as units."""
    text = IDENTIFIER_GROUP.sub(" IDENTIFIERGROUP ", text)
    return [tok for tok in TOKEN.findall(text) if not tok.isspace()]


def token_is_symbolic(token: str) -> bool:
    """True when this token carries mathematical content.

    A single letter is a variable. A minus sign is a sign. A prime is a
    derivative or a relabelled quantity. A greek command is a symbol. Only
    structural punctuation and prose words are not mathematics.
    """
    if token in NEUTRAL_PUNCTUATION or token in FORMATTING:
        return False
    if PROSE_WORD.match(token) and token not in SIGN:
        return False
    return True


def changed_tokens(before: str, after: str) -> tuple[list[str], list[str]]:
    """(removed, added) tokens, so a diff never splits a LaTeX command."""
    old, new = tokenise(before), tokenise(after)
    matcher = difflib.SequenceMatcher(None, old, new)
    removed, added = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed.extend(old[i1:i2])
        added.extend(new[j1:j2])
    return removed, added


def complaint_kind(quote: str) -> str:
    """What the referee asked for, from their own words.

    Independent of what the authors then changed. Keeping the two apart is the
    point: a correction answered by a comma is a flag, and collapsing the axes
    hides it.
    """
    if SAYS_TYPOGRAPHICAL.search(quote):
        return "typographical"
    if SAYS_PRESENTATIONAL.search(quote):
        return "presentational"
    return "correction"


def edit_scope(card: dict) -> dict:
    hunk = card.get("anchor_hunk") or {}
    before, after = hunk.get("before_text") or "", hunk.get("after_text") or ""
    removed, added = changed_tokens(before, after)
    changed = removed + added
    quote = card.get("referee_quote", "")

    symbolic = [tok for tok in changed if token_is_symbolic(tok)]
    signs = [tok for tok in changed if tok in SIGN]
    greek = [tok for tok in changed if GREEK.match(tok)]
    asked = complaint_kind(quote)
    signals: list[str] = [f"referee asked for: {asked}"]

    if not changed:
        scope = "no_edit_recorded"
        signals.append("the hunk records no token change")
    elif not symbolic:
        formatting = [tok for tok in changed if tok in FORMATTING]
        scope = "typesetting_only" if formatting else "punctuation_only"
        signals.append("no changed token carries mathematical content")
        if formatting:
            signals.append(f"typesetting commands changed ({', '.join(sorted(set(formatting)))})")
    else:
        if signs:
            signals.append(f"a sign changed ({', '.join(sorted(set(signs)))})")
        if greek:
            signals.append(f"a symbol changed ({', '.join(sorted(set(greek)))})")
        signals.append(f"{len(symbolic)} of {len(changed)} changed tokens are symbolic")
        if len(changed) > RESTRUCTURED_TOKENS:
            scope = "derivation_restructured"
        elif len(changed) <= BOUNDED_TOKENS:
            scope = "bounded_symbolic"
        else:
            scope = "expression_rewritten"

    # Does the recorded edit answer the complaint? A referee asking for a
    # correction, answered by a comma or by nothing, means the anchor found a
    # real changed hunk at the right equation but not the authors' actual fix.
    agrees = not (asked == "correction"
                  and scope in ("punctuation_only", "typesetting_only", "no_edit_recorded"))
    if not agrees:
        signals.append("the recorded edit does not answer the complaint")

    return {
        "card_id": card["card_id"],
        "arxiv_id": card["arxiv_id"],
        "complaint_kind": asked,
        "edit_scope": scope,
        "anchor_answers_the_complaint": agrees,
        "signals": signals,
        "changed_tokens": len(changed),
        "symbolic_tokens": len(symbolic),
        "sign_changed": bool(signs),
        "edit_preview": (f"-{removed!r} +{added!r}" if changed else "")[:300],
        "annotated_by": "annotate_edit_scope.py (deterministic rules, no model)",
        "is_severity_judgement": False,
        "human_severity_label": card.get("human_severity_label", "unreviewed"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cards = list(read_jsonl(args.gold))
    rows = [edit_scope(c) for c in cards]
    write_jsonl(args.output, rows, sort_keys=False)

    scopes = collections.Counter(r["edit_scope"] for r in rows)
    kinds = collections.Counter(r["complaint_kind"] for r in rows)
    flagged = [r for r in rows if not r["anchor_answers_the_complaint"]]
    print(f"{len(rows)} cards -> {args.output}")
    print("\nwhat the referee asked for:")
    for kind, n in kinds.most_common():
        print(f"  {n:>4}  {kind}")
    print("\nwhat the authors' recorded edit touched:")
    for label, n in scopes.most_common():
        print(f"  {n:>4}  {label}")
    print(f"\n{len(flagged)} cards where the recorded edit does not answer the complaint")
    print("\nNeither axis is severity. A one-token edit can be a sign flip that")
    print("invalidates a result; a large edit can be cosmetic. Deciding that needs")
    print("the physics re-derived, so human_severity_label stays unreviewed.")


if __name__ == "__main__":
    main()
