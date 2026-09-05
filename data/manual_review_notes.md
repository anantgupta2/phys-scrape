# Manual collection audit

This is a small triage audit, not a gold annotation set.  It records what was
verified directly from the arXiv comment and v1/v2 source pair.

| arXiv ID | Review signal | v1/v2 status | Manual disposition |
| --- | --- | --- | --- |
| 2506.24112 | v3 is the published version | v2 explicitly corrects the upper bound; source diff changes the abstract, theorem, proof, and consequences from an `O(d^2/delta)` to an `O(d^3/delta)` upper bound | **Positive seed.** A compact, mechanistic, line-localizable quantitative error. First substantive changed claim: the abstract's upper-bound sentence (around line 108 of v1). |
| 2605.29990 | To be published in JHEP | Comment says typographical errors in figures/equations were corrected; v1/v2 TeX diff is roughly 500 added and 499 deleted lines | **Do not label from metadata.** This is useful as a hard negative/ambiguity control only after a human establishes whether a specific changed equation was consequential. |
| 2503.22805 | Published in JHEP; comment says modified results | The arXiv record reports only one version, so no v1/v2 pair is available | **Exclude from paired-revision benchmark.** Keep only as a possible external-review/erratum lead. |

Collection rule exposed by this audit: require `version_count >= 2` before a
record enters the latexdiff path, and require a human- or report-backed
severity label before treating an equation-correction comment as fatal.

## 12-paper reviewed follow-up

Source-pair triage is saved in `reviewed_audit_triage.jsonl`.

- **Exclude before diffing:** `2603.24168` and `2608.17837` have only v1.
- **Retry:** `2408.15202` advertises three versions, but one e-print response
  was not a tar archive. The collector now records this as `invalid_archive`.
- **Clear nonfatal controls:** `2511.16380` is a 14-line typo/exception-case
  update; `2605.27754` is grammar/reference cleanup; `2604.25569` adds a
  label and explanatory discussion. None should become a fatal-error card.
- **Broad revision / human review:** `2509.26583`, `2606.01486`, `2605.28670`,
  `2604.03003`, and `2604.00570` change 241--1786 TeX lines or explicitly say
  that the result is unchanged.
- **Potential substantive lead:** `2604.20165` changes the universal-island
  no-go argument's assumptions and replaces definitions with a lightsheet
  lemma. It merits expert severity review, but is not ground truth yet.
