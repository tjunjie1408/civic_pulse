<div align="center">

# CivicPulse

### From scattered civic complaints to explainable incident intelligence.

A local-first civic incident intelligence prototype that can run offline after its dependencies and embedding model are prewarmed.

**Python 3.12** · **FastAPI** · **SQLite** · **Streamlit** · **Strict Pydantic contracts**

</div>

> **Demo status** — Phase 9 is complete. The core MVP now includes composed runtime startup,
> offline/fault/recovery validation, measured performance budgets, and versioned reference
> evidence. It is frozen for demo and release rehearsal.

## Why CivicPulse?

Municipal teams rarely receive one clean report per incident. They receive overlapping messages in different languages, with inconsistent spelling, approximate locations, and different descriptions of the same problem.

CivicPulse turns that stream into an operational view:

```text
Submit complaint
→ normalize and compare evidence
→ auto_match / review_required / no_match
→ confirmed / isolated / conflict incident state
→ officer resolution when needed
→ incident snapshot and priority refresh
```

The important product decision is what CivicPulse refuses to pretend it knows:

| Layer | States | Operational meaning |
| --- | --- | --- |
| Relationship decision | `auto_match`, `review_required`, `no_match` | Pair-level matcher or officer outcome |
| Incident status | `confirmed`, `isolated`, `conflict` | Graph-level operational state |
| Operational priority | `low`, `medium`, `high`, `critical`, or unavailable | Policy output from confirmed evidence only |

Conflict incidents deliberately return `priority: null`; this is an explicit safety outcome, not missing computation. This keeps a likely duplicate from silently becoming a confirmed public-service incident.

## What the demo shows

The Dashboard presents a compact, synthetic municipal district modelled on urban patterns around Shah Alam, Selangor. It is deliberately not real municipal data.

### The synthetic district

The deterministic seed contains **120 complaints** arranged across five zones:

| Zone | Story in the demo |
| --- | --- |
| **Taman Seri Murni** | Residential rubbish, street-light, flooding, and pothole reports |
| **Seksyen Harmoni** | School-access drainage, pothole, street-light, and flooding reports |
| **Kawasan Perindustrian Maju** | Industrial-road damage, rubbish, lighting, and drainage reports |
| **Pusat Komersial Sentosa** | Commercial rubbish, pothole, drainage, and lighting reports |
| **Kampung Sungai Damai** | Low-lying-road flooding and downstream drainage reports |

The seed includes a small spatial narrative: an upstream drain problem near a school-access area and flooding on a downstream low-lying road. That structure gives the map a coherent civic story without pretending to be an official dataset. It is demonstration context, not a generated causal prediction.

> **Synthetic data notice** — All complaints, coordinates, zone names, and incident outcomes shown by this prototype are synthetic. The spatial layout is inspired by common Klang Valley urban patterns and must not be interpreted as live Shah Alam complaints.

### Dashboard workflow

1. **Operational queue** — Read API-ranked incidents with confirmed and pending counts kept separate.
2. **Incident detail** — Inspect complaint membership, accepted edges, candidate relationships, priority reasons, and conflict reasons.
3. **Hotspot map** — See confirmed incident centroids; pending candidates do not inflate hotspot intensity.
4. **Complaint submission** — Submit a new report through the API with a stable `Idempotency-Key` across Streamlit reruns.
5. **Review queue** — Read original matcher evidence, then approve or reject through the persistent review service.
6. **Safe demo reset** — Restore the server-configured seed only when the API feature flag and Dashboard setting are both enabled and the operator types `RESET DEMO`.

## Architecture

```mermaid
flowchart TB
    U["Officer / demo user"] --> S["Streamlit Dashboard"]
    S --> G["Typed HTTP gateway"]
    G --> A["FastAPI v1 API"]

    subgraph READ["Read path"]
        Q["IncidentQueryService"] --> R[("SQLite read model")]
    end

    subgraph WRITE["Mutation path"]
        M["Application mutation service"] --> X["Matching / clustering / priority"]
        X --> R
    end

    A --> Q
    A --> M
```

