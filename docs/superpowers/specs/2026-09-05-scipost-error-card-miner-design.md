# SciPost error-card miner — design

Date: 2026-09-05
Status: implemented (enumerate, select, version pairs, card generator)

## Purpose

Produce benchmark cards for physics papers containing errors that were
identified by human referees, so that frontier models can be scored on finding
those errors.

The defining constraint is that ground truth must not originate from an LLM.
If a model finds the errors and is then graded on finding them, the benchmark
measures nothing. Every card's ground truth therefore traces to a named,
publicly posted referee report with a DOI.

This supersedes, for evidence-gathering purposes, the arXiv v1/v2 diff approach
already in the repository. That approach yielded one usable candidate from
fifteen hand-reviewed papers, because a diff shows that something changed
without showing what was wrong. A referee report states the error directly.

## Source

SciPost (https://scipost.org) is an open-access physics publisher whose entire
referee process is public. Its JSON API requires no authentication:

    https://scipost.org/api/submissions/?format=json&limit=200&offset=<n>

Measured against a 1,000-submission sample of the 8,846 available on
2026-09-05:

| Property | Sample | Projected corpus |
| --- | ---: | ---: |
| `acad_field == "Physics"` | 987 | ~8,700 |
| has at least one report | 744 | ~6,500 |
| report + arXiv identifier + a later round | 159 | ~1,400 |
| report text containing error language | 102 | ~900 |

Each submission record carries `identifier`, `thread_hash`,
`is_resubmission_of`, `status`, `specialties`, and a `reports` list whose
entries include `report`, `weaknesses`, `requested_changes`, `validity`,
`status`, `url`, and `doi_string`.

Two properties of the schema matter to this design:

1. For arXiv-sourced submissions, `identifier` is the arXiv ID **with its
   version** (`2208.00606v1`). The referee's complaint therefore attaches to a
   known arXiv version, and the following round names the version that
   contains the fix. Version alignment is exact and requires no inference.
2. Rounds are not always v1 to v2. Observed real threads include
   `2208.01226v2 -> v3` and a `2207.11940v0`. Version pairs must be read from
   the thread, never assumed.

Content is licensed CC-BY 4.0 and reports carry individual DOIs, so report
text may be retained provided cards record the DOI for attribution.

## Decisions

| Decision | Choice |
| --- | --- |
| Output unit | Full benchmark card: v-before excerpt, referee quote, location, the fixing change |
| Selection | Deterministic rules only. Claude ranks the surviving queue; it never removes a candidate |
| Scope | All physics theory and computational specialties, not only hep-th/quant-ph/gr-qc |
| Localization | Anchor on the v-before/v-after diff, corroborate with the referee's cited location |
| Unlocalizable cards | Emitted and tagged, never dropped |

Restricting selection to rules is what keeps the dataset free of LLM
influence: every candidate is reproducible by running the rules, and Claude
cannot silently exclude a category of error it happens to be weak at.

## Architecture

Three stages, each reading and writing JSONL, following the existing flat-script
and atomic-write conventions in the repository.

    scipost_mine.py enumerate
        -> data/scipost_api_cache/submissions_<offset>.json
    scipost_mine.py select
        -> data/scipost_candidates.jsonl

    collect_arxiv_candidates.py fetch-sources   (existing, one change)
        -> data/scipost_sources/<arxiv_id>/v<n>.tar | v<n>.tex.gz

    build_error_cards.py
        -> data/error_cards.jsonl        (model-facing)
        -> data/error_cards_gold.jsonl   (gold evidence)

Enumeration is separated from selection because enumeration is the slow,
rate-limited step and its output is stable. Selection and card building then
run repeatedly against the local cache without further network access, which
also makes the pipeline reproducible by a third party holding the cache.

### Change to existing code

`collect_arxiv_candidates.fetch_sources` currently hardcodes `for version in
(1, 2)`. It gains a version-pair argument supplied per row, defaulting to
`(1, 2)` so the existing arXiv-diff path is unaffected.

`build_review_evidence_queue.py` is left in place. Its SciPost-matching purpose
is superseded by direct API access, but it still serves the arXiv-diff path.

## Selection rules

A submission round qualifies only if every condition holds. No scoring, no
judgment, no model involvement.

1. `acad_field == "Physics"` and at least one specialty in an explicit
   allowlist. A substring test on "Theory" or "Computational" must not be
   used: it would silently drop Quantum Physics, Mathematical Physics,
   Gravitation/Cosmology, and Statistical and Soft Matter Physics, which is
   481 of the 1,000 sampled submissions. The allowlist is:

       Condensed Matter Physics - Theory
       Condensed Matter Physics - Computational
       High-Energy Physics - Theory
       High-Energy Physics - Phenomenology
       Quantum Physics
       Mathematical Physics
       Gravitation, Cosmology and Astroparticle Physics
       Statistical and Soft Matter Physics
       Atomic, Molecular and Optical Physics - Theory
       Nuclear Physics - Theory

   Specialties ending in `- Experiment` are excluded by omission.
2. `identifier` is an arXiv identifier, i.e. it does not start with `scipost_`.
3. At least one report with `status == "vetted"`.
4. `status == "resubmitted"`, which is SciPost's own marker that this round was
   superseded by a later one and therefore that the authors responded. The
   `thread_hash` group then supplies the identifier of the following round,
   which names the arXiv version containing the fix.
5. At least one vetted report containing a **single sentence** that both
   objects and cites a numbered location, and is not about presentation.

Matching is sentence-level, not document-level. Document-level co-occurrence
was tried first and failed in both directions against real reports:

- It admitted a compliment. "does not follow" appeared in praise on one
  submission while the cited location sat in an unrelated sentence.
- It missed a real objection. Report 1 on arXiv:2207.00854v2 reads "I do not
  understand the first equality in (8)" and then derives a counterexample.
  That report contains no word from any error-keyword list, so the paper
  qualified only through a second referee, and the better objection would
  have been lost.

Requiring both signals in one sentence fixes both cases and yields the exact
quote to record as evidence. Consequently the objection vocabulary includes
hedged forms -- "do not understand", "not clear how", "not sure I agree",
"should be", "should read", "fails to hold" -- alongside blunt ones, and a
prose filter rejects sentences about punctuation, grammar, spelling, captions
and numbering.

A bare parenthesised number is treated as an equation reference, since that is
how referees most often cite one, but only from 1 upward: "the delta(0) in
Fourier" is notation, not a citation.

**Precision is roughly one real error in two**, and that is the ceiling for
lexical rules. Tightening them further -- demanding inline math, dropping
section references -- was measured and rejected: it discarded real objections
while still admitting noise such as "(28) should be Eq.~(28) in the LaTeX
source file". Separating "equation 3 is incorrect" from "all equations should
be numbered" is a semantic judgment. That is what the ranking step is for, and
why ranking may reorder the queue but never shorten it.

`validity` is recorded on each card but is not a selection criterion. Measured
correlation with error language is weak and the field is unset on 36% of
reports; a referee may rate validity `high` while still identifying a specific
wrong equation.

## Localization

For each qualifying (submission, report, cited-location) triple:

1. Parse the report text into cited locations. Recognized forms:
   `Eq. (20)`, `Eq 20`, `equation (20)`, `Eqs. (20)-(22)`,
   `Theorem 3`, `Theorem 3.2`, `Lemma 4`, `Proposition 2`, `Section 4.2`.
2. Read the v-before and v-after main TeX using
   `audit_latex_pairs.main_tex`, which already handles both tar and bare
   gzipped sources.
3. Compute changed hunks with `difflib.SequenceMatcher`.
4. Retain hunks whose before-or-after text contains a numbered mathematical
   environment (`equation`, `align`, `gather`, `multline`, `eqnarray`, each
   without a starred form) or a theorem-like environment.
5. Choose an anchor, and record how well it is evidenced.

| Confidence | Meaning | Served? |
| --- | --- | :-: |
| `corroborated_symbol` | A symbol the referee quoted appears in the excerpt | yes |
| `corroborated_author_marked` | The authors tagged the change (`\changed`) | yes |
| `corroborated_unique` | Only one equation changed, within tolerance | yes |
| `corroborated_exact` | Ordinal matches the cited number exactly | yes |
| `corroborated_near` | Closest changed equation is 1-3 ordinals away | no |
| `contradicted_symbols` | A quoted symbol is absent from the excerpt | no |
| `unresolved` | No changed equation is comparable to the citation | no |

Numbers are matched two ways, because papers print both: a dotted citation
such as "(3.26)" against a section-qualified label, only within the cited
section; a plain one against the document ordinal.

Symbols outrank ordinals. Referees frequently quote the offending expression
verbatim -- "it should read $j(-h)^{*}$ instead of $J(-h)^{*}$" -- and on real
cards this confirmed 5 anchors and contradicted 3 that ordinal matching had
accepted. Matching uses subscripted compounds in preference to bare macros and
ignores formatting macros: an early version treated `\rm` as a symbol, and it
appears in nearly every excerpt.

Before any ordinal reasoning, a hunk whose after-text carries an author
revision macro (`\changed`, `\revised`, `\added`) wins outright. Authors who
tag their own revisions have already localized the fix; 20 of the 74 changed
hunks on arXiv:2207.00854 were tagged this way.

The approximate ordinal count is a tie-breaker with a tolerance window, not an
emulation of LaTeX numbering. Tolerance is 3: the fracton case sat exactly two
ordinals from the referee's cited number, too close to a tolerance of 2 to
depend on. But only an exact match is served. Measured over 37 real anchored
cards, 20 matched exactly and 17 sat one to three away, and a spot-checked
distance-3 case pointed at a charge table while the referee was objecting to a
superpotential.

Measured on arXiv:2207.00854 v2->v3, this reduces 74 changed hunks to 6
containing numbered equations, one of which holds the referee's target.

An `unresolved` card is not a rejected card. Authors sometimes rebut a
referee rather than revise, and the referee may still be correct. These are
surfaced for the physicist rather than discarded, consistent with the existing
codebase's practice of retaining failures for retry.

### Excerpt extraction

The model-facing excerpt is taken from the v-before source: the anchor hunk
expanded outward to the nearest enclosing environment boundaries, plus ten
lines of context on each side, capped at 400 lines. It contains no diff
markup, no v-after content, and no referee text.

## Card schema

Two files, joined on `card_id`. One card is emitted per distinct cited
location, so every card has exactly one answer.

Output is three files, not two. A card whose anchor is not evidenced still has
an excerpt, but that excerpt is a guess and may not contain the error at all;
serving it would ask a question the excerpt cannot answer and score a model
wrong for our imprecision. Those go to a reviewer, with their referee quote
and candidate hunks and no model-facing excerpt:

    data/error_cards.jsonl              anchored; the only model-facing file
    data/error_cards_gold.jsonl         gold evidence for the above
    data/error_cards_unresolved.jsonl   human localization queue

Nothing is discarded. A referee can be right about a paper whose authors
rebutted them.

`data/error_cards.jsonl` — the only file that may be shown to an evaluated
model:

    {
      "card_id": "2208.00606v1-eq20",
      "arxiv_id": "2208.00606",
      "version": 1,
      "excerpt_lines": [104, 131],
      "excerpt": "<v-before LaTeX>",
      "task": "Identify any incorrect claim in this excerpt and explain why."
    }

`data/error_cards_gold.jsonl` — never served to a model:

    {
      "card_id": "2208.00606v1-eq20",
      "scipost_submission_url": "https://scipost.org/submissions/2208.00606v1/",
      "report_url": "https://scipost.org/submissions/2208.00606v1/#report_1",
      "report_doi": "10.21468/SciPost.Report.13826",
      "referee_quote": "(20): The first equation is wrong: ...",
      "referee_validity_rating": "ok",
      "cited_location": {"kind": "equation", "number": "20"},
      "supporting_quotes": [],
      "main_tex": "paper.tex",
      "location_confidence": "corroborated_symbol",
      "candidate_hunks": [],
      "v_before": 1,
      "v_after": 2,
      "anchor_hunk": {"before_lines": [104, 131], "after_lines": [104, 128]},
      "diff_summary": {"added": 12, "deleted": 9},
      "retrieved_at": "2026-09-05T18:00:00Z",
      "text_hash": "sha256:...",
      "evidence_class": "referee_stated_technical",
      "human_severity_label": "unreviewed",
      "rank": 3,
      "rank_rationale": "<Claude's ordering note>"
    }

`human_severity_label` is `unreviewed` on every card the miner produces. A
referee stating that something is wrong routes a paper to expert review; it
does not by itself certify that the flaw is fatal. This preserves the
distinction already drawn in `data/collection_status_and_risks.md`, and it is
the single field an expert fills in.

## Safeguards

**Leakage.** The model-facing and gold sides are separate files rather than
separate fields, so gold evidence cannot be served by accident. A test asserts
that no gold-side string appears in the model-facing file.

**Rate limiting.** Enumeration uses a conservative delay and caches every API
response to disk on first pass. Selection and card building are offline.

**Attribution.** Every gold record carries `report_doi` and
`scipost_submission_url`, satisfying CC-BY.

**Reproducibility.** Every record carries `retrieved_at` and a `text_hash` of
the report text it quotes, so a later change on SciPost is detectable.

## Testing

1. **Leakage invariant.** No referee quote, gold field name, or v-after content
   appears anywhere in `error_cards.jsonl`.
2. **Selection rules** against fixtures, including the observed false positive:
   "does not follow" inside a compliment, citing no location, must be rejected.
3. **Location parsing** across all recognized forms.
4. **Thread ordering** against the real irregular cases: a `v0` round, and a
   `v2 -> v3` round.
5. **Wire format.** One real recorded API response is committed as a fixture,
   so a SciPost schema change fails loudly rather than silently yielding zero
   candidates.
6. **Regression.** The existing 17 tests continue to pass.

## Out of scope

- Adjudicating severity. Cards are routed to a human, never labeled fatal.
- The other three data sources in the README (ORB, MOPRD, PeerRead, AIBS).
- Synthetic error injection.
- Claude-as-grader evaluation.
- Removal or rewriting of the existing arXiv-diff pipeline.

## Measured yield

Full enumeration on 2026-09-05 returned 8,846 submissions and produced
**462 candidates carrying 793 referee objection quotes**.

**59% of candidates are not v1 -> v2 rounds.** Observed pairs include v2->v3
(181), v3->v4 (44), v1->v3 (17), v2->v4 (14) and v4->v5 (8). Assuming v1/v2
would have fetched the wrong revisions for 274 of the 462 papers, including
every verified example below.

The two largest drops are informative. Requiring an arXiv identifier costs 36%
because many SciPost submissions are hosted natively rather than on arXiv;
those have referee reports but no v1/v2 source pair to diff. Requiring error
language costs 77% of what remains, which is the expected shape: most referee
reports request clarification rather than report a mistake.

## Verified examples

Five candidates were confirmed by hand against their arXiv source pairs.

| Paper | Referee's objection | What changed |
| --- | --- | --- |
| 2207.00854 v2->v3 | "I do not understand the first equality in (8)"; shows it fails on curved space | v3 adds the missing hypothesis that the vector field is covariantly constant |
| 2002.02120 v2->v3 | "(21) is incorrect... presented as the main result, does not agree with the standard Weinberg soft factor" | v3 restructures the soft factor to sum over external legs |
| 2412.01149 v2->v3 | "in the third equation in (3.26) it should read k^jk^kp^0" | index contraction corrected from k^i k^j to k^j k^k |
| 2411.06954 v2->v3 | "a small mistake right before Eq.(22)" about CNOT counting | gate scaling corrected from D^5 to D^4(D-2) |
| 2411.08030 v1->v2 | "(4.16) should read alpha_{l-1} nu_l = F_{l-1} nu_{l-1}" | corrected, but inside a 63-hunk restructuring: localizes poorly |

2002.02120 is still unresolved after three rounds and two "ask for major
revision" recommendations, so it is a live dispute rather than a settled
correction. The distinction belongs to the expert, not the miner.

## Known risks

1. **SciPost is not representative.** It covers a specific slice of physics.
   Cards must not be presented as a random sample of the literature.
2. **Referees are sometimes wrong.** A stated error is evidence, not proof;
   this is precisely why `human_severity_label` exists.
3. **Selection bias toward localizable errors.** Requiring a cited location
   favors equation-level mistakes over structural or conceptual ones. This
   should be recorded as a property of the dataset.
4. **Report text may change.** SciPost reports are versioned documents;
   `text_hash` detects drift.
5. **Yield is measured on a sample, not the full corpus.** The funnel below
   derives from 1,000 of 8,846 submissions. The first full enumeration settles
   the true number.
