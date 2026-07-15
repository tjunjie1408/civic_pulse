# Task 9.3A: Dashboard Boundary and Startup Profiling

## Objective

Correct the Dashboard first-usable measurement boundary and capture runtime startup
spans before making any performance optimization changes.

## Scope

1. Start the Dashboard timer only after `/api/v1/health/ready` returns successfully.
2. Preserve the full cold-demo path as an informational metric from API process start.
3. Record runtime spans for policy loading, model readiness, database/seed setup, app
   composition, and the uninstrumented process-to-ready remainder.
4. Re-run the unchanged performance budgets and use the resulting profile to choose
   one evidence-backed optimization, if a hard gate remains breached.

## Verification gate

- Dashboard-only p95 is compared with the five-second budget.
- Full-demo cold path is informational and is not substituted for the Dashboard gate.
- Startup profile is present in the JSON audit report and concise Markdown summary.
- No optimization is accepted without a before/after measurement from the same harness.
- Correctness tests, Pyright, changed-file Ruff, and the hybrid benchmark remain green.