The architecture is intentionally split into two narrow paths: read endpoints query a read model, while mutations go through application orchestration before recalculating graph and priority state.

The Dashboard is an API client, not a second backend:

- routes validate, map, and translate errors;
- application services own mutation orchestration and transaction boundaries;
- read endpoints use `IncidentQueryService` to isolate the read model;
- sorting, matching, clustering, and priority rules stay server-owned;
- Streamlit does not import repositories, SQLite, backend services, or domain models;
- incident IDs are membership-derived **snapshot IDs**, not permanent case IDs.

## API surface

The API contract is versioned under `/api/v1` and protected by a deterministic OpenAPI snapshot at [`tests/contracts/openapi-v1.json`](tests/contracts/openapi-v1.json).

| Area | Endpoints |
| --- | --- |
| Health | `GET /api/v1/health/live`, `GET /api/v1/health/ready` |
| Incidents | `GET /api/v1/incidents`, `GET /api/v1/incidents/{incident_id}` |
| Complaints | `POST /api/v1/complaints` with required `Idempotency-Key` |
| Reviews | `GET /api/v1/reviews`, `GET /api/v1/reviews/{review_id}` |
| Review actions | `POST /api/v1/reviews/{review_id}/approve`, `POST /api/v1/reviews/{review_id}/reject` |
| Demo administration | `POST /api/v1/admin/reset`, disabled by default and bodyless |

Mutation responses expose previous and new snapshot IDs so clients can refresh without guessing which incident changed.

## Development setup

The repository contains both an injection-only FastAPI boundary for contract tests and a production composition entrypoint for the local demo. The server owns the repository, policies, seed, sensitive-location fixture, and embedding provider; the Dashboard remains an HTTP client.

### Vue frontend setup

The Slice 1 operations shell is a separate Vite application in `frontend/`. It requires Node `>=22.12.0` and pnpm `11.9.0` (the versions are also pinned by `frontend/package.json`). From the repository root, install the locked frontend dependencies with:

```powershell
pnpm --dir frontend install --frozen-lockfile
```

Start the API in one terminal, then start the Vite development server in another:

```powershell
uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000
pnpm --dir frontend run dev -- --host 127.0.0.1
```

Vite proxies `/api` to the API at `http://127.0.0.1:8000`; the frontend therefore remains an HTTP client and does not recreate server-owned ordering, matching, clustering, or priority logic.

### 1. Install dependencies

PowerShell:

```powershell
# First-time setup; requires network access if the uv cache is empty
uv sync

# Subsequent cached setup; fully offline
uv sync --offline
```

The project targets Python `>=3.12,<3.13`.

### 2. Prewarm the local embedding model

```powershell
# First prewarm; requires network access if the model is not cached
uv run python -m scripts.prewarm_model

# Subsequent cached readiness check; fully offline
uv run --offline python -m scripts.prewarm_model
```

Use a different policy file only when intentionally changing the configured contract:

```powershell
uv run --offline python -m scripts.prewarm_model --policy config/matching_policy.json
```

The readiness probe uses the fixed sentence `CivicPulse offline model readiness check` and the model configured in `config/matching_policy.json`. Production/demo runtime uses `local_files_only=True`; a missing cache fails fast and never triggers an implicit download. The first cached-model initialization on the Windows reference machine can take 20+ seconds; prewarm and start the API before a live demo. Subsequent readiness checks reuse the verified model state and are fast. See the [offline, fault, and recovery runbook](docs/demo-runbook.md) for recovery commands and stable error codes.

### 3. Start the composed API and Dashboard

Use two terminals after the embedding model has been prewarmed.

Terminal 1 — composed API, SQLite, policies, seed, and cached embedding model:

```powershell
uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000
```

Terminal 2 — Dashboard HTTP client:

```powershell
uv run --offline streamlit run src/civicpulse_dashboard/app.py
```

