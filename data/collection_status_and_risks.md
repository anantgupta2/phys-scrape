# Collection status, review-first evidence plan, and risks

Last audited: 2026-09-05.

## Current inventory

| Item | Count | Meaning |
| --- | ---: | --- |
| Raw target-category manifest | 690 | Papers returned by the balanced hep-th / quant-ph / gr-qc category pool, including cross-lists. |
| Strict-primary manifest | 592 | Primary category is exactly hep-th (159), quant-ph (252), or gr-qc (181). This is the current working pool. |
| Manual audit papers | 15 distinct | Three initial papers plus twelve reviewed/revision-signalled follow-ups. |
| Verified strong positive seed | 1 | `2506.24112`, a corrected query-complexity upper bound. |
| Excluded for no v1/v2 pair | 3 | `2503.22805`, `2603.24168`, `2608.17837`. |
| Invalid source response | 1 | `2408.15202`; re-fetch required. |
| Potential substantive lead, not ground truth | 1 | `2604.20165`; its island no-go argument changes assumptions and proof structure. |

`candidates_primary.jsonl` is an **in-scope discovery pool**, not an error-labeled
dataset. The currently saved pool was built from category sampling; the larger
keyword-enrichment pass was rate-limited and must be rerun safely before it is
used as an error-candidate population.

## What the manual checks established

### Positive seed: `2506.24112`

The author comment states that v2 corrected an upper bound, and the source pair
confirms a compact, coherent claim-level correction:

- abstract: `O(d^2/delta)` becomes `O(d^3/delta)`;
- theorem and proof propagate the added factor of `d`;
- subsequent complexity claims and conclusion are updated consistently.

This is suitable for a card after an expert validates the mathematics. It has a
natural first flawed claim and a mechanistic explanation (the second-order
simulation error carries an extra dimension factor).

### Controls and exclusions

- Metadata such as “typos corrected” is not a severity label. `2605.27754`
  and `2604.25569` looked compact to a generic diff heuristic but were ordinary
  prose/reference or explanatory changes on inspection.
- `2605.29990` advertises corrected equations but has an approximately 1,000
  line TeX diff; it cannot be localized from the comment alone.
- A comment saying “modified results” does not guarantee a usable pair:
  `2503.22805` has only v1.
- `2604.20165` is the best follow-up lead, not a label: the revision changes
  the universal-island condition and replaces definitions with a lightsheet
  lemma. An expert must decide whether this fixes a fatal premise, narrows a
  theorem, or merely improves exposition.

The detailed per-paper log is in `manual_review_notes.md`; source-pair routing
output is in `reviewed_audit_triage.jsonl`.

## Preferred evidence hierarchy: review first

Use public SciPost submission material as the evidence source wherever it
exists. SciPost's workflow supports public referee reports, author replies,
and author comments on resubmission; replies can state planned changes and
resubmission comments can list what changed. See the
[SciPost refereeing guidance](https://scipost.org/SciPostChemRev/refereeing)
and a representative
[public submission page](https://scipost.org/submissions/scipost_202010_00006v2/).

For each candidate, collect this provenance bundle before reading the LaTeX in
depth:

```json
{
  "arxiv_id": "2506.24112",
  "scipost_submission_url": null,
  "match_status": "unmatched | matched_title_author | matched_arxiv_id",
  "reports": [{"url": null, "posted_at": null, "text_hash": null}],
  "author_replies": [{"url": null, "posted_at": null, "text_hash": null}],
  "resubmission_comments": [{"url": null, "text_hash": null}],
  "editorial_decision": null,
  "evidence_class": "none | presentation | technical | fatal_candidate",
  "human_severity_label": "unreviewed"
}
```

Promotion rule: create a fatal-flaw card only when a public report identifies a
specific technical issue **and** an author response/resubmission explicitly
addresses it, with a v1/v2 change that can be localized. Report-only critiques
and author-only assertions stay `unreviewed`. This sharply reduces physics work
while preserving a defensible causal chain: challenge -> response -> source
change.

## Required separation to avoid evaluation leakage

The model-facing prompt may contain only the pre-correction manuscript excerpt
and allowed contextual definitions. Referee reports, author responses, later
versions, labels, and diff markup are gold-side evidence only. Store their
URLs, hashes, and quoted locations in an annotation file that is never served
to the evaluated model. Public availability does not make this leakage benign.

## Known implementation and data risks

1. **Discovery is not error discovery.** Category membership and revision count
   have low precision; author comments are useful routing signals only.
2. **Version mismatch.** An arXiv v1/v2 pair need not align with a SciPost
   submission/resubmission round. Record both dates and never assume alignment.
3. **Missing public evidence is selection bias.** SciPost coverage is not
   representative of hep-th, quant-ph, or gr-qc. Maintain a separate
   `no_public_review` stratum rather than silently discarding it.
4. **Identity matching can be wrong.** Prefer an exact arXiv identifier; if
   absent, require normalized title plus author overlap and mark it
   `matched_title_author`, not exact.
5. **Bot protection / retrieval reproducibility.** Direct scripted retrieval
   of a SciPost submission page returned a bot-interstitial in this environment.
   Retain original submission/report/attachment URLs and retrieval timestamps;
   use an authorized browser-mediated or index-mediated acquisition route.
6. **Source download validity.** HTTP 200 is insufficient: `2408.15202`
   produced a non-tar response. Validate archives before recording a pair as
   downloaded; the collector now marks `invalid_archive`.
7. **TeX filename and formatting churn.** Main files may be renamed and
   publisher formatting can dominate raw diffs. The current auditor chooses the
   largest TeX file, which is a triage heuristic, not a canonical latexdiff
   resolver.
8. **Severity ambiguity.** “Corrected,” “revised,” “misprint,” and a referee
   request do not establish that a flaw is fatal. Keep `fatal_candidate` and
   `human_severity_label` distinct.
9. **Taxonomy leakage and hindsight.** Do not derive the target taxonomy from
   reviewer wording alone; independently annotate the mechanism from v1, then
   use the response only to verify ground truth.
10. **Copyright and retention.** Save snippets/locations/hashes by default;
    retain full public reports or attachments only where their license and the
    benchmark's access policy permit it.

## Next low-effort execution path

1. Build a SciPost match manifest for the 592 strict-primary IDs, recording
   exact match, ambiguous match, or no match.
2. For exact matches, ingest report/reply/resubmission URLs and their hashes.
3. Rank only exact matches with a technical report plus an explicit author
   change statement.
4. Download and diff source pairs only for that ranked subset.
5. Ask a physicist to adjudicate the small `fatal_candidate` queue; use the
   rest as calibrated negatives or exclude them.

## Implemented safeguards

- `collect_arxiv_candidates.py` now validates e-print downloads as tar archives,
  retries malformed responses with backoff, writes replacement archives
  atomically, and records a SHA-256 plus byte count for each accepted source.
- `audit_latex_pairs.py` now reads arXiv's `00README.json` and uses its
  `toplevel` TeX declaration before falling back to the largest-TeX heuristic.
- `build_review_evidence_queue.py` creates the review-first queue with explicit
  `queue_route`, match state, report/reply slots, and model-input exclusion
  policy. Source triage can override a stale download-success record.
- The recovery test for `2408.15202` still yields `invalid_archive`; it is now
  correctly retained as a retry item rather than treated as a source pair.
