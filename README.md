# phys-scrape
For any new agent, you may change the methodology but your goal should be to extract errors in physics papers. This repository focuses on using arxiv diff versions and open peer review to find such papers. We want the errors to be human verified and agent scraped. Having them agent curated would induce a bias.
We have only tried directly scraping since that was the hardest one, please look at these datasets as well for possible venues.

| Dataset | Primary Domains | Size / Content | Surveyed 2026-09-08 |
|---|---|---|---|
| ORB Dataset (CERN/GitLab) | Physics (SciPost), AI/ML (OpenReview), biology (PeerJ) | >36k papers, >89k reviews | Its SciPost half is 99.1% of what the live API already gives us, a year staler. OpenReview is ICLR/NeurIPS; PeerJ is biology. **2 usable candidates, both unusable in practice.** |
| MOPRD (Multidisciplinary Open Peer Review Dataset) | PeerJ only — biology, medicine, CS, chemistry | 6,578 papers, multi-round reviews | Not F1000Research/Nature/BMJ as previously listed. No physics discipline at all. **0.** |
| PeerRead (AllenAI) | CS/ML (ICLR, NeurIPS, ACL) + arXiv cs.* drafts | ~14.7k papers, ~10.7k reviews | The arXiv half carries no review text; the reviewed half is ML/NLP. 35 physics cross-lists, all with empty reviews. **0.** |
| AIBS Open Peer Review Repository | Grant review panels | 16 compiled datasets | A bibliography, not a corpus. 14 of 16 are grant scores with no text; the physics subset is not public. **0.** |

Full method and numbers: [`docs/dataset-survey.md`](docs/dataset-survey.md).
SciPost remains the only source of theoretical physics papers with public
referee-identified errors and recoverable arXiv revision pairs.

## Pipelines in this repository

Two paths to candidates. The second is the one to build on.

### 1. arXiv revision diffs (original)

Finds papers with more than one arXiv version and diffs the LaTeX source.
Tells you *that* something changed, not *what was wrong*, so every candidate
needs a physicist. Fifteen hand-reviewed papers produced one usable case.

```bash
python collect_arxiv_candidates.py discover --output data/candidates.jsonl --per-query 500
python collect_arxiv_candidates.py fetch-sources --input data/candidates.jsonl \
    --output data/candidates_sources.jsonl --source-dir data/sources
python audit_latex_pairs.py --input data/candidates_sources.jsonl \
    --source-dir data/sources --output data/triage.jsonl
```

### 2. SciPost referee reports (current)

Sources ground truth from public peer review: a referee states what is wrong
and where, and the following revision shows the fix. 8,844 submissions yield
**538 candidates carrying 995 referee objection quotes** over 1,128 distinct
cited locations, each with a report DOI. 237 of those are localized to the
exact equation; the remaining 891 go to a human queue.

```bash
./rebuild.sh
```

That is the whole thing. It creates the virtualenv, installs dependencies,
queries SciPost, selects candidates, downloads the arXiv sources, builds the
cards and ranks them. **Safe to interrupt** — re-running resumes rather than
starting over, and a paper whose sources are already on disk costs no network
request at all.

| | |
| --- | --- |
| First run | a few hours, almost all of it the arXiv download |
| Later runs | about a minute, if the sources are already there |
| Disk | ~2.5 GB (1.9 GB sources, 75 MB API cache) |
| Needs | python3.10+, network. No API keys, no accounts. |

```bash
./rebuild.sh --no-download   # rebuild cards from sources already on disk
./rebuild.sh --refresh       # re-query SciPost even if the cache exists
./rebuild.sh --help
```

**You do not need to run this to read the results.** Every committed card
carries the referee's quote, the cited equation and the changed LaTeX inline,
so the benchmark set and the review queue can both be worked straight from the
repository. The download is only for rebuilding.

**Counts will not match the committed files**, and that is expected: SciPost
keeps accepting submissions, so a later run sees papers that did not exist
when these were built. The rules are fixed; the corpus is not.

