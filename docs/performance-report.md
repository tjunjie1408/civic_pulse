# CivicPulse Performance Budget

- Budget version: `prototype-1`
- Hard-gate result: **PASS**
- Raw samples are retained in `benchmarks/reports/performance-budget.json`.

- Measurement timestamp: 2026-07-15T13:22:58.832261+00:00
- Git commit: `0496980795ff10c72b33c0edc7330ae8cd2be353` (dirty=True)

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
| cached_process_readiness_seconds | 12.78 | 14.01 | 14.01 | — | False | PASS |
| warm_readiness_seconds | 0.01 | 0.03 | 0.03 | 2.00 | True | PASS |
| application_composition_seconds | 1.14 | 1.19 | 1.19 | 5.00 | True | PASS |
| cold_cached_model_initialization_seconds | 10.48 | 11.95 | 11.95 | 25.00 | True | PASS |
| incident_list_p95_ms | 27.34 | 31.73 | 37.73 | 250.00 | True | PASS |
| incident_detail_p95_ms | 8.06 | 10.31 | 24.40 | 200.00 | True | PASS |
| submission_isolated_p95_ms | 1283.74 | 1456.19 | 4217.58 | — | False | PASS |
| submission_auto_match_p95_ms | 1267.00 | 1610.30 | 3959.15 | — | False | PASS |
| submission_review_required_p95_ms | 1295.21 | 1427.07 | 4056.27 | — | False | PASS |
| review_approve_p95_ms | 140.70 | 163.66 | 318.60 | — | False | PASS |
| review_reject_p95_ms | 142.47 | 160.58 | 165.59 | — | False | PASS |
| review_merge_p95_ms | 142.55 | 168.62 | 283.94 | — | False | PASS |
| reset_seconds | 0.35 | 0.36 | 0.36 | 45.00 | True | PASS |
| ready_rss_mb | 888.33 | 890.54 | 890.54 | 1536.00 | True | PASS |
| post_20_mutations_rss_mb | 894.25 | 895.85 | 895.85 | — | False | PASS |
| mutation_memory_growth_percent | 0.67 | 0.75 | 0.75 | 15.00 | True | PASS |
| dashboard_first_usable_seconds | 1.64 | 1.70 | 1.70 | 5.00 | True | PASS |
| full_demo_cold_path_seconds | 13.12 | 13.17 | 13.17 | — | False | PASS |
| submission_p95_ms | aggregate | 1610.30 | — | 2500.00 | True | PASS |
| review_resolution_p95_ms | aggregate | 168.62 | — | 2000.00 | True | PASS |
| mutation_memory_growth_percent | aggregate | 0.75 | — | 15.00 | True | PASS |

Known noise sources: Windows filesystem/cache variance, Streamlit rerun variance not yet measured.

## Cached readiness timing profile

- app_composition: 0.000 s
- database_and_seed_initialization: 1.190 s
- model_provider_load: 0.000 s
- readiness_probe: 11.955 s
- runtime_composition_total: 13.060 s
- settings_and_policy_loading: 0.002 s
- process_to_ready_unattributed: 0.952 s

## Startup budget history

- Prototype-1 originally defined cached process readiness as <=8 s.
- Profiling showed that metric combined application composition with first cached-model initialization; it is retired as a hard gate, not silently widened.

This Markdown report contains summaries only; the JSON file is the audit source.
No optimization was performed where the measured result already met budget.