The Dashboard reads the API base URL from `CIVICPULSE_API_URL`; the default is:

```text
http://127.0.0.1:8000/api/v1
```

For example:

```powershell
$env:CIVICPULSE_API_URL = "http://127.0.0.1:8000/api/v1"
uv run --offline streamlit run src/civicpulse_dashboard/app.py
```

On first start, an empty database is initialized from `data/seed_complaints.json`. A non-empty database is preserved across restarts. Reset remains disabled unless `CIVICPULSE_ADMIN_RESET_ENABLED=true`; database, seed, and sensitive-location paths (`CIVICPULSE_DB_PATH`, `CIVICPULSE_SEED_PATH`, and `CIVICPULSE_SENSITIVE_LOCATIONS_PATH`) are server-side configuration and are never supplied by API requests.

The example Manglish report is intentionally `review_required` when automatic evidence is insufficient. It becomes confirmed incident membership only after an officer approves the candidate relationship in the review queue. Runtime cache, SQLite fault, reset rollback, restart, and Dashboard recovery behavior are documented in [`docs/demo-runbook.md`](docs/demo-runbook.md).

## Deterministic demo data

The checked-in seed is generated from typed Python data:

```powershell
uv run --offline python scripts/generate_seed_fixture.py
```

The manifest records:

- seed version: `shah-alam-demo-v1`;
- 120 complaints;
- normalization version: `normalization-v1`;
- embedding model: `intfloat/multilingual-e5-small`;
- embedding dimension: `384`;
- matching policy: `matching-v1`;
- priority policy: `priority-v1`;
- deterministic content checksum.

Reset is server-configured and disabled by default. The client never supplies a seed path or URL.

## Verification

Run the project-standard checks from the repository root:

```powershell
uv run --offline python -m pytest -q
uv run --offline pyright src scripts
uv run --offline ruff check src/civicpulse_dashboard
uv run --offline python -m scripts.run_hybrid_benchmark
git diff --check
```

For the Vue frontend release gates, run the commands below after the frozen dependency install. Each gate is intentionally listed so failures remain attributable; `check` runs the combined API contract, lint, behavior-test, and production-build gates.

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend run api:check
pnpm --dir frontend run lint
pnpm --dir frontend run typecheck
pnpm --dir frontend run test
pnpm --dir frontend run build
pnpm --dir frontend run check
```

The frontend scope audit also checks for prohibited dependencies, queue sorting, and placeholder copy:

```powershell
rg -n "pinia|@tanstack|maplibre|vue-router|axios|zod|\.sort\(" frontend/src frontend/package.json
rg -n "TODO|TBD|placeholder|lorem|coming soon" frontend/src
```

The affected backend contract gates are:

```powershell
uv run --offline python -m pytest tests/contract/test_incident_read_api.py tests/contract/test_openapi_freeze.py tests/contract/test_dashboard_gateway.py tests/contract/test_dashboard_recovery.py -q
```

The isolated Windows worktree has one approved, environment-only baseline deviation: `tests/unit/test_benchmark_schema.py::test_benchmark_manifest_matches_fixture_bytes` fails because `core.autocrlf=true` checks out the frozen fixture as CRLF. The manifest hash (`4b0136286710195e696216d209002eb9749b5f55e5fd32f45e09e73f438c8028`) and actual worktree hash (`bec7464dadd3c606efe87adc82b9fee2b8aa4399d6c7fddf33ef7e887ad65a60`) are recorded in `.superpowers/sdd/baseline.md`; do not alter the fixture, manifest, or Git configuration to hide it. Release reports must preserve the differential statement: `Known baseline failure: 1` and `New failures introduced by Slice 1: 0`.

The verified Phase 9 evidence is:

- non-performance tests: `247 passed`;
- performance contracts: `19 passed`;
- Pyright: `0 errors`;
- hybrid benchmark: **PASS**, with `0` holdout false merges;
- active performance hard gates: **PASS**;
- known non-blocking warning: the installed FastAPI/Starlette test stack reports an httpx deprecation warning.

Reference evidence and recovery guidance:

- [performance summary](docs/performance-report.md);
- [raw performance samples and gate results](benchmarks/reports/performance-budget.json);
- [offline demo and recovery runbook](docs/demo-runbook.md).

The OpenAPI freeze tests compare a canonical generated snapshot and never update it automatically. Contract changes require an explicit snapshot update and review.

## Repository map

```text
src/civicpulse/
├── api/                 FastAPI app factory, DTOs, routes, and error mapping
├── config.py            Versioned policy loading
├── demo_seed.py         Deterministic synthetic Shah Alam-inspired geography
├── embeddings.py        Offline embedding provider boundary
├── matching.py          Explainable text and hard-constraint matching
├── clustering.py        Incident graph construction and conflict handling
├── priority.py          Transparent operational priority policy
├── repository.py        SQLite persistence and atomic replacement
└── service.py           Application orchestration and mutation boundaries

