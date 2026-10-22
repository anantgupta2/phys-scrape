# Five candidate errors in theoretical physics papers

Five sample cards from a dataset of 1,119 candidate errors mined from SciPost's
open peer review. Each one pairs a **named referee's published objection** with
**a change the authors made in the next arXiv revision**.

Every claim below is **a claim to be tested, not an established fact.** Nobody
qualified has verified the physics. What has been verified mechanically is only
this: the referee wrote these words in a public report, and the authors changed
that specific equation in the next revision. That is evidence, not proof — a
referee can be wrong, and in at least one case here the correction was itself
disputed by the next round of review.

- **Ground truth source:** SciPost referee reports, CC-BY 4.0, cited by DOI.
- **Nothing here was found by a language model.** Selection was rule-based.
- **Contents:** 5 of 236 anchored cards, from 1,119 total candidates.

---

## How to verify one of these

**For a person:** open both arXiv versions, find the numbered equation in the
"before" version, read the referee's objection, and decide whether the objection
is correct. Then look at what the authors did in the "after" version.

**For an LLM with internet access:** for each error below,

1. Fetch the **before** arXiv abstract page and the paper itself. The equation
   numbers given are the numbers **as printed in that specific version** — they
   often differ between versions, so use the version named.
2. Locate the cited equation. Confirm it matches the LaTeX quoted here.
3. Evaluate the referee's specific objection on its own merits. Do the
   calculation where one is called for; do not defer to the referee.
4. Fetch the **after** version and confirm what changed.
5. Answer the **verification question**, and report one of:
   - `CONFIRMED` — the referee is right; the "before" equation is wrong.
   - `REFUTED` — the referee is mistaken; the "before" equation was fine.
   - `UNRESOLVED` — cannot determine without information not in the papers.
   - `STILL-WRONG` — the referee was right and the correction does not fix it.

State your reasoning and quote the equation you evaluated. Do not treat the
authors' having changed something as proof the original was wrong: authors
sometimes concede points to get published.

---

## 1. Main result contradicts the standard Weinberg soft factor

|  |  |
| --- | --- |
| **Paper** | *Helicity Constraints To Soft Factor Of All Spin* — Andriniaina Narindra Rasoanaivo |
| **Before** | https://arxiv.org/abs/2002.02120v2 |
| **After** | https://arxiv.org/abs/2002.02120v3 |
| **Referee report** | https://scipost.org/submissions/2002.02120v2/#report_1 (report 1, vetted; no DOI issued) |
| **Equation** | (21) in v2 |
| **Referee's validity rating** | good |
| **Status** | Never accepted. v2 → v3 → v4, two "ask for major revision" recommendations. |

**Referee wrote:**

> While the motivation is interesting, the paper contains a critical error:
> eq. (21), presented as the main result, does not agree with the standard
> Weinberg soft factor.

> The standard expression is a single sum over hard particles, whereas eq. (21)
> has a double sum over pairs $(i,j)$ — it indicates that eq. (21) is incorrect,
> and the derivation leading to it must contain an error.

> The central formula eq. (21) is incorrect and must be corrected before the
> paper can be reconsidered.

**v2 source** (`elsarticle-template_proofread.tex`, around line 251):

```latex
S^{(0)}_\text{general} = \left[\sum_{\alpha\in\mathbb{Z}} g_{\alpha+1}
    \Big(\braket{ir}[ir]\Big)^\alpha\right] \times S^{(0)}_{\ldots}
```

**v3 replaces it with:**

```latex
S^{(0)}_{s,h_r} = \sum_{i} \frac{g_s\, t^r_{i}}{\left(\braket{ir}[ir]\right)^{1-s}}
    \left(\frac{\braket{ij}}{\braket{ir}\braket{jr}}\right)^{\frac{s+h_r}{2}}
    \left(\frac{[ij]}{[ir][jr]}\right)^{\frac{s-h_r}{2}}
```

with new prose: *"The sum over $i$ is due to the fact that physical solution is
described by superposition of all possible ways to attach the soft particle."*

**Verification question.** Does Weinberg's leading soft factor for a spin-$s$
soft emission sum over single hard legs, or over pairs? Is v2's eq. (21)
inconsistent with it?

**Then check the fix.** v3's formula sums over $i$ alone, but a free index $j$
still appears inside the summand. Is $j$ a fixed reference leg, or is the
expression still ill-defined? A referee on the **next** round wrote *"the sum
over legs in (21) does not follow from Eqs."* — so `STILL-WRONG` is a live
possibility here, and is the most interesting outcome to test.

---

## 2. Partition-function exponents contradict the paper's own matrix dimension

|  |  |
| --- | --- |
| **Paper** | *The boundary disorder correlation for the Ising model on a cylinder* |
| **Before** | https://arxiv.org/abs/2407.03100v2 |
| **After** | https://arxiv.org/abs/2407.03100v3 |
| **Referee report** | https://scipost.org/submissions/2407.03100v2/#report_2 · DOI [10.21468/SciPost.Report.10159](https://doi.org/10.21468/SciPost.Report.10159) |
| **Equation** | (10) in v2, referred to (2) in v2 |
| **Referee's validity rating** | ok |

