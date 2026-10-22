# Referee agent — the benchmark prompt

Sent to 12 agents on 2026-09-17, one per paper. **All 12 prompts were
byte-identical except for the manuscript path.** Model: `claude-opus-5`, no
per-agent override, effort level xhigh.

## The prompt

```text
You are a careful referee for a theoretical physics journal.

Read the manuscript at <RUN_DIR>/manuscript.tex . It is LaTeX source.

Constraints, and these matter:
- Read that one file and nothing else. Do not read any other file on this machine and do not explore the filesystem.
- Do not use web search and do not fetch any URL.
- Work only from the manuscript's own content and your own physics knowledge.

Your task: find substantive errors in the physics or the mathematics. A substantive error is a wrong equation, a wrong sign, a missing or spurious factor, an invalid algebraic step, a dimensional inconsistency, a claim that contradicts another part of the same paper, or a derivation that does not follow from what precedes it. Typography, grammar, notation preferences, missing citations, and requests for more explanation are NOT errors: do not report them.

Check the algebra yourself where you can. Re-derive intermediate steps rather than trusting the text. Pay attention to whether each equation is consistent with the ones it is derived from.

For each error you find, report:
- the equation number as printed in the manuscript, or the nearest numbered equation plus where the problem sits relative to it
- a quote of the offending expression
- what is wrong, stated precisely
- what it should be instead, if you can determine that
- your confidence: high, medium, or low

Report only what you can argue for. If you find nothing you can defend, say so plainly: that is an acceptable answer. Do not pad the list with weak observations.

End with a one-line summary naming the equation numbers you are most confident about.
```

## What each agent could and could not see

Each agent ran in its own context with no memory of this project. It received
one file — its manuscript, as LaTeX source — at a path named by an opaque
hash, in a scratch directory holding nothing else.

Deliberately withheld:

- that a known error existed in the paper at all
- how many errors to expect
- the referee's report, the report DOI, the later version, any diff
- the paper's title, arXiv ID, and its own citation keys, all stripped from
  `papers.txt` before the run
- the paper's difficulty band

The prompt forbids reading any other file and forbids web search, so an agent
could not recover the paper's identity and look up its published referee
report. No report showed signs of leakage; several argued *against* the fix
the referee had asked for, which is the behaviour you would expect from a
model that had never seen it.

## Paper number to run directory

Directory names are run scratch, deliberately uninformative. Recorded here so
the transcript's prompts can be matched to results.

| Paper | Run directory | Spawned (UTC) |
|---:|---|---|
| 1 | `/tmp/eval_run/e662293c21/` | 20:42:34 |
| 2 | `/tmp/eval_run/4c56973a97/` | 20:42:39 |
| 3 | `/tmp/eval_run/5a9f730ce5/` | 20:42:44 |
| 4 | `/tmp/eval_run/5a811a278e/` | 20:42:48 |
| 5 | `/tmp/eval_run/f9c78094a0/` | 20:42:53 |
| 6 | `/tmp/eval_run/1c20973398/` | 20:42:57 |
| 7 | `/tmp/eval_run/633439e8dc/` | 20:43:08 |
| 8 | `/tmp/eval_run/37327ff5a4/` | 20:43:13 |
| 9 | `/tmp/eval_run/62ac0ca949/` | 20:43:17 |
| 10 | `/tmp/eval_run/6d320f3ca0/` | 20:43:22 |
| 11 | `/tmp/eval_run/93a57151ef/` | 20:43:27 |
| 12 | `/tmp/eval_run/1ab7b65d00/` | 20:43:32 |

Results per paper are in `minibench/run-2026-09-17/NN.json`; gold answers in
`minibench/answers.jsonl`.

## One design note

The prompt tells the agent that reporting nothing is an acceptable answer, and
tells it not to pad the list. This matters for reading the results: agents
still produced 57 unscored findings beyond the gold across 11 papers, a median
of 5 per paper, on papers known to contain exactly one referee-reported error.
Those went unverified. They are the open question the run left behind, not a
result it established.
