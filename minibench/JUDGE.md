# Judge protocol

You are grading one candidate's attempt to find errors in twelve physics
manuscripts. For each paper you are given the **gold error** — one that a named
referee identified in a public report, and which the authors then changed in
the next revision — and the **candidate's claims** about that paper.

Decide, for each paper, whether the candidate found the gold error.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `MATCH` | Same location **and** same defect. The candidate names the equation the referee named (or unambiguously describes it) and says what is wrong in a way that means the same thing as the referee's objection. Different wording is fine; different substance is not. |
| `PARTIAL` | Half of it. Right equation, but the described defect is vague, wrong, or a different problem in the same equation. Or: correct defect described, but attached to the wrong equation number when the paper's numbering makes that a real error. |
| `OTHER_FINDING` | The candidate makes a substantive claim about this paper that is **not** the gold error. This is not a miss and not a hit. The referee found one error; the paper may contain others nobody reported. Flag it for a human. |
| `MISS` | The candidate said nothing about this paper, or only made non-substantive remarks (typography, notation, requests for clarification). |

## Rules

1. **Judge substance, not vocabulary.** "The exponent needs a minus sign" and
   "should be $e^{-x}$ not $e^{x}$" are the same claim.
2. **Do not credit hedging.** "Equation 6 may warrant checking" is not a
   finding. The candidate must say what is wrong.
3. **Do not credit a shotgun.** If the candidate lists many possible problems
   for one paper and one happens to coincide with the gold, that is `PARTIAL`
   at best — note how many claims were made.
4. **You are not re-refereeing the paper.** Do not decide whether the referee
   was right. Decide whether the candidate found what the referee found.
5. **`OTHER_FINDING` is not failure.** Record it plainly so a physicist can
   look. Do not inflate it into a match.
6. **Equation numbers may be off by a little.** The candidate sees LaTeX
   source, not the typeset PDF, so it may count numbers differently. If the
   quoted content matches, treat the location as correct.

## Output

Return one JSON object per paper, then a summary.

```json
{"paper_number": 1, "verdict": "MATCH",
 "candidate_claim": "<what they said, quoted or tightly summarised>",
 "gold_claim": "<the referee's objection, summarised>",
 "reasoning": "<one or two sentences>",
 "claims_made_about_this_paper": 1}
```

Summary:

```json
{"match": 0, "partial": 0, "other_finding": 0, "miss": 0,
 "by_level": {"1": {"match": 0, "of": 3}, "2": {"match": 0, "of": 3},
              "3": {"match": 0, "of": 3}, "4": {"match": 0, "of": 3}}}
```

Nothing else. No preamble.

---

## The gold errors

### Paper 1  (difficulty level 1)

- **Equation as printed:** 3
- **Referee wrote:** • Page 4, I believe equation 3 is incorrect, should the (1+n/v)^v be (1+M/v)^-n ?
- **Changed in the next revision:**
  - before: `	P_{M}(n) = \frac{\Gamma(n+M)}{\Gamma(n+1)\Gamma(M)}(1+n/\nu)^{\nu}(1+\nu/M)^{-M} \; ,`
  - after:  `	P_{M}(n) = \frac{\Gamma(n+M)}{\Gamma(n+1)\Gamma(M)}(1+M/\nu)^{-n}(1+\nu/M)^{-M} \; ,`

### Paper 2  (difficulty level 1)

- **Equation as printed:** 6
- **Referee wrote:** 4, I think the exponent in (6) is missing an overall minus sign.
- **Changed in the next revision:**
  - before: `\langle N_i \rangle  = \frac{1}{{\rm e}^{\beta \left(\mu - \epsilon_i\right)} -1 } \,.`
  - after:  `\langle N_i \rangle  = \frac{1}{{\rm e}^{\beta \left(\epsilon_i-\mu \right)} -1 } \,.`

### Paper 3  (difficulty level 1)

- **Equation as printed:** 3
- **Referee wrote:** - Eq. 3 has a mistake: $p(c^*|\omega)$ on the righthand side should be $p(c^*|\omega,C)$.
- **Changed in the next revision:**
  - before: `= \int d \omega \; p(c^* | \omega) \; p(\omega | C )`
  - after:  `= \int d \omega \; p(c^* | \omega, C) \; p(\omega | C )`

### Paper 4  (difficulty level 2)

