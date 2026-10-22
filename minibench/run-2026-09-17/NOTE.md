# What this run was scored against

The 12 manuscripts given to the agents were split straight out of
`minibench/papers.txt` as it stood on 2026-09-17, one body per file, with no
further cleaning.

`papers.txt` has since been rebuilt (2026-09-23) to close an anonymisation
hole: author e-mail addresses survived in two papers, and one of those also
kept a hand-typeset block of author names and affiliations. **Papers 6 and 12
of this run therefore carried their authors' identities**, which a model with
web access could have used to find the paper and its public referee report.

Three reasons this does not change the result:

- The prompt forbade web search and forbade reading any other file, and no
  report showed signs of having seen the referee's finding.
- Both affected papers were scored MISS. Neither contributed to the match
  count.
- The physics is untouched. The rebuild removed 1,874 characters across the
  whole file, all of it front matter; every paper still carries its numbered
  equations, and `answers.jsonl` is byte-identical.

A re-run against the current `papers.txt` is not byte-comparable with this
one for papers 6 and 12. Every other paper is unchanged.
