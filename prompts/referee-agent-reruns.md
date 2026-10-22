# Referee agent — the two reruns, and a disclosure

Agents 7 and 9 crashed on the 64k output-token ceiling: both generated
commentary until they ran out of room, without reaching a conclusion. They
were relaunched at 21:26:54 and 21:30:33 UTC with modified prompts.

## Disclosure: the reruns carried a hint

The relaunches were meant to add only a length cap. They also each added a
clause to the "check the algebra" paragraph — and **each clause names the
class of the paper's own gold error.**

| Paper | Gold error | Clause added to the rerun prompt |
|---:|---|---|
| 7 | `m\|φ\|²` should be `m²\|φ\|²` in Eq. (1) — a **dimensional** slip | "...and to whether the quoted symbols have the **dimensions** they should" |
| 9 | "should the 2 be replaced by N?" in Eq. 5.23 — a **coefficient** that must track the construction | "...and to whether **coefficients** and index ranges match what the surrounding construction requires" |

That is a steer toward the answer. Paper 7 timed out again, so it cost
nothing there. **Paper 9 scored MATCH under the hinted prompt**, and that
MATCH cannot be credited to an unaided model.

### Tested, 2026-09-24: the hint did not carry the result

Paper 9 was re-run with a fresh agent under the canonical prompt plus the
length cap and **no error-class clause**. It matched again, at high
confidence, and argued the error from gauge invariance rather than asserting
it:

> `e^{2i\oint a + Ni\int B^3}` — the preceding sentence defines this as the
> N-th power `e^{Ni\oint a}`, and gauge invariance requires it. The exponent
> should be N, not 2.

So paper 9 stays in the count, and the headline is **6 of 11** — where it
started. See [`referee-agent-clean-rerun.md`](referee-agent-clean-rerun.md)
for the prompt and `minibench/run-2026-09-24/09.json` for the verdict.

Between finding the contamination and testing it, this file reported 5 of 10.
That was the right reading of the evidence available then: a match under a
prompt naming the error's class is not evidence of unaided performance, and
nothing short of a clean run could separate the two. The episode's result is
not that the number changed — it is that the contamination existed, was
found by writing the prompts down, and was shown not to matter.

**Paper 7 is still unresolved.** Two attempts hit the 64k output ceiling and a
third stalled without producing a report. It has never been scored and is
excluded from every denominator.

### How this got missed

The earlier disclosure said the reruns used "a non-identical prompt with a
1,200-word report cap", which was true and incomplete. The cap was the change
being tracked; the clause was added in the same edit and did not get named.
Diffing the two prompts against the canonical one is what surfaced it, which
is the argument for keeping this directory.

## Paper 7 rerun — diff against the canonical prompt

```diff
--- referee-agent.md (papers 1-12)
+++ this variant
@@ -2,3 +2,3 @@
 
-Read the manuscript at /tmp/eval_run/e662293c21/manuscript.tex . It is LaTeX source.
+Read the manuscript at /tmp/eval_run/633439e8dc/manuscript.tex . It is LaTeX source.
 
@@ -11,8 +11,10 @@
 
-Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from.
+Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from, and to whether the quoted symbols have the dimensions they should.
 
-For each error you find, report:
+IMPORTANT, on length: your final report must be under 1200 words. Do all the checking you need, but report only conclusions, not your working. Do not reproduce long derivations or list every equation you verified. Think privately; write briefly.
+
+For each error you find, report compactly:
 - the equation number as printed in the manuscript, or the nearest numbered equation plus where the problem sits relative to it
-- a quote of the offending expression
-- what is wrong, stated precisely
+- a short quote of the offending expression
+- what is wrong, in one or two sentences
 - what it should be instead, if you can determine that
```

## Paper 9 rerun — diff against the canonical prompt

```diff
--- referee-agent.md (papers 1-12)
+++ this variant
@@ -2,3 +2,3 @@
 
-Read the manuscript at /tmp/eval_run/e662293c21/manuscript.tex . It is LaTeX source.
+Read the manuscript at /tmp/eval_run/62ac0ca949/manuscript.tex . It is LaTeX source. It is long; read it in sections if you need to.
 
@@ -11,8 +11,10 @@
 
-Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from.
+Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from, and to whether coefficients and index ranges match what the surrounding construction requires.
 
-For each error you find, report:
+IMPORTANT, on length: your final report must be under 1200 words. Do all the checking you need, but report only conclusions, not your working. Do not reproduce long derivations or list every equation you verified. Think privately; write briefly.
+
+For each error you find, report compactly:
 - the equation number as printed in the manuscript, or the nearest numbered equation plus where the problem sits relative to it
-- a quote of the offending expression
-- what is wrong, stated precisely
+- a short quote of the offending expression
+- what is wrong, in one or two sentences
 - what it should be instead, if you can determine that
```

## Full text, paper 7 rerun

```text
You are a careful referee for a theoretical physics journal.

Read the manuscript at /tmp/eval_run/633439e8dc/manuscript.tex . It is LaTeX source.

Constraints, and these matter:
- Read that one file and nothing else. Do not read any other file on this machine and do not explore the filesystem.
- Do not use web search and do not fetch any URL.
- Work only from the manuscript's own content and your own physics knowledge.

Your task: find substantive errors in the physics or the mathematics. A substantive error is a wrong equation, a wrong sign, a missing or spurious factor, an invalid algebraic step, a dimensional inconsistency, a claim that contradicts another part of the same paper, or a derivation that does not follow from what precedes it. Typography, grammar, notation preferences, missing citations, and requests for more explanation are NOT errors: do not report them.

Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from, and to whether the quoted symbols have the dimensions they should.

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

## Full text, paper 9 rerun

```text
You are a careful referee for a theoretical physics journal.

Read the manuscript at /tmp/eval_run/62ac0ca949/manuscript.tex . It is LaTeX source. It is long; read it in sections if you need to.

Constraints, and these matter:
- Read that one file and nothing else. Do not read any other file on this machine and do not explore the filesystem.
- Do not use web search and do not fetch any URL.
- Work only from the manuscript's own content and your own physics knowledge.

Your task: find substantive errors in the physics or the mathematics. A substantive error is a wrong equation, a wrong sign, a missing or spurious factor, an invalid algebraic step, a dimensional inconsistency, a claim that contradicts another part of the same paper, or a derivation that does not follow from what precedes it. Typography, grammar, notation preferences, missing citations, and requests for more explanation are NOT errors: do not report them.

Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from, and to whether coefficients and index ranges match what the surrounding construction requires.

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
