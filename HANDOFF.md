# Handoff

Written 2026-09-22. Read this first if you are picking the project up on a
different machine, or if you are me with no memory of the above.

## 1. Do this before anything else

Six commits exist only on this laptop:

    git push mine fix-retrieval-encoding-bugs

`mine` is https://github.com/michaelochurch/phys-scrape (Mike's fork).
`origin` is https://github.com/anantgupta2/phys-scrape (Anant's, untouched).
`main` here is identical to `origin/main` at 285e0ff — all 31 commits of new
work are on the branch `fix-retrieval-encoding-bugs`. Nothing has ever been
pushed to `origin`; opening a PR against it is a deliberate act, not a
leftover step.

Everything else on this machine is reproducible. Those six commits are not.

## 2. What this project is

Mine physics papers for errors that a *human referee* found, so the resulting
dataset can be used to test whether models can find the same errors.

**The one rule that governs every design decision:** no model may influence
what enters the dataset. Ground truth traces to a human referee's own words
or the benchmark measures nothing. Every selection step in this repo is
deterministic rules over referee text — grep and regex, no LLM anywhere in
the pipeline. Keep it that way.

## 3. Where the data comes from

**SciPost** (https://scipost.org), and only SciPost. It publishes referee
reports openly, each with a DOI, CC-BY 4.0, and — the load-bearing detail —
its submission `identifier` is the arXiv ID *with version* (`2002.02120v2`),
so a referee's complaint maps to an exact arXiv revision. `thread_hash` and
`is_resubmission_of` chain the rounds, so the authors' next version shows
what they changed in response.

The manuscript text itself comes from **arXiv** `/e-print/` (LaTeX source for
the exact before/after versions). SciPost supplies the identifier and the
ground truth; arXiv supplies the paper.

The four other datasets named in the README — ORB, MOPRD, PeerRead, AIBS —
were surveyed and yield **nothing**. See `docs/dataset-survey.md` for the
method and the numbers. Short version: ORB's physics content is the same
SciPost corpus a year staler; the rest are computer science, machine
learning, biology and grant review. Don't redo this survey.

## 3a. The pre-cutoff dataset

`data/precutoff/` holds the same pipeline restricted to referee reports
submitted before **2022-11-30**, ChatGPT's public release. The point is that
the ground truth cannot have been model-assisted, so a benchmark built on it
is not grading models against their own output.

The filter is on the **report** date, not the paper's — a 2021 paper can be
refereed in 2024, and that report is not pre-cutoff text. Because a report
always postdates its submission, every reviewed manuscript in the set is
pre-cutoff as well.

`tests/test_precutoff_dataset.py` reads the committed files and fails the
suite if any card carries a report dated on or after the cutoff. Do not weaken
those tests to make a build pass; the property is the dataset.

Each card carries `report_date`, `report_doi`, `referee_invited`,
`referee_signed`. 686 of 692 are from invited referees; the 6 Contributed
Reports are held in the human queue and never served.

Rebuild with `./rebuild.sh --precutoff`. The dataset is closed: no report
written after 2022-11-29 can ever enter it, so a later rebuild reproduces
these counts apart from records SciPost stops serving.

## 4. Current state

Branch `fix-retrieval-encoding-bugs`, 31 commits, clean tree, 205 tests
passing under Python 3.14.3 in `.venv`.

Pipeline output, all committed:

| | |
|---|---|
| 8,844 SciPost submissions enumerated | 45 pages, no offset gaps |
| 537 review rounds over 513 distinct arXiv papers | `data/scipost_candidates.jsonl` |
| 990 referee objections | 321 `stated_error`, 669 `corrective_request` |
| 1,119 error cards | from 1,215 cited locations |
| → 236 served | `data/error_cards_gold.jsonl` + `data/error_cards.jsonl` |
| → 883 queued for a human | `data/error_cards_unresolved.jsonl` |
| → 10 unreadable sources | `data/error_cards_skipped.jsonl` |
| 513 papers difficulty-labelled | `data/paper_levels.jsonl`, 4 bands |
| **pre-2022-11-30 dataset** | `data/precutoff/` — 143 anchored cards over 94 papers, 549 queued, 0 cutoff violations |

The 236 served cards are those where the referee's cited location could be
corroborated against the actual source diff: 203 `corroborated_exact`, 23
`corroborated_symbol`, 9 `corroborated_unique`, 1 `corroborated_author_marked`.
The 883 are not rejects — they are cards a human needs to localize.

**Leakage firewall.** `data/error_cards.jsonl` is the only file a model under
test may see. It holds exactly four keys: `card_id`, `excerpt_lines`,
`excerpt`, `task`. `card_id` is a SHA-256 prefix, not a readable identifier —
an earlier version leaked the answer through the ID itself. The gold file
carries everything else. If you add a field, add it to the gold file and
check `tests/` — there is a test that compares every gold value against every
model-facing value.

## 5. What is on disk but not in git

    data/scipost_sources/       1.9 GB   arXiv LaTeX source pairs
    data/scipost_api_cache/      72 MB   raw SciPost API JSON
    .venv/                       31 MB

All three are gitignored and all three rebuild from scratch:

    ./rebuild.sh              # full: ~6 min of API, then hours of arXiv
    ./rebuild.sh --no-download   # cards only, from sources already present
    ./rebuild.sh --help

Safe to interrupt and re-run; every stage skips work already done. Counts
will differ from the committed files on a later run because SciPost keeps
growing — that is expected, not a regression.

The 12 benchmark papers are committed as `minibench/papers.txt` (980 KB), so
the benchmark is reproducible without the 1.9 GB.

## 6. The minibenchmark

`minibench/` — 12 papers, 3 from each difficulty band, each with exactly one
referee-reported error.

    papers.txt        the 12 manuscripts, front matter stripped
                      (0 titles, 0 arXiv IDs, 0 arXiv citation keys survive)
    answers.jsonl     gold: referee quote, report DOI, equation number,
                      the before/after source of the fix
    JUDGE.md          protocol for an LLM judge to score a candidate answer
    selection.txt     why these 12
    run-2026-09-17/   first run: 12 result JSONs + SUMMARY.json

**Result: 6 of 11 agents found the gold error unaided**, 7 of 11 counting one
partial. Paper 7 is excluded — it has never completed a run. Paper 9 was
briefly excluded too, because its relaunch prompt named the class of its own
gold error; a clean re-run on 2026-09-24 matched again, so it is back in. See
`prompts/referee-agent-clean-rerun.md`.

Two findings from it that should shape what comes next:

1. **Difficulty band predicted nothing** (L1 2/3, L2 2/3, L3 1/2, L4 1/3).
   What did predict: whether the error admits a *convention defence*. Errors
   with no escape route — a divergent sum, a negative occupation number, a
   dimensional mismatch — went 6 match + 1 partial of 7. Errors defensible as
   convention or intent went 0 of 4. That distinction is not a field in the
   schema, and it probably should be.

2. **57 unscored other findings**, median 5 per paper, on papers known to
   hold exactly one referee-reported error. Unverified. If even a fraction
   survive scrutiny, model-proposed errors are a second discovery channel —
   but they would have no referee provenance, so they cannot enter this
   dataset under rule §2 without a separate human check.

Run conditions, verified from the session transcripts rather than memory:
**Opus 5 (`claude-opus-5`), no model override, effort level xhigh.** All 15
agents in that session logged the same model. Papers 7 and 9 ran a different
prompt after both crashed on the 64k output ceiling: a 1,200-word report cap
*and* — not noticed until the prompts were diffed — a clause naming the class
of that paper's own gold error. Paper 9 was re-run clean on 2026-09-24 and
matched again; paper 7 has still never completed. Treat 6/11 as near a ceiling for a single unaided pass, not a typical score, and not a statement
about models in general — every agent was the same model.

## 7. Open items

- **Push.** §1.
- **No physics has been verified by a qualified human.** Every card ships
  `human_severity_label: unreviewed`. A referee writing "this is wrong"
  routes a paper to an expert; it does not certify the flaw is real or fatal.
  Nothing in this repo should be described as a confirmed error.
- **Anant is waiting on examples.** `sample_errors_5.md` is the artifact for
  him: 5 worked candidates, every URL checked, written so a human or an LLM
  with web access can verify each one independently.
- Mike's commits are authored `mchurch8@gatech.edu`; registering that address
  on his GitHub account will link them to his profile.
- **Paper 7 has never been scored.** Four attempts, three of which generated
  past the 64k output ceiling before producing a report -- including one under
  an explicit 1,200-word cap, so the instruction does not bound the generation
  that precedes the report. An earlier note here blamed equation sparsity;
  that does not survive measurement (paper 7 sits at 2.1 numbered-math
  environments per 10k characters, and paper 1 is lower at 1.8 and matched).
  The failure is reproducible; the explanation is not established.
- Offered, not started: a `convention_defence` field on the cards (§6.1); a
  model comparison over the frozen 12; a filter for papers that cannot be
  scored at all, once someone works out what actually characterises them.

## 8. Map of the code

    scipost_mine.py            enumerate / select / fetch-manifest
    collect_arxiv_candidates.py  arXiv retrieval (Anant's, 5 bugs fixed)
    build_error_cards.py       diff-anchored localization, card emission
    rank_cards.py              heuristic ordering; never removes a card
    build_minibench.py         the 12-paper set
    build_review_evidence_queue.py, audit_latex_pairs.py, jsonl_io.py
    tests/                     205 tests
    prompts/                   every subagent prompt, verbatim, + a disclosure
    docs/dataset-survey.md     the four-dataset negative result
    docs/superpowers/specs/2026-09-05-scipost-error-card-miner-design.md

Two traps worth knowing before you edit:

- **LaTeX equation numbers are assigned at typesetting time.** You cannot
  find "equation (8)" by counting `\begin{equation}`. `build_error_cards.py`
  counts the rows LaTeX would actually print (align rows minus `\nonumber`)
  and corroborates against the diff. `\numberwithin{equation}{section}` makes
  "(3.26)" the 26th equation of section 3.
- **Referee text must be matched per sentence, not per report.** Document-level
  matching both admitted compliments and missed real complaints. Fields are
  joined with a newline, not a space — 2,033 field boundaries lack terminal
  punctuation and fabricated 13 quotes when joined with a space.
