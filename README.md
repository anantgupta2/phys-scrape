# phys-scrape
For any new agent, you may change the methodology but your goal should be to extract errors in physics papers. This repository focuses on using arxiv diff versions and open peer review to find such papers. We want the errors to be human verified and agent scraped. Having them agent curated would induce a bias.
We have only tried directly scraping since that was the hardest one, please look at these datasets as well for possible venues.

| Dataset | Primary Domains | Size / Content | Key Strengths |
|---|---|---|---|
| ORB Dataset (CERN/GitLab) | Physics (SciPost) & AI/ML (OpenReview) | >36k papers, >89k reviews | Direct coverage of formal physics literature paired with parsed review text. |
| MOPRD (Multidisciplinary Open Peer Review Dataset) | Multi-domain (F1000Research, PeerJ, Nature, BMJ) | Multi-round reviews, decisions, revisions | Contains genuine referee discussions across experimental and physical domains. |
| PeerRead (AllenAI) | CS/ML (ICLR, NeurIPS, ACL) + arXiv drafts | ~14.7k papers, ~10.7k reviews | Standard NLP baseline corpus; available directly on Hugging Face (`allenai/peer_read`). |
| AIBS Open Peer Review Repository | Scientific & Grant Review Panels | 16 compiled datasets | Useful for analyzing inter-reviewer scoring calibration and criterion weighting. |

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
