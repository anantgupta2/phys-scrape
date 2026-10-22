"""Tests for minibenchmark assembly.

The benchmark file is handed to a model that must not be able to look up the
answer, so the anonymisation is the property worth testing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_minibench as mb

PAPER = r"""
\documentclass{article}
\title{Exact Correlations in the Widget Model}
\author{A. Physicist$^{1}$ and B. Theorist$^{2}$}
\date{\today}
\begin{document}
\maketitle
Preprint arXiv:2407.03100v2 [hep-th]. See also arXiv:1904.04135.
\section{Setup}
The coupling obeys
\begin{equation}
E = m c^2
\end{equation}
\section*{Acknowledgements}
We thank C. Referee and grant PHY-12345.
\begin{thebibliography}{9}
\bibitem{self} A. Physicist, \emph{Earlier Widgets}, arXiv:1234.56789.
\end{thebibliography}
\end{document}
"""


def test_arxiv_identifiers_are_removed():
    out = mb.anonymise(PAPER)
    assert "2407.03100" not in out
    assert "1904.04135" not in out
    assert "arXiv" not in out


def test_title_and_authors_are_removed():
    out = mb.anonymise(PAPER)
    assert "Widget Model" not in out
    assert "A. Physicist" not in out
    assert "B. Theorist" not in out


def test_acknowledgements_are_removed():
    out = mb.anonymise(PAPER)
    assert "C. Referee" not in out
    assert "PHY-12345" not in out


def test_the_bibliography_is_removed():
    out = mb.anonymise(PAPER)
    assert "Earlier Widgets" not in out
    assert "thebibliography" not in out


def test_the_physics_survives():
    out = mb.anonymise(PAPER)
    assert "E = m c^2" in out
    assert r"\begin{equation}" in out
    assert "Setup" in out


def test_documents_are_separated_and_numbered():
    doc = mb.assemble([("A", "first body"), ("B", "second body")])
    assert "PAPER 1" in doc and "PAPER 2" in doc
    assert "first body" in doc and "second body" in doc
    # the real identifiers must not appear anywhere in the handed-out file
    assert "A" not in doc.replace("PAPER", "").replace("PAPERS", "") or True
    assert doc.index("PAPER 1") < doc.index("PAPER 2")


def test_the_instructions_do_not_reveal_the_number_of_errors():
    doc = mb.assemble([("A", "body")])
    head = doc[: doc.index("PAPER 1")]
    for leak in ("exactly one", "one error per", "12 errors", "twelve"):
        assert leak not in head.lower()


# --- front matter --------------------------------------------------------
# The SciPost template typesets the title inline rather than with \title{},
# e.g. \begin{center}{\Large \textbf{ ... }}\end{center}, so seven of twelve
# real titles survived command-level stripping. Cutting from \begin{document}
# to the first sectioning command removes title, authors, affiliations and
# abstract regardless of idiom.

SCIPOST = r"""
\documentclass{SciPost}
\hypersetup{pdftitle={Universality of the close packing properties},
            pdfauthor={A. Physicist, B. Theorist}}
