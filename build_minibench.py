"""Assemble a 12-paper minibenchmark: the papers, the answers, and a judge.

Three papers at each of the four difficulty bands, each containing exactly one
error that a referee identified in a public report -- and only one, so a
candidate cannot be marked wrong for finding a different real problem.

The papers go out as one concatenated file with identifying material removed.
Full anonymisation of a physics paper is impossible: the content identifies it
to anyone who searches.  What this removes are the cheap handles -- titles,
authors, arXiv identifiers, acknowledgements, bibliography -- so that a model
reading the file cannot trivially fetch the next revision and read the answer.
A candidate with web access should be instructed not to search.

Examples
--------
python build_minibench.py --ids minibench/selection.txt --out-dir minibench
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import audit_latex_pairs as audit
from jsonl_io import read_jsonl, write_jsonl


ARXIV = re.compile(r"ar[XxΧ]iv[.:\s]*\d{4}\.\d{4,5}(v\d+)?|\barXiv\b|\d{4}\.\d{4,5}v\d+", re.I)
# Journal classes spell these a dozen ways: jheppub writes \emailAdd, Elsevier
# \ead, Springer \institute. A name missed here puts an author identity into
# the file the model is given.
STRIP_COMMANDS = (
    "title", "titlerunning", "author", "authorrunning", "date", "thanks",
    "affiliation", "altaffiliation", "affil", "institute", "institution",
    "emailAdd", "email", "ead", "address", "abstract", "keywords", "pacs",
)
ACK = re.compile(
    r"\\(?:section|subsection|paragraph|section\*|subsection\*)\s*\{[^}]*"
    r"(?:acknowledg|funding|competing interest)[^}]*\}.*?(?=\\(?:section|subsection|appendix|begin\{thebibliography\})|\Z)",
    re.I | re.S,
)
BIB = re.compile(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}|\\bibliography\{[^}]*\}", re.S)
# Front matter carries title, authors, affiliations and abstract. Templates
# typeset it a dozen different ways -- SciPost uses a bare centred \Large
# \textbf block, never \title{} -- so it is cut by position, not by command.
DOC_START = re.compile(r"\\begin\{document\}")
FIRST_SECTION = re.compile(r"\\(?:section|chapter|part)\b\*?\s*\{")
NUMBERED_MATH = re.compile(r"\\begin\{(?:equation|align|gather|multline|eqnarray)\}")
PDF_META = re.compile(r"pdf(?:title|author|subject|keywords)\s*=\s*\{[^{}]*\}", re.I)
EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
ABSTRACT_ENV = re.compile(r"\\begin\{abstract\}.*?\\end\{abstract\}", re.S)
# Some authors typeset the title block by hand instead of using \author, so
# there is no command to strip -- only a centred or flush-left box sitting
# ahead of the physics with names, affiliations and addresses in it.
TITLE_BLOCK_ENV = re.compile(r"\\begin\{(flushleft|flushright|center|titlepage)\}.*?\\end\{\1\}", re.S)
IDENTIFYING = re.compile(
    r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}|E-?mail|\$\^\{?\d"
    r"|Universit|Institut|Department|Laborator|Academy|College|School of",
    re.I,
)
CITE_KEY_ID = re.compile(r"(?<=[{,])\s*\d{4}\.\d{4,5}(v\d+)?\s*(?=[,}])")

HEADER = """\
You are reviewing {n} theoretical physics manuscripts, given below as LaTeX
source. Each was submitted to a journal and refereed.

Your task: find substantive errors in the physics or the mathematics. A
substantive error is a wrong equation, a wrong sign or factor, an invalid
step, a claim that contradicts another part of the same paper, or a
derivation that does not follow. Typography, grammar, notation preferences
and requests for more explanation are NOT errors.

For every error you find, report:

  - the paper number
  - the equation number as printed in that paper, or the nearest one
  - what is wrong, stated precisely
  - what it should be instead, if you can tell

