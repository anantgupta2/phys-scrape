# prompts/

Every prompt this project sent to a subagent, verbatim, extracted from the
session transcript rather than retyped from memory.

| File | What it drove | Agents |
|---|---|---:|
| [`referee-agent.md`](referee-agent.md) | the 12-paper blind error-finding benchmark | 12 |
| [`referee-agent-reruns.md`](referee-agent-reruns.md) | two relaunches after output-ceiling crashes | 2 |
| [`code-review-agent.md`](code-review-agent.md) | review of the pipeline before merge | 1 |

## Why these are kept

The benchmark in `minibench/` reports a score. A score is only meaningful
alongside the exact instruction that produced it — how strongly the model was
steered, what it was forbidden to read, what it was told to report. Without
the prompt, `6 of 11` is a number with no denominator you can inspect.

Keeping them also made a problem visible that prose summaries had hidden. See
the disclosure in [`referee-agent-reruns.md`](referee-agent-reruns.md): two of
the fourteen referee agents ran a prompt carrying a hint pointed at their own
gold answer, and one of them scored a MATCH. That result is now excluded from
the clean count.

## Reproducing the benchmark run

The 12 agents each got one manuscript at a neutral path and nothing else. To
re-run against a different model, split `minibench/papers.txt` on its paper
delimiters, write each to its own directory, and send `referee-agent.md` with
`<RUN_DIR>` substituted. Score with `minibench/JUDGE.md` against
`minibench/answers.jsonl`.

Do not let the model under test see `minibench/answers.jsonl`, this directory's
disclosure section, or any path whose name encodes the paper's identity.