src/civicpulse_dashboard/
├── api_client.py        Typed HTTP gateway
├── api_models.py        Strict UI-facing API models
├── state.py             UI-only session state and snapshot transitions
├── app.py               Streamlit entrypoint
└── ui/                  Queue, detail, map, submission, review, and reset views

tests/
├── unit/                Pure domain, seed, state, and policy tests
├── integration/         SQLite, service, health, and benchmark tests
├── contract/            API, Dashboard gateway, OpenAPI, and mutation contracts
└── contracts/           Frozen OpenAPI v1 snapshot and metadata
```

## Current boundaries and limitations

- Demo complaints and locations are synthetic; no live municipal feed is included.
- The embedding model must be cached before a fully offline run can succeed.
- The application is a single-process, local prototype; no authentication framework is included yet.
- Admin reset is protected by a feature flag and should remain unreachable in an untrusted deployment.
- Priority is a transparent prototype policy, not causal discovery or a flood prediction model.
- Photo analysis and SCM-inspired risk propagation are intentionally outside the current core workflow.
- This repository currently has no declared `LICENSE` file; reuse terms should be clarified before public redistribution.
- Repository-wide pre-commit is not currently green. Task-scoped tests, Pyright, benchmark,
  performance contracts, and diff checks pass, but repository-wide Ruff/Pyright/pytest-hook
  baseline debt remains to be handled in a separate hygiene phase.

## Roadmap

Phase 9 is complete and closes the reliability and performance work for the core MVP:

1. **Task 9.1 complete:** full composed demo regression;
2. **Task 9.2 complete:** offline, fault, and recovery validation;
3. **Task 9.3 complete:** measured performance budgets and versioned reference evidence.

**Core MVP status: demo-ready and frozen for rehearsal.** Phase 10 is optional enrichment,
not the default next step. Repository quality-debt cleanup should precede any optional photo
or spatial risk-propagation expansion.

### Performance budget measurement

Task 9.3 keeps correctness tests separate from wall-clock performance evidence. Its startup budgets intentionally separate application composition, warm readiness, and one-time cached-model initialization; the old single eight-second readiness budget mixed these costs and is retired. Run the opt-in cached-model harness explicitly:

```powershell
$env:HF_HUB_OFFLINE = "1"
uv run --offline python -m scripts.run_performance_budget --offline --warmups 3 --runs 20 --startup-runs 5 --reset-runs 5 --dashboard-runs 5
```

The harness records environment metadata, raw samples, p50/p95/max summaries, API-process RSS, and hard-gate results. Ordinary correctness runs exclude the `performance` marker; run those measurements separately with `uv run --offline python -m pytest -m performance tests/performance -q`. Cold-start/download and Windows filesystem variance are informational, not production SLA claims. The concise reference report is [docs/performance-report.md](docs/performance-report.md); its raw JSON source is `benchmarks/reports/performance-budget.json`.

## Project status

Built as a focused Hackathon prototype with a deliberately conservative matching boundary: explainability and safe uncertainty handling take priority over aggressive automatic merging.
