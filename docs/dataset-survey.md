# Survey of the four README datasets

Date: 2026-09-08
Question: do ORB, MOPRD, PeerRead or AIBS contain theoretical physics papers
with referee-identified errors that the SciPost pipeline does not already have?

**Answer: two, and neither should be used.** Details and method below, so the
result can be checked rather than taken on faith.

## What a source has to provide

The SciPost pipeline needs four things from a record. Missing any one of them
means no card can be built:

1. **Referee text** stating what is wrong — the ground truth.
2. **A theoretical physics paper** — the target domain.
3. **A paper identifier resolving to arXiv**, so the manuscript source exists.
4. **A revision pair**, so the flawed claim can be localized and the authors'
   response confirms it.

A source failing (1) or (2) is out entirely. A source with both but failing
(3) or (4) could still support referee-quote-only records, but not cards.

## Results

| Source | Records examined | Theoretical physics with referee text | New candidates |
| --- | ---: | ---: | ---: |
| ORB — SciPost | 6,189 | 4,895 with reports, 99.1% already held | **2** |
| ORB — OpenReview | 18,842 venue strings | 0 | 0 |
| ORB — PeerJ | 33,276 | 0 | 0 |
| MOPRD | 6,578 | 0 | 0 |
| PeerRead | 12,325 | 0 | 0 |
| AIBS | 16 datasets | 0 accessible | 0 |

## ORB (Open Review-Based dataset)