**Referee wrote:**

> I think formula (10) is wrong if the partition function is as in (2): I expect
> a 4MN in the exponent instead of MN and 2N(M − 1) instead of N(M − 1).

**v2 source** (`Ising_cylinder.tex`):

```latex
Z_\pm = \frac12 \left(2 \cosh \beta J\right)^{MN}
        \left( \cosh \beta J \right)^{N(M-1)} \sqrt{|A_\pm|}
```

immediately followed in the same paragraph by:

> where $A$ is an antisymmetric $4MN \times 4MN$ matrix made up of $4\times4$ blocks

**v3** deletes this derivation and rebuilds it from McCoy & Wu, now summing over
$\{-1,+1\}^{4\mathcal{M}\mathcal{N}}$ on a $2\mathcal{M}\times 2\mathcal{N}$
cylinder.

**Verification question.** For the lattice defined in eq. (2) of v2, count the
sites and the horizontal and vertical bonds. Should the high-temperature
prefactor exponents be $MN$ and $N(M-1)$, or $4MN$ and $2N(M-1)$?

**Why this one is a good first test.** It needs no field theory — only counting
— and the inconsistency is visible on a single page: an $MN$ exponent sitting
beside a $4MN \times 4MN$ matrix built from the same lattice.

---

## 3. A consistency check the referee actually ran and failed

|  |  |
| --- | --- |
| **Paper** | *Low-energy effective description of dark $Sp(4)$ theories* |
| **Before** | https://arxiv.org/abs/2202.05191v1 |
| **After** | https://arxiv.org/abs/2202.05191v2 |
| **Referee report** | https://scipost.org/submissions/2202.05191v1/#report_2 · DOI [10.21468/SciPost.Report.5151](https://doi.org/10.21468/SciPost.Report.5151) |
| **Equation** | (3.23) in v1 |
| **Referee's validity rating** | not given |

**Referee wrote:**

> I noticed this because plugging the KSRF relation into Eq. (3.23) does not
> seem to give $Z^2 = 1/2$ as it should.

**v1 source** (`main.tex`):

```latex
a_{\mu} \rightarrow \tilde{a}_{\mu} + \frac{g_{\rho\pi\pi}}{2 m_{\rho}^{2}} \tilde{f}_{\pi} \ldots
Z^{2} = \left(1 - g_{\rho\pi\pi}^{2}\tilde{f}_{\pi}^{2} / 4 m_{\rho}^{2}\right)
```

**v2 source:**

```latex
a_{\mu} \rightarrow \tilde{a}_{\mu} + \frac{g_{\rho}}{\sqrt{2} m_{\rho}^{2}} \tilde{f}_{\pi} \ldots
Z^{2} = \left(1 - g_{\rho}^{2}\tilde{f}_{\pi}^{2} / 2 m_{\rho}^{2}\right)
```

Both the coupling ($g_{\rho\pi\pi} \to g_{\rho}$) and the denominators
($2m_\rho^2 \to \sqrt2 m_\rho^2$, $4m_\rho^2 \to 2m_\rho^2$) changed.

**Verification question.** Apply the KSRF relation to v1's eq. (3.23). Does
$Z^2 = 1/2$ follow? Repeat for v2's version. Which coupling convention is
consistent with KSRF?

**Note.** This is a coupling-convention error propagating into the field-strength
renormalization — the kind of mistake that is invisible unless you run exactly
the check this referee ran.

---

## 4. One spurious factor in a definition

|  |  |
| --- | --- |
| **Paper** | *A modular implementation of an effective interaction approach for harmonically trapped fermions in 1D* |
| **Before** | https://arxiv.org/abs/2202.04603v1 |
| **After** | https://arxiv.org/abs/2202.04603v2 |
| **Referee report** | https://scipost.org/submissions/2202.04603v1/#report_1 · DOI [10.21468/SciPost.Report.4884](https://doi.org/10.21468/SciPost.Report.4884) |
| **Equation** | (11) in v1 |
| **Referee's validity rating** | high |

**Referee wrote:**

> 5 - Please remove the erroneous factor $g$ in Eq. (11) with the general
> two-body potential.

**v1 source** (`method_paper.tex`):

```latex
V_{ijkl} = g\int\!\d x_1 \d x_2\; \phi_{i}(x_1)\,\phi_{j}(x_2)\,V(x_1-x_2)\,\phi_{l}(x_1)\,\phi_{k}(x_2)
```

**v2 source** — identical but for the removal of `g`:

```latex
V_{ijkl} = \int\!\d x_1 \d x_2\; \phi_{i}(x_1)\,\phi_{j}(x_2)\,V(x_1-x_2)\,\phi_{l}(x_1)\,\phi_{k}(x_2)
```

**Verification question.** In this paper, $g$ is the contact-interaction coupling
strength. Does carrying it as a prefactor on a matrix element of the *general*
two-body potential $V(x_1-x_2)$ double-count the coupling? Check the dimensions,
and check where $g$ appears in the surrounding definitions.