Report only errors you can argue for. Do not search the web.
"""

SEPARATOR = "\n\n" + "=" * 78 + "\n=== PAPER {i} " + "=" * 60 + "\n" + "=" * 78 + "\n\n"


def cut_front_matter(text: str) -> str:
    """Drop everything between \\begin{document} and the first section.

    Refuses to cut when that region contains a numbered equation: removing
    physics to hide a title would be a worse trade than leaving the title.
    """
    start = DOC_START.search(text)
    if not start:
        return text
    section = FIRST_SECTION.search(text, start.end())
    if not section:
        return text
    front = text[start.end():section.start()]
    if NUMBERED_MATH.search(front):
        return text
    return text[:start.end()] + "\n\n" + text[section.start():]


def cut_title_blocks(text: str) -> str:
    """Drop a hand-typeset title block: a box of names and affiliations.

    Only boxes standing ahead of the first numbered equation are considered,
    and only those carrying an identifying mark -- an address, an e-mail, a
    superscript affiliation key. A box holding a numbered equation is physics
    and is kept whatever else it contains.
    """
    first_equation = NUMBERED_MATH.search(text)
    limit = first_equation.start() if first_equation else len(text)
    for block in reversed(list(TITLE_BLOCK_ENV.finditer(text))):
        if block.start() >= limit:
            continue
        body = block.group(0)
        if NUMBERED_MATH.search(body) or not IDENTIFYING.search(body):
            continue
        text = text[:block.start()] + text[block.end():]
    return text


def scrub_title(text: str, title: str) -> str:
    """Remove the title wherever it appears, tolerating LaTeX whitespace."""
    words = [re.escape(w) for w in title.split() if w]
    if not words:
        return text
    pattern = re.compile(r"\s*".join(words), re.I)
    return pattern.sub("", text)


def anonymise(source: str, title: str | None = None) -> str:
    """Remove the cheap handles that would let a reader look the paper up."""
    text = BIB.sub("", source)
    text = ACK.sub("", text)
    text = PDF_META.sub("", text)
    text = cut_front_matter(text)
    text = cut_title_blocks(text)
    text = ABSTRACT_ENV.sub("", text)
    text = CITE_KEY_ID.sub("REF", text)
    if title:
        text = scrub_title(text, title)
    for command in STRIP_COMMANDS:
        text = re.sub(r"\\" + command + r"\s*(\[[^\]]*\])?\s*\{", r"\\REMOVED" + "{", text)
        text = _drop_braced(text, r"\REMOVED{")
    text = ARXIV.sub("", text)
    text = EMAIL.sub("", text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def _drop_braced(text: str, marker: str) -> str:
    """Delete `marker{...}` including nested braces."""
    while (start := text.find(marker)) != -1:
        depth, i = 0, start + len(marker) - 1
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        text = text[:start] + text[i + 1:]
    return text


def assemble(papers: list[tuple[str, str]]) -> str:
    """One file: instructions, then each paper under an opaque number."""
    parts = [HEADER.format(n=len(papers))]
    for index, (_, body) in enumerate(papers, start=1):
        parts.append(SEPARATOR.format(i=index))
        parts.append(body)
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, default=Path("data/scipost_sources"))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    ids = args.ids.read_text().split()
    gold = {g["arxiv_id"]: g for g in read_jsonl(Path("data/error_cards_gold.jsonl"))}
    levels = {r["arxiv_id"]: r for r in read_jsonl(Path("data/paper_levels.jsonl"))}

    papers, answers = [], []
    for position, arxiv_id in enumerate(ids, start=1):
        card = gold[arxiv_id]
        folder = args.source_dir / arxiv_id
        name, before = audit.main_tex(audit.source_file(folder, card["v_before"]))
        papers.append((arxiv_id, anonymise("\n".join(before), title=card["title"])))
        answers.append({
            "paper_number": position,
            "arxiv_id": arxiv_id,
            "title": card["title"],
            "paper_level": levels[arxiv_id]["paper_level"],
            "paper_level_meaning": levels[arxiv_id]["paper_level_meaning"],
            "printed_equation": card["cited_location"]["number"],
            "referee_quote": card["referee_quote"],
            "report_url": card["report_url"],
            "report_doi": card["report_doi"],
            "version_reviewed": card["v_before"],
            "version_fixed": card["v_after"],
            "fix_before": (card["anchor_hunk"] or {}).get("before_text"),
            "fix_after": (card["anchor_hunk"] or {}).get("after_text"),
            "main_tex": name,
            "human_severity_label": "unreviewed",
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    document = assemble(papers)
    (args.out_dir / "papers.txt").write_text(document, encoding="utf-8")
    write_jsonl(args.out_dir / "answers.jsonl", answers, sort_keys=False)

    leaked = [a["arxiv_id"] for a in answers if a["arxiv_id"] in document]
    print(f"{len(papers)} papers -> {args.out_dir/'papers.txt'} "
          f"({len(document):,} chars, ~{len(document)//4000}k tokens)")
    print(f"answers -> {args.out_dir/'answers.jsonl'}")
    print(f"arXiv identifiers leaked into the paper file: {len(leaked)}")


if __name__ == "__main__":
    main()
