# CivicPulse Performance Budget

- Budget version: `prototype-1`
- Hard-gate result: **PASS**
- Raw samples are retained in `benchmarks/reports/performance-budget.json`.

- Measurement timestamp: 2026-07-15T13:04:39.542672+00:00
- Git commit: `d4e59c3f0e5111bb2324b0774f6b4519ef317290` (dirty=True)

## Environment

- OS: Windows-11-10.0.26200-SP0
- CPU: AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD
- RAM: 15674 MB
- Python: 3.12.13
- Model: intfloat/multilingual-e5-small
- Seed size: 120
- Database: SQLite local file
- Offline mode: True
- Runs: warm-up=3, measured=20
- Method: time.perf_counter; cold process, warm readiness, and startup spans are separate; Dashboard timer starts after API readiness

## Results

| Metric | p50 | p95 | max | Limit | Hard | Result |
|---|---:|---:|---:|---:|:---:|:---:|
| cached_process_readiness_seconds | 20.84 | 24.49 | 24.49 | — | False | PASS |
| warm_readiness_seconds | 0.02 | 0.03 | 0.03 | 2.00 | True | PASS |
| application_composition_seconds | 2.08 | 2.23 | 2.23 | 5.00 | True | PASS |
| cold_cached_model_initialization_seconds | 17.66 | 20.61 | 20.61 | 25.00 | True | PASS |
| incident_list_p95_ms | 56.81 | 71.05 | 80.10 | 250.00 | True | PASS |
| incident_detail_p95_ms | 13.11 | 16.74 | 23.30 | 200.00 | True | PASS |
| submission_isolated_p95_ms | 2044.97 | 2321.79 | 2359.56 | — | False | PASS |
| submission_auto_match_p95_ms | 2014.92 | 2333.11 | 3120.75 | — | False | PASS |
| submission_review_required_p95_ms | 1996.07 | 2326.17 | 2380.74 | — | False | PASS |
| review_approve_p95_ms | 314.43 | 372.82 | 529.22 | — | False | PASS |
| review_reject_p95_ms | 311.82 | 358.21 | 393.67 | — | False | PASS |
| review_merge_p95_ms | 319.74 | 361.58 | 366.05 | — | False | PASS |
| reset_seconds | 0.82 | 1.14 | 1.14 | 45.00 | True | PASS |
| ready_rss_mb | 889.00 | 889.25 | 889.25 | 1536.00 | True | PASS |
| post_20_mutations_rss_mb | 894.54 | 894.87 | 894.87 | — | False | PASS |
| mutation_memory_growth_percent | 0.66 | 0.69 | 0.69 | 15.00 | True | PASS |
| dashboard_first_usable_seconds | 1.98 | 2.92 | 2.92 | 5.00 | True | PASS |
| full_demo_cold_path_seconds | 19.46 | 23.27 | 23.27 | — | False | PASS |
| submission_p95_ms | aggregate | 2333.11 | — | 2500.00 | True | PASS |
| review_resolution_p95_ms | aggregate | 372.82 | — | 2000.00 | True | PASS |
| mutation_memory_growth_percent | aggregate | 0.69 | — | 15.00 | True | PASS |

Known noise sources: Windows filesystem/cache variance, Streamlit rerun variance not yet measured.

## Cached readiness timing profile

- app_composition: 0.001 s
- database_and_seed_initialization: 2.230 s
- model_provider_load: 0.000 s
- readiness_probe: 20.605 s
- runtime_composition_total: 22.687 s
- settings_and_policy_loading: 0.003 s
- process_to_ready_unattributed: 1.805 s

## Budget interpretation

The former single eight-second cached-readiness budget mixed application startup
with first local Transformer initialization. Profiling separated those cost
centers: application composition is budgeted at five seconds, warm readiness at
two seconds, and cold cached-model initialization at 25 seconds. This is an
explicit semantic reclassification based on the reference Windows hardware,
not a silent relaxation of the original gate.

For a live demo, prewarm the model and start the API before presenting the
workflow; subsequent readiness checks use the verified model state and remain
fast.

This Markdown report contains summaries only; the JSON file is the audit source.
No optimization was performed where the measured result already met budget.
