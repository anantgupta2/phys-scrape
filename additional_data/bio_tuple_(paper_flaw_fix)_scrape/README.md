# eLife (paper, flaw, fix) triples, pre-2022-11-30, rules only

**171,022 triples from 12,318 eLife papers accepted before 2022-11-30.** Each triple pairs a
referee or editor point, quoted verbatim in the authors' response, with the authors' answer to it.
No model read or selected anything: segmentation uses the JATS XML structure and regular
expressions only, following phys-scrape's rule that ground truth must trace to a human referee's
own words.

Built 2026-10-27 from [elifesciences/elife-article-xml](https://github.com/elifesciences/elife-article-xml)
(newest version file of each of 19,640 articles). eLife content is CC BY 4.0; cite eLife and the
article DOI when redistributing.

## Files

| File | What it holds |
| --- | --- |
| `elife_triples.jsonl.gz` | One triple per line (171,022 lines) |
| `elife_papers.jsonl.gz` | One line per article file (19,640), with full metadata and why it was kept or skipped |
| `elife_triples_sample.csv` | 200 random triples for reading in a spreadsheet |
| `stats.json` | Counts by status, accepted year, quote style and review round |
| `extract_elife_triples.py` | The extractor |
| `make_sample_csv.py` | Builds the CSV sample |

## Counts

| Accepted year | Papers | Triples |
| --- | --- | --- |
| 2012 | 36 | 199 |
| 2013 | 219 | 1,472 |
| 2014 | 500 | 4,697 |
| 2015 | 850 | 9,489 |
| 2016 | 1,070 | 10,875 |
| 2017 | 1,302 | 15,467 |
| 2018 | 1,261 | 16,274 |
| 2019 | 1,491 | 18,927 |
| 2020 | 1,884 | 23,991 |
| 2021 | 1,991 | 34,197 |
| 2022 (to Nov 29) | 1,714 | 35,434 |

Of the 19,640 files, 5,694 lack a decision-letter-plus-response pair: 3,558 are papers under
eLife's 2023+ reviewed-preprint model (public reviews, not decision letters), 2,009 are
non-research items (Insights, corrections, reviews, editorials) and 127 are research papers
missing one of the two. Another 1,568 were accepted on or after 2022-11-30, 8 lack an accepted
date, and 52 have a response with no quoted points.
For comparison, Crossref lists 12,381 eLife articles with peer-review links published
2012-01-01 to 2022-11-30, so coverage is about 99.5%.

Top subjects by paper: Neuroscience 3,848; Cell Biology 2,271; Developmental Biology 1,470;
Structural Biology and Molecular Biophysics 1,307; Biochemistry and Chemical Biology 1,246.

## Schema

```json
{
  "triple_id": "elife-45403-003",
  "paper": {"elife_id": "45403", "doi": "10.7554/eLife.45403", "title": "...",
            "subjects": ["..."], "accepted": "2019-05-08"},
  "flaw": {
    "text": "3) The manuscript relies on a large number of figures ...",
    "section": "Essential revisions",          // "Reviewer #2 (Recommendations for the authors)", or null
    "reviewer": null,                          // "Reviewer #2", "Reviewing editor", or null
    "section_part": "Essential revisions",     // sub-heading, or null
    "point_number": 3,                         // from a leading "3)" / "3." / "3:", else null
    "review_round": 1,                         // 1 = response to the first review; 2+ after an "[Editors' note ...]"
    "in_decision_letter": true,                // flaw's first 80 letters found in the decision letter
    "source": "author_response_quote"
  },
  "fix": {
    "text": "We have broken up the original figures into 12 smaller ...",
    "reports_change": false,                   // regex: "we have added/revised/removed ...", "new figure", etc.
                                               // (a heuristic: "we have broken up" is not in the list)
    "source": "author_response_answer"
  },
  "provenance": {
    "quote_mode": "disp-quote",                // or "italic" (older files quote points in italics)
    "review_date_upper_bound": "2019-05-08",   // the accepted date
    "decision_letter_doi": "10.7554/eLife.45403.074",
    "author_response_doi": "10.7554/eLife.45403.075"
  }
}
```

## Method

1. Take the newest `elife-<id>-v<N>.xml` per article. Find the decision letter
   (`sub-article` type `decision-letter` or `article-commentary`) and the author response
   (`reply` or `author-comment`).
2. Keep the paper only if its `accepted` date is before 2022-11-30. The review sub-articles carry
   no date of their own, and the review always precedes acceptance, so this is a conservative
   bound on the report date.
3. Flatten the author response into paragraphs. A paragraph is a **quote** if it sits in a
   `<disp-quote>`, or, in files with no `<disp-quote>`, if at least 90% of its text is italic.
   A short paragraph matching a label pattern ("Essential revisions", "Reviewer #2
   (Recommendations for the authors)", "Major comments" …) sets the section. A paragraph starting
   "[Editors' note" closes the round.
4. Each run of quote paragraphs is one flaw; the non-quote paragraphs after it, up to the next
   quote, label or round boundary, are its fix. Text before the first quote is preamble and is
   dropped. Figures and tables inside answers become placeholders such as `[Author response image 1]`.
5. Drop points whose flaw is under 30 characters or that have no answer.

## Quality check

An independent reviewer compared 30 random triples with their source XML. Flaw boundaries were
right in 30/30 and fixes in 29/30. The errors found (section labels with a parenthetical,
labels in the middle of a quote, editors' notes leaking into the last answer of a round,
figure captions in answers, invisible characters breaking point numbers) were fixed in the
extractor before this release. 95.5% of flaws are found verbatim in the decision letter.

## Caveats

- **The fix is the authors' description of the change**, not a diff of the manuscript. 55.4% of
  answers match the `reports_change` pattern; the rest are rebuttals, clarifications or promises.
  Locating the change in the text needs the version the referees read, usually the bioRxiv
  preprint linked from Crossref's `has-preprint` relation (not fetched here).
- **The decision letter's "Essential revisions" are the editor's consolidated summary** of the
  referees. Points from the individual reviewers' sections are closer to the referees' own words.
  `flaw.section` and `flaw.reviewer` let you separate the two.
- A flaw can bundle several quoted paragraphs that the authors answered together, and can include a
  reviewer's summary or praise at the top of their section. Short or summary-like flaws are kept
  rather than guessed away; filter on `point_number`, `section` or length as needed.
- 16% of triples have no section label, mostly 2012–2015 papers whose responses use none.

## Rebuild

```bash
git clone --filter=blob:none --no-checkout --depth 1 https://github.com/elifesciences/elife-article-xml
# check out the newest version file of each article into xml/, then:
python3 extract_elife_triples.py xml/ out/ --cutoff 2022-11-30
python3 make_sample_csv.py out/elife_triples.jsonl out/elife_triples_sample.csv 200
```

Requires Python 3.10+ and `lxml`. The full run takes about 1.5 minutes.
