# CivicPulse offline, fault, and recovery runbook

This runbook is for the local production/demo composition. It keeps runtime behavior deterministic: the API and Dashboard use the local model cache only, while preparation and benchmark commands opt into downloads explicitly.

## Model preparation modes

The runtime provider is constructed with `local_files_only=True`. It never decides based on whether a network happens to be available.

### First preparation (explicitly online)

Run this only when the model is not already cached and network access is approved:

```powershell
uv run python -m scripts.prewarm_model
```

The command loads the configured model, runs the fixed readiness sentence, and validates the 384-dimensional seed contract before reporting `ready`.

### Offline cache validation

Use this at a venue or in CI when downloads are forbidden:

```powershell
uv run --offline python -m scripts.prewarm_model --offline
```

If the cache is missing or incomplete, the command fails quickly with `embedding_model_cache_missing` or `embedding_model_cache_invalid`. It does not fall back to a download. The error does not include a local cache path.

## Start and verify the composed runtime

Start the API only after offline prewarm succeeds:

```powershell
uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000
```

Check liveness and readiness from another terminal:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health/live
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health/ready
```

Readiness is healthy only when the database schema is readable, policies match, the model loads locally, the probe vector is non-empty and has the expected dimension, and the seed state is present. A non-empty database is preserved across API restarts.

Run the Dashboard as a separate HTTP client:

```powershell
uv run --offline streamlit run src/civicpulse_dashboard/app.py
```

If readiness returns `503 readiness_failure`, the Dashboard shows a safe not-ready message and does not render incident, map, submission, or review views. Once readiness succeeds on a later refresh, those views become available again. A timeout or connection error remains `api_unreachable`.

## Stable fault semantics

| Code | Meaning | Operator action |
| --- | --- | --- |
| `embedding_model_cache_missing` | Runtime/prewarm offline cannot find a usable model cache | Run the explicit online prewarm command, then rerun offline validation |
| `embedding_model_cache_invalid` | Model load or probe dimension is invalid | Re-prewarm the configured model; do not point runtime at an arbitrary cache path |
| `database_busy` | A bounded SQLite write timeout expired | Retry after the competing local process releases the lock |
| `database_corrupt` | SQLite rejected the file or schema | Stop the API, preserve the file for diagnosis, and restore a known-good database backup |
| `readiness_failure` | One or more core runtime dependencies are unavailable | Use the readiness component message and recovery command; do not serve operational traffic |

Public API errors are sanitized. They do not expose cache/database paths, SQL text, traceback text, or tokens.

## SQLite lock and corruption recovery

SQLite writes use a 250 ms busy timeout and rollback before `database_busy` is returned. A failed write leaves no complaint, embedding, submission key, incident, edge, or review row behind.

Do not delete or recreate a corrupt database automatically. Stop the API, copy the file to a safe diagnostic location, and restore the approved database artifact. Then restart the API and verify `/api/v1/health/ready` before reopening the Dashboard.

## Atomic reset and restart recovery

Reset is server-configured and disabled unless `CIVICPULSE_ADMIN_RESET_ENABLED=true`. The client cannot supply a seed path or URL.

```powershell
$env:CIVICPULSE_ADMIN_RESET_ENABLED = "true"
Invoke-WebRequest -Method Post http://127.0.0.1:8000/api/v1/admin/reset
```

Reset replacement is one transaction. If seed validation, model embedding, lock acquisition, or storage fails—including a failure after dataset delete—the transaction rolls back. This reset rollback preserves the complete pre-reset dataset.

After an API restart, verify that a previously accepted `Idempotency-Key` replays the original submission and that resolved review status/evidence remains stored. Restart does not reseed or delete a non-empty database.

## Benchmark boundary

Benchmarks retain an explicit download-capable provider mode and are not changed by the runtime cache-only policy:

```powershell
uv run --offline python -m scripts.run_hybrid_benchmark
```

The benchmark's model loading policy is separate from production/demo composition. Do not make runtime infer permission from benchmark behavior or current network state.

## Server-owned configuration

The server may use these environment variables for approved local configuration:

```text
CIVICPULSE_DB_PATH
CIVICPULSE_SEED_PATH
CIVICPULSE_SENSITIVE_LOCATIONS_PATH
CIVICPULSE_MATCHING_POLICY_PATH
CIVICPULSE_PRIORITY_POLICY_PATH
CIVICPULSE_ADMIN_RESET_ENABLED
```

API requests and Dashboard controls never provide filesystem paths. Keep the default runtime invocation offline and use the explicit prewarm command when cache preparation is required.
