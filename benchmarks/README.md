# Manglish Complaint Embedding Benchmark

This is a deliberately small, hand-authored smoke test for the first CivicPulse-lite assumption: whether a multilingual embedding model separates semantically related Malaysian civic complaints from confusingly similar but unrelated ones.

It contains 30 text pairs plus typed incident metadata in `incident_pair_metadata.json`:

- 15 direct or code-switched positive pairs;
- 13 semantic hard negatives (same category or landmark, but a different problem/location);
- 2 time-window cases that are semantic matches but must not be merged into one incident.

Run it with:

```powershell
uv sync --frozen
uv run python scripts/run_embedding_benchmark.py
```

The runner uses `intfloat/multilingual-e5-small`, prints similarity distributions, and recommends a conservative semantic threshold that prioritizes avoiding false merges. Review the five weakest matches and five strongest non-matches before choosing a prototype threshold.

This benchmark evaluates text similarity only. Geographic radius and time-window checks are separate hard constraints in the incident-matching pipeline.
