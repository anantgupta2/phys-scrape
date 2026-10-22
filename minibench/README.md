# Minibenchmark: 12 papers, 12 errors

Twelve theoretical physics manuscripts, three at each difficulty level, each
containing **exactly one** error that a named referee identified in a public
report and the authors then changed in the next arXiv revision.

| File | What it is | Who sees it |
| --- | --- | --- |
| `papers.txt` | All 12 papers concatenated, 921 KB / ~230k tokens | **the candidate** |
| `answers.jsonl` | The gold errors, with referee quote, DOI and the fix | never the candidate |
| `JUDGE.md` | Grading protocol with the gold errors inlined | the judge |
| `selection.txt` | The twelve arXiv ids, for rebuilding | — |
| `run-2026-09-17/` | First run: per-paper verdicts and `SUMMARY.json` | — |

The prompt sent to the twelve agents in that first run is kept verbatim in
[`../prompts/referee-agent.md`](../prompts/referee-agent.md). The score is
**6 of 11** — one paper has never completed a run and is excluded.

Two of the twelve agents were relaunched under a prompt that named the class
of their own gold error;
[`../prompts/referee-agent-reruns.md`](../prompts/referee-agent-reruns.md)
records that, and the 2026-09-24 re-run that showed the hint did not change
the outcome.

## Running it

1. Give `papers.txt` to the candidate model. The instructions are in the file.
   It does **not** say how many errors there are, or that there is one per
   paper. Tell the model not to search the web.
2. Collect its answer verbatim.
3. Give `JUDGE.md` plus the candidate's answer to a judge model.

Papers are numbered 1-12 in `papers.txt`; `answers.jsonl` uses the same
numbers. Difficulty runs 3 papers per level in order, so papers 1-3 are level
1 and papers 10-12 are level 4 — do not show the candidate that ordering.

## What is removed from the papers

Titles, authors, affiliations, e-mail addresses, abstracts, acknowledgements,
bibliographies, arXiv identifiers, and arXiv numbers used as citation keys.
Verified: zero titles, zero identifiers and zero e-mail addresses survive.

Two idioms defeated the first version of this and were found only by grepping
the built file for `@`: jheppub's `\emailAdd{}`, which the `\email` rule did
not match, and a title block typeset by hand inside `flushleft` rather than
with `\author`, which no command-based rule can see. Both are now covered, and
`tests/test_minibench.py` holds a case for each.

**Citation keys still carry surnames.** `\cite{Jacobsen06}` names a cited
author, not one of the paper's own, and stripping every key would break the
`\cite` commands throughout. They stay.

**This is not real anonymity.** A physics paper is identified by its content;
anyone who searches a distinctive phrase will find it, and with it the
revision containing the fix. The removals raise the cost of looking the answer
up rather than making it impossible. If the candidate has web access, instruct
it not to search, and treat a suspiciously perfect score as evidence it did.

## What a score means

The gold error is the one a referee found. **A paper may contain other errors
nobody reported**, so the judge has a verdict for that: `OTHER_FINDING` is
neither a hit nor a miss, and should be read by a physicist rather than scored.

No error here has been verified by a qualified human. Every record carries
`human_severity_label: unreviewed`. A referee saying an equation is wrong is
strong evidence, not proof, and one of the twelve may yet turn out to be a
referee's mistake.

## Rebuilding

```bash
python build_minibench.py --ids minibench/selection.txt --out-dir minibench
```

Selection criteria: exactly one served benchmark card, exactly one cited
location anywhere in the referee record, a substantive error rather than a
presentation request, and no overlap with the five papers already published in
`sample_errors_5.md`.