- **Equation as printed:** 2
- **Referee wrote:** 1) Eqs. 2a and 2b appear to be missing a factor $y$ in front of the last cosine term.
- **Changed in the next revision:**
  - before: `   h_{1}:=\left|x \cos \left(\varphi_{1}\right)+y \sin \left(\varphi_{1}\right)\right|^{n}+\left|-x \sin \left(\varphi_{1}\right)+\cos \left(\varphi_{`
  - after:  `   h_{1}:=\left|x \cos \left(\varphi_{1}\right) + y\sin \left(\varphi_{1}\right)\right|^{n}+\left|-x \sin \left(\varphi_{1}\right) + y\cos \left(\varp`

### Paper 5  (difficulty level 2)

- **Equation as printed:** 4
- **Referee wrote:** 1 - In the mass shell delta function for particle n in equation (4), p_n should read p_n^2.
- **Changed in the next revision:**
  - before: `  &\;\times\frac{{\rm d}^4p_n}{(2\pi)^3}\,\delta(p_n-s_n)\Theta(E_n)\;`
  - after:  `  &\;\times\frac{{\rm d}^4p_n}{(2\pi)^3}\,\delta(p_n^2-s_n)\Theta(E_n)\;`

### Paper 6  (difficulty level 2)

- **Equation as printed:** 2.13
- **Referee wrote:** I do not see how the transformation in eq.(2.13) could be realised as a transformation acting only on those degrees of freedom.
- **Changed in the next revision:**
  - before: ` \Sigma \to g_L  \Sigma \, g_R^\dagger.`
  - after:  ` \Sigma \to g_L  \Sigma \, g_R^\dagger,`

### Paper 7  (difficulty level 3)

- **Equation as printed:** 1
- **Referee wrote:** 2 - In Eq. (1), $m |\phi|^2$ should be replaced by $m^2 |\phi|^2$.
- **Changed in the next revision:**
  - before: `\mathcal L = \sum_{i=1}^{N_f} |(\partial_\mu - i A_\mu)\phi_i|^2 + m |\phi|^2+\frac{g}{4}|\phi|^4 + \frac{1}{4e^2}F_{\mu\nu}^2.`
  - after:  `\mathcal L = \sum_{i=1}^{N_f} |(\partial_\mu - i A_\mu)\phi_i|^2 + m^2 |\phi|^2+\frac{g}{4}|\phi|^4 + \frac{1}{4e^2}F_{\mu\nu}^2.`

### Paper 8  (difficulty level 3)

- **Equation as printed:** 33
- **Referee wrote:** It would be helpful if the authors could clarify whether there is a factor of $1/2$ missing in Eq. (33).

### Paper 9  (difficulty level 3)

- **Equation as printed:** 5.23
- **Referee wrote:** In Eq. 5.23, should the $2$ be replaced by $N$?
- **Changed in the next revision:**
  - before: `    e^{2i\oint a+ Ni\int B^3}~,`
  - after:  `    e^{Ni\oint a+ Ni\int B^3}~,`

### Paper 10  (difficulty level 4)

- **Equation as printed:** 2.5
- **Referee wrote:** On Eq. 2.5 a factor L is missing inside the logarithm.
- **Changed in the next revision:**
  - before: `\begin{equation} \label{eq:S-cyl} /   S_N(\ell/L,\mathrm{vac}) = \frac{(N + 1) c}{6 N} \log \left(\sin \frac{\pi \ell}{L} \right) \,.`
  - after:  `\begin{equation} \label{eq:CC2} /   S_N(\ell/L,\mathrm{vac}) = \frac{c}{6}\frac{N + 1}{N}\log \left[ L \sin \left(\frac{\pi \ell}{L}\right) \right] \,`

### Paper 11  (difficulty level 4)

- **Equation as printed:** 11
- **Referee wrote:** By the way, the second formula (11) is probably wrong and should be (in the right units) '$a_B = -1/g_B$', not '$-1/g$'.
- **Changed in the next revision:**
  - before: `a_{\text{B}} \equiv -\frac{\hbar^2}{m g} `
  - after:  `a_{\text{B}} \equiv -\frac{\hbar^2}{m g_{\text{B}}} `

### Paper 12  (difficulty level 4)

- **Equation as printed:** 1.9
- **Referee wrote:** 4.In Equation (1.9), scaling invariance does not explain the C_{000} factor.I think it comes from the normalization that \omega_{000} should be 1.
- **Changed in the next revision:**
  - before: `  \boxed{\omega_{123} = C_{123} \sqrt{\frac{C_{000}}{C_{011}C_{022}C_{033}}}}\ ,`
  - after:  `  \boxed{\omega_{123} = C_{123} \sqrt{\frac{C_{000}}{C_{011}C_{022}C_{033}}}}\ .`

