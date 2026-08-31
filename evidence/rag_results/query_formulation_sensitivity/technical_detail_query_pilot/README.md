# Technical-detail query formulation sensitivity pilot

This is a retrieval-component offline evaluation. It does not call an LLM and
does not evaluate fault diagnosis. The query set in `query_set.json` contains
expert-authored technical-detail queries informed by phenomena documented in the
two representative condition reports:

- repeated spike episodes;
- zero-value dropout across multiple channels;
- highly synchronized channel groups with no detected lagged propagation chain.

The benchmark compares those six bilingual queries with the four fixed baseline
queries used by the independent embedding benchmark. It reuses the saved 240-word,
24-word-overlap corpus embeddings for the same 64-document collection (13 IAEA
core documents plus 51 supplementary documents). For each corpus-expansion size,
ten seeded supplementary-document draws are evaluated except at the core-only
baseline, which has one deterministic run.

Outputs are stored per encoder under `results/`. `scope_detail.csv` holds every
query--scope--trial result and `scope_summary.csv` holds means and standard
deviations. These results are exploratory: the technical-detail wording was
manually specified, informed by two representative cases, and is not an expert
relevance-labelled benchmark or an automatic query-generation experiment.