<details>
<summary>Running the stages individually</summary>

```bash
python scipost_mine.py enumerate --cache-dir data/scipost_api_cache
python scipost_mine.py select --cache-dir data/scipost_api_cache \
    --output data/scipost_candidates.jsonl
python scipost_mine.py fetch-manifest --candidates data/scipost_candidates.jsonl \
    --output data/fetch_manifest.jsonl
python collect_arxiv_candidates.py fetch-sources --input data/fetch_manifest.jsonl \
    --output data/scipost_sources_status.jsonl --source-dir data/scipost_sources
python build_error_cards.py --candidates data/scipost_candidates.jsonl \
    --source-dir data/scipost_sources --output-dir data
python rank_cards.py --gold data/error_cards_gold.jsonl \
    --unresolved data/error_cards_unresolved.jsonl
```
</details>

Design and measured results: `docs/superpowers/specs/2026-09-05-scipost-error-card-miner-design.md`.

### What comes out

| File | Rows | What it is |
| --- | ---: | --- |
| `data/error_cards.jsonl` | 237 | Benchmark cards. A manuscript excerpt and a task. **The only file a model may see.** |
| `data/error_cards_gold.jsonl` | 237 | The answers: referee quote, report DOI, cited equation, the revision pair and its diff, rank and the signals behind it. |
| `data/error_cards_unresolved.jsonl` | 891 | Cards a human must localize. Same evidence, plus the candidate hunks, minus the excerpt. |
| `data/error_cards_skipped.jsonl` | 10 | Papers whose sources could not be read, with the reason. |
| `data/scipost_candidates.jsonl` | 538 | The selected review rounds, before card construction. |

The two card files join on `card_id`. A gold or queued record is
self-contained — it carries the referee's words, the cited equation, and the
LaTeX that changed — so a physicist can adjudicate a card without opening
anything else. Both queues are sorted: `rank` 1 is the strongest evidence,
`rank_signals` says why.

### Two rules that matter

**Selection is deterministic.** No model decides which papers enter the
dataset. A model may rank the queue so a reviewer sees the strongest
candidates first, but it never removes one, so the selected population is
reproducible by running the rules. If Claude chose the errors, testing Claude
on them would prove nothing.

**Gold evidence is a separate file.** `error_cards.jsonl` is the only file
that may be shown to an evaluated model. `error_cards_gold.jsonl` holds the
referee quote, DOI, later version and diff. A test asserts nothing leaks
across.

A third file, `error_cards_unresolved.jsonl`, holds cards whose excerpt could
not be anchored to the equation the referee cited. They carry the quote and
the candidate hunks but no excerpt, and go to a reviewer rather than to a
model: an unanchored excerpt may not contain the error, and scoring a model
against it would measure our localization, not the model.

Severity is never assigned automatically: every card ships
`human_severity_label: unreviewed`. A referee saying "wrong" routes a paper to
an expert; it does not certify that the flaw is fatal.

### Tests

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q      # 168 tests
```


                  ┌─────────────────────────────────────────┐
                  │ Benchmark Dataset                       │
                  │ - Errata & Retractions (arXiv / SciPost)│
                  │ - Injected Derivation Perturbations     │
                  └──────────────────┬──────────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────────┐
                  │ Candidate LLM Grader                    │
                  │ (Extracts: Step ID, Taxonomy, Fix)      │
                  └──────────────────┬──────────────────────┘
                                     │
                 ┌───────────────────┴────────────────────┐
                 ▼                                        ▼
    ┌──────────────────────────┐             ┌─────────────────────────┐
    │ Programmatic Verifier    │             │ Alignment with Ground   │
    │ - Symbolic check (SymPy) │             │ Truth Error Rubric      │
    │ - Limit/Asymptotic tests │             │ (Precision / Recall)    │
    └──────────────────────────┘             └─────────────────────────┘