[Zenodo 13628746](https://zenodo.org/records/13628746), CC-BY 4.0, snapshot
dated 2024-08-30. Three separate extracts: SciPost, OpenReview, PeerJ.

**SciPost portion** — 6,189 submissions, 4,895 with reports. This is the same
corpus the live API serves, frozen a year earlier:

    ORB ids                6,189
    live API ids           8,844
    overlap                6,134   (99.1% of ORB)
    in ORB only               55   (42 with reports)
    in live only           2,710   (submissions made since the snapshot)

The 55 ORB-only records are not a gap in our collection. Fetching them from
SciPost now redirects to `/login/`: they were public in 2024 and have since
been restricted or withdrawn. Our own enumeration is complete — 45 pages, no
offset gaps, 8,846 records matching the API's own reported count.

Running the full selection rules over those 42 leaves **2 candidates**
(`2302.11863v3`, hep-th; `2204.06567v3`, cond-mat theory), both in the weaker
`corrective_request` tier.

**Neither should be ingested.** The dataset's central claim is that every card
traces to a publicly verifiable referee report with a DOI. These two are now
behind a login and carry no report DOI, so including them would break exactly
the property that makes the dataset worth having — for a 0.4% increase in
candidates.

ORB's schema also lacks `is_resubmission_of` and report DOIs, so ingesting it
would mean reconstructing threads from version suffixes and accepting
un-citable evidence. That is real work for a negative return.

**OpenReview portion** — machine learning, not physics. All 18,842 distinct
venue strings are ICLR, NeurIPS, ICML and their workshops. The physics-adjacent
entries are ML-for-science workshops: `ICLR.cc/2023/Workshop/Physics4ML` (67
blind submissions), `AI4Science` across three years (~143), `ML4Materials`
(78). These are machine learning papers that apply physics, not physics papers,
and OpenReview submissions carry no arXiv version pair.

**PeerJ portion** — biology. Top areas are Ecology (3,400), Zoology (2,970),
Molecular Biology (2,850), Bioinformatics (2,697). Of 60,972 distinct keywords,
28 match a physics pattern, and they are computing and materials terms:
"Quantum dots" (3), "Post-quantum cryptography" (3), "Quantum computing" (2).

## MOPRD

[arXiv:2212.04972](https://arxiv.org/abs/2212.04972), Neural Computing and
Applications 35(34).

The README describes MOPRD as covering "F1000Research, PeerJ, Nature, BMJ".
**That is not correct.** MOPRD draws exclusively from PeerJ's seven journals:
Analytical Chemistry, Computer Science, Inorganic Chemistry, Life and
Environment, Materials Science, Organic Chemistry, Physical Chemistry. None is
a physics journal.

The authors' own discipline figure gives: Biology 46.7%, Medicine 19.7%,
Computer science 15.7%, Environment 8.9%, Others 4.6%, Chemistry 4.4%. There
is no physics category. Since ORB's PeerJ extract covers the same publisher
and shows the same picture at 33,276 records, this is corroborated
independently.

Distribution is via Baidu Pan with an extraction code, so it is not
scriptable; the URL printed in the paper
(`http://www.linjialiang.net/publications/moprd`) 404s over HTTPS and the
domain's certificate is issued to an unrelated host.

## PeerRead

[allenai/PeerRead](https://github.com/allenai/PeerRead), Kang et al. 2018.
12,325 records carrying a review file.

**Review text exists in only three sections, all of them ML or NLP venues:**

    acl_2017                    137 records,   137 with review text
    conll_2016                   22 records,    22 with review text
    iclr_2017                   427 records,   427 with review text
    arxiv.cs.ai_2007-2017     4,092 records,     0 with review text
    arxiv.cs.cl_2007-2017     2,638 records,     0 with review text
    arxiv.cs.lg_2007-2017     5,048 records,     0 with review text

The arXiv sections — the only part with arXiv identifiers, and therefore the
only part that could ever yield a source pair — carry `"reviews": []`. They
hold accept/reject labels for decision prediction, not referee text.

Across all 71 distinct arXiv subject tags, **35 records cross-list to a physics
category** (`physics.soc-ph`, `astro-ph.IM`, `astro-ph.EP`, `physics.data-an`,
`cond-mat.dis-nn`). All 35 are in the arXiv sections, so **all 35 have zero
review text**. None is theoretical physics regardless.

## AIBS

[SPARS open peer review data sets](https://www.aibs.org/spars/open-peer-review-data-sets.html).

This is a bibliography of peer-review-research datasets, not a corpus. Of the
16 entries, 14 contain grant application scores and reviewer metadata with no
review text and no papers. One of the remaining two *is* PeerRead.

The only novel entry is Severin et al. — 38,250 reports on 12,294 Swiss
National Science Foundation grant applications, of which 3,979 (10.4%) are
mathematics/physics. It fails on three counts: they are **grant applications,
not papers**; only **numeric scores** were analysed, not review text; and the
data is **not public** — "available to others on request for an approved
research project, after signing a data sharing agreement".

## Conclusion

The SciPost API remains the only source of theoretical physics papers with
public referee-identified errors and recoverable arXiv revision pairs. The
other three named datasets are out of domain — computer science, machine
learning, biology and grant review — and ORB's physics content is the same
SciPost corpus we already read, a year staler.

No code change is warranted. The work this survey saves is the reason to
record it.

### Method

    # ORB
    curl -L -o scipost.pickle    'https://zenodo.org/records/13628746/files/extract_results_SciPost_etl_agent.pickle?download=1'
    curl -L -o openreview.pickle 'https://zenodo.org/records/13628746/files/extract_results_OpenReview_etl_agent.pickle?download=1'
    curl -L -o peerj.pickle      'https://zenodo.org/records/13628746/files/extract_results_Peerj_etl_agent.pickle?download=1'

    # PeerRead
    git clone --depth 1 https://github.com/allenai/PeerRead.git

The SciPost and PeerJ pickles contain only builtin containers — verified with
`pickletools.genops`, zero `GLOBAL`/`STACK_GLOBAL` opcodes — so they are safe
to load. The OpenReview pickle carries one `STACK_GLOBAL` referencing the
`openreview` package; it was read statically through `pickletools` rather than
unpickled.

Physics filters applied: for SciPost, the `THEORY_SPECIALTIES` allowlist in
`scipost_mine.py`; for PeerRead, arXiv category prefixes (`hep-`, `gr-qc`,
`quant-ph`, `cond-mat`, `astro-ph`, `physics.`, `math-ph`, `nucl-`, `nlin.`);
for PeerJ and OpenReview, the source's own area, keyword and venue fields.