**Why this one matters.** It is a single character, and the referee who found it
rated the paper's overall validity **high**. Use it to calibrate: a checker that
cannot find this will not find anything subtler.

---

## 5. An identity that was deleted rather than corrected

|  |  |
| --- | --- |
| **Paper** | *Universality class of the mode-locked glassy random laser* |
| **Before** | https://arxiv.org/abs/2210.04362v1 |
| **After** | https://arxiv.org/abs/2210.04362v2 |
| **Referee report** | https://scipost.org/submissions/2210.04362v1/#report_1 · DOI [10.21468/SciPost.Report.6393](https://doi.org/10.21468/SciPost.Report.6393) |
| **Equation** | (10) in v1 |
| **Referee's validity rating** | high |

**Referee wrote:**

> However, Eq. (10) states that $1/\mathcal{P}^2 = T/\epsilon^2$, which seems to
> be inconsistent with the definition.

**v1 source** (`MLpspinPBC_v4.tex`):

```latex
T_{\rm photonic} = \frac{T}{\epsilon^2} = \frac{1}{\mathcal{P}^2}.
```

**v2 source** — the second equality is gone:

```latex
T_{\rm photonic} = \frac{T}{\epsilon^2}.
```

**Verification question.** Trace $\mathcal{P}$, $T$ and $\epsilon$ to their
definitions in v1. Is $T/\epsilon^2 = 1/\mathcal{P}^2$ actually true?

**Then check the consequence.** The authors deleted the identification rather
than repairing it, which is what one does when an equality is simply false. Did
anything downstream in v1 rely on $1/\mathcal{P}^2$? A deleted equation is only
harmless if nothing used it.

---

## Machine-readable summary

```json
[
 {"id":"2002.02120","before":"https://arxiv.org/abs/2002.02120v2","after":"https://arxiv.org/abs/2002.02120v3",
  "equation":"21","report":"https://scipost.org/submissions/2002.02120v2/#report_1","report_doi":null,
  "claim":"eq (21) has a double sum over pairs; Weinberg soft factor has a single sum over hard legs",
  "test":"Does the standard Weinberg soft factor sum over single hard legs?","fix_disputed":true},
 {"id":"2407.03100","before":"https://arxiv.org/abs/2407.03100v2","after":"https://arxiv.org/abs/2407.03100v3",
  "equation":"10","report":"https://scipost.org/submissions/2407.03100v2/#report_2","report_doi":"10.21468/SciPost.Report.10159",
  "claim":"exponents should be 4MN and 2N(M-1), not MN and N(M-1)",
  "test":"Count sites and bonds on the lattice of eq (2); which exponents follow?","fix_disputed":false},
 {"id":"2202.05191","before":"https://arxiv.org/abs/2202.05191v1","after":"https://arxiv.org/abs/2202.05191v2",
  "equation":"3.23","report":"https://scipost.org/submissions/2202.05191v1/#report_2","report_doi":"10.21468/SciPost.Report.5151",
  "claim":"KSRF relation applied to eq (3.23) does not yield Z^2 = 1/2",
  "test":"Apply KSRF to v1 and v2 forms; which gives Z^2 = 1/2?","fix_disputed":false},
 {"id":"2202.04603","before":"https://arxiv.org/abs/2202.04603v1","after":"https://arxiv.org/abs/2202.04603v2",
  "equation":"11","report":"https://scipost.org/submissions/2202.04603v1/#report_1","report_doi":"10.21468/SciPost.Report.4884",
  "claim":"a factor g wrongly prefixes the general two-body potential matrix element",
  "test":"Does the prefactor g double-count the coupling? Check dimensions.","fix_disputed":false},
 {"id":"2210.04362","before":"https://arxiv.org/abs/2210.04362v1","after":"https://arxiv.org/abs/2210.04362v2",
  "equation":"10","report":"https://scipost.org/submissions/2210.04362v1/#report_1","report_doi":"10.21468/SciPost.Report.6393",
  "claim":"the identity 1/P^2 = T/epsilon^2 contradicts the definitions",
  "test":"Trace P, T, epsilon to their definitions; does the identity hold?","fix_disputed":false}
]
```

---

## Where these came from

| | |
| --- | ---: |
| SciPost submissions read | 8,844 |
| Review rounds passing selection | 537 |
| Referee objection quotes | 990 |
| **Candidate errors (cards)** | **1,119** |
| — anchored to a specific equation | 236 |
| — awaiting human localization | 883 |
| Distinct papers | 513 |

Selection is deterministic: a theoretical-physics specialty, an arXiv-sourced
submission, a vetted referee report, a later revision proving the authors
responded, and a single referee sentence that both objects and cites a numbered
location. Roughly half of selected sentences describe a real theoretical error
and half concern notation or presentation; that is the ceiling for lexical rules
and the reason cards are ranked rather than filtered.

No card carries a severity label. Every one ships
`human_severity_label: unreviewed`, because a referee saying "wrong" routes a
paper to an expert — it does not certify that the flaw is real or fatal.

Method and full results: `docs/superpowers/specs/2026-09-05-scipost-error-card-miner-design.md`
and `docs/dataset-survey.md` in the same repository.
