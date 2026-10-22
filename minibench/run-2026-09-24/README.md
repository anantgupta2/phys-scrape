# Re-run, 2026-09-24

Two papers, one question each. Prompt:
[`../../prompts/referee-agent-clean-rerun.md`](../../prompts/referee-agent-clean-rerun.md)
— the canonical prompt plus a 1,200-word report cap, naming no error class.

## Paper 9 — did the hint carry the match?

**No. MATCH again**, at high confidence, argued from gauge invariance. The
2026-09-17 relaunch prompt had added a clause about coefficients and index
ranges, which is why the result was set aside; a run without it reaches the
same place. Paper 9 is restored to the count and the headline is **6 of 11**.

Verdict: [`09.json`](09.json).

## Paper 7 — can it be scored at all?

**No, still.** Four attempts now, three of them the same failure: generation
runs past the 64k output token ceiling before a report is produced. The third
attempt carried an explicit 1,200-word cap and overran anyway, so the
instruction bounds the report but not the work that precedes it. The fourth
stalled outright.

The earlier explanation on file — that the paper is unusually equation-sparse
— does not hold up. Measured across the set, paper 7 sits at 2.1 numbered-math
environments per 10k characters, second-lowest; paper 1 is lower at 1.8 and
matched. **The failure is reproducible. Why it happens is not established.**

Paper 7 is excluded from every denominator, so nothing in the headline depends
on it. Record: [`../run-2026-09-17/07.json`](../run-2026-09-17/07.json).
