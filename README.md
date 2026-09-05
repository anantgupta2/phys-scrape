# phys-scrape
For any new agent, you may change the methodology but your goal should be to extract errors in physics papers. This repository focuses on using arxiv diff versions and open peer review to find such papers.

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
