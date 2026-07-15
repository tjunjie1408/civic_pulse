# CivicPulse Performance Budget

- Budget version: `prototype-1`
- Hard-gate result: **FAIL**
- Raw samples are retained in `benchmarks/reports/performance-budget.json`.

- Measurement timestamp: 2026-07-14T16:19:07.935685+00:00
- Git commit: `24fbaa1d2f3634aaefbd000c93e0c176665e6d52` (dirty=True)

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
- Method: time.perf_counter with API readiness, Streamlit root response, and AppTest marker

## Results

| Metric | p50 | p95 | max | Limit | Hard | Result |
|---|---:|---:|---:|---:|:---:|:---:|
| cached_process_readiness_seconds | 11.56 | 11.87 | 11.87 | 8.00 | True | FAIL |
| incident_list_p95_ms | 26.01 | 196.69 | 197.63 | 250.00 | True | PASS |
| incident_detail_p95_ms | 7.87 | 12.04 | 185.46 | 200.00 | True | PASS |
| submission_isolated_p95_ms | 1221.22 | 1402.00 | 1432.93 | — | False | PASS |
| submission_auto_match_p95_ms | 1176.38 | 1370.05 | 1370.47 | — | False | PASS |
| submission_review_required_p95_ms | 1184.73 | 1314.38 | 1362.22 | — | False | PASS |
| review_approve_p95_ms | 135.72 | 184.51 | 427.45 | — | False | PASS |
| review_reject_p95_ms | 136.07 | 173.34 | 176.81 | — | False | PASS |
| review_merge_p95_ms | 136.48 | 171.39 | 171.91 | — | False | PASS |
| reset_seconds | 0.35 | 0.53 | 0.53 | 45.00 | True | PASS |
| ready_rss_mb | 891.07 | 892.18 | 892.18 | 1536.00 | True | PASS |
| post_20_mutations_rss_mb | 897.32 | 898.20 | 898.20 | — | False | PASS |
| mutation_memory_growth_percent | 0.67 | 0.70 | 0.70 | 15.00 | True | PASS |
| dashboard_first_usable_seconds | 13.19 | 14.80 | 14.80 | 5.00 | True | FAIL |
| submission_p95_ms | aggregate | 1402.00 | — | 2500.00 | True | PASS |
| review_resolution_p95_ms | aggregate | 184.51 | — | 2000.00 | True | PASS |
| mutation_memory_growth_percent | aggregate | 0.70 | — | 15.00 | True | PASS |

Known noise sources: Windows filesystem/cache variance, Streamlit rerun variance not yet measured.

## Budget breaches and decisions

- Cached process readiness p95 is 11.87 s against the 8 s prototype gate. This remains a stable model-import/composition breach on the reference Windows environment; no optimization was applied in Task 9.3.
- Dashboard first usable p95 is 14.80 s against the 5 s prototype gate. The measurement includes API readiness, Streamlit root response, and the operational marker; no threshold was silently widened.
- All read, mutation, reset, API RSS, and 20-mutation growth gates pass on the same warm-up-inclusive reference run.

This Markdown report contains summaries only; the JSON file is the audit source.
No optimization was performed where the measured result already met budget.
