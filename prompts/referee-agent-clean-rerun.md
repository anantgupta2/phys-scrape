# Referee agent — the clean re-run (2026-09-24)

Written to settle one question: did paper 9's MATCH on 2026-09-17 depend on
the hint its relaunch prompt carried?

This prompt is the canonical [`referee-agent.md`](referee-agent.md) plus the
1,200-word report cap and a note that the file may be long. **It names no
error class.** The cap is kept because the original attempt on this paper
crashed on the 64k output ceiling without reaching a conclusion; without it
there is no result to compare.

```text
You are a careful referee for a theoretical physics journal.

Read the manuscript at <RUN_DIR>/manuscript.tex . It is LaTeX source. It may be long; read it in sections if you need to.

Constraints, and these matter:
- Read that one file and nothing else. Do not read any other file on this machine and do not explore the filesystem.
- Do not use web search and do not fetch any URL.
- Work only from the manuscript's own content and your own physics knowledge.

Your task: find substantive errors in the physics or the mathematics. A substantive error is a wrong equation, a wrong sign, a missing or spurious factor, an invalid algebraic step, a dimensional inconsistency, a claim that contradicts another part of the same paper, or a derivation that does not follow from what precedes it. Typography, grammar, notation preferences, missing citations, and requests for more explanation are NOT errors: do not report them.

Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from.

IMPORTANT, on length: your final report must be under 1200 words. Do all the checking you need, but report only conclusions, not your working. Do not reproduce long derivations or list every equation you verified. Think privately; write briefly.

For each error you find, report compactly:
- the equation number as printed in the manuscript, or the nearest numbered equation plus where the problem sits relative to it
- a short quote of the offending expression
- what is wrong, in one or two sentences
- what it should be instead, if you can determine that
- your confidence: high, medium, or low

Report only what you can argue for. If you find nothing you can defend, say so plainly: that is an acceptable answer. Do not pad the list with weak observations.

End with a one-line summary naming the equation numbers you are most confident about.
```

## Result

**Paper 9: MATCH.** The agent reported, at high confidence and with no
prompting toward coefficients:

> **Sec. 5.2, "Example 1: single foliation".** `e^{2i\oint a+ Ni\int B^3}` —
> The preceding sentence defines this as the N-th power `e^{Ni\oint a}`, and
> gauge invariance requires it. **The exponent should be N, not 2.**

The referee's own words were "In Eq. 5.23, should the $2$ be replaced by $N$?"
The agent found the same thing and argued it from gauge invariance rather than
asserting it.

So the hint did not carry that result, and paper 9 is restored to the count:
**6 of 11**, which is where it started. The contamination was real and was
worth excluding until it could be tested; testing it showed the outcome did
not depend on it.

Localisation is by section and quote, not by equation number, because LaTeX
source carries no printed numbers. `JUDGE.md` scores on content for this
reason.

Verdict record: `minibench/run-2026-09-24/09.json`.