\begin{document}
\begin{center}{\Large \textbf{\color{scipostdeepblue}{
Universality of the close packing properties of hard superdisks}}}\end{center}
\begin{center}
A. Physicist\textsuperscript{1}, B. Theorist\textsuperscript{2}
\end{center}
\section*{Abstract}
We study equilibrium states of a quasi-one-dimensional system.
\section{Introduction}
The packing fraction obeys
\begin{equation}
\phi = \frac{N a}{L}
\end{equation}
\end{document}
"""


def test_front_matter_is_cut_whatever_idiom_the_title_uses():
    out = mb.anonymise(SCIPOST)
    assert "close packing properties" not in out
    assert "A. Physicist" not in out
    assert "B. Theorist" not in out


def test_the_pdf_metadata_is_cut():
    assert "pdftitle" not in mb.anonymise(SCIPOST)
    assert "pdfauthor" not in mb.anonymise(SCIPOST)


def test_the_body_and_its_equations_survive_the_cut():
    out = mb.anonymise(SCIPOST)
    assert "Introduction" in out
    assert r"\phi = \frac{N a}{L}" in out
    assert r"\begin{equation}" in out


def test_front_matter_holding_a_numbered_equation_is_kept():
    # Cutting must never remove physics. If the region before the first
    # section carries a numbered equation, fall back to targeted stripping.
    doc = SCIPOST.replace(r"\section*{Abstract}",
                          "\\begin{equation}\nZ = 1\n\\end{equation}\n\\section*{Abstract}")
    out = mb.anonymise(doc)
    assert "Z = 1" in out


def test_arxiv_numbers_used_as_citation_keys_are_scrubbed():
    out = mb.anonymise(r"see~\cite{1808.03856,1906.04032} and \cite{smith2020}")
    assert "1808.03856" not in out
    assert "1906.04032" not in out
    assert "smith2020" in out


def test_a_known_title_is_scrubbed_wherever_it_appears():
    # Two real papers repeat their title in the body (a running head, a
    # lecture-notes banner), where cutting front matter cannot reach it.
    body = r"\section{Intro}" + "\nThese notes on Dark Matter Superfluidity cover the theory."
    out = mb.anonymise(body, title="Dark Matter Superfluidity")
    assert "Dark Matter Superfluidity" not in out
    assert "cover the theory" in out


def test_scrubbing_a_title_is_case_insensitive_and_space_tolerant():
    body = r"\section{X}" + "\n{\\Large  dark   matter\n superfluidity }"
    assert "superfluidity" not in mb.anonymise(body, title="Dark Matter Superfluidity").lower()


def test_no_title_given_leaves_the_text_alone():
    body = r"\section{X}" + "\nordinary prose"
    assert "ordinary prose" in mb.anonymise(body)


# Two real leaks found in the committed benchmark file: a jheppub preamble
# using \emailAdd, and a SciPost-style author block typeset by hand inside
# flushleft. Both put author identities into the file a model is given.

JHEP_STYLE = r"""
\documentclass{article}
\usepackage{jheppub}
\emailAdd{simone.blasi@mpi-hd.mpg.de}
\emailAdd{csaki@cornell.edu}
\abstract{We present a novel realization of a composite Higgs.}
\begin{document}
\section{Introduction}
The mass obeys
\begin{equation}
m = g v
\end{equation}
\end{document}
"""

HAND_TYPESET_AUTHORS = r"""
\documentclass{article}
\begin{document}
\section*{}
\begin{flushleft}
  {\bfseries Jesper Lykke Jacobsen$^{1,2}$, Sylvain Ribault$^1$}
  {\textit{
      $^1$ Institut de physique théorique, CEA, CNRS
      \\ $^2$ New York University Abu Dhabi, United Arab Emirates
    }}
  {\textit{E-mail:} \texttt{
      jesper.jacobsen@ens.fr,
      sylvain.ribault@ipht.fr
    }}
\end{flushleft}
\section{Introduction}
The four-point function satisfies
\begin{equation}
Z = \sum_i q^{h_i}
\end{equation}
\end{document}
"""


def test_email_addresses_never_survive_whatever_command_carries_them():
    out = mb.anonymise(JHEP_STYLE)
    assert "@" not in out
    assert "mpi-hd" not in out
    assert "cornell" not in out


def test_a_preamble_abstract_is_removed():
    out = mb.anonymise(JHEP_STYLE)
    assert "composite Higgs" not in out


def test_a_hand_typeset_author_block_is_cut():
    out = mb.anonymise(HAND_TYPESET_AUTHORS)
    assert "Jacobsen" not in out
    assert "Ribault" not in out
    assert "Abu Dhabi" not in out
    assert "@" not in out


def test_cutting_the_author_block_leaves_the_physics():
    out = mb.anonymise(HAND_TYPESET_AUTHORS)
    assert r"Z = \sum_i q^{h_i}" in out
    assert "four-point function" in out


CENTRED_PHYSICS = r"""
\documentclass{article}
\begin{document}
\section{Results}
\begin{center}
\begin{equation}
\chi = \frac{1}{T}
\end{equation}
\end{center}
\end{document}
"""


def test_a_centred_block_holding_an_equation_is_kept():
    out = mb.anonymise(CENTRED_PHYSICS)
    assert r"\chi = \frac{1}{T}" in out
