# Task 9.2 Offline, Fault, and Recovery Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Establish an offline-enforced production runtime policy and prove safe failure, rollback, restart, and Dashboard recovery for model caches, SQLite state, locks, and reset operations.

**Architecture:** Keep the embedding abstraction reusable, but make construction intent explicit. The production runtime uses a cache-only provider and fails fast; prewarm and benchmark call explicit download-capable modes. SQLite writes use bounded busy timeouts and translate lock failures after rollback. Health and Dashboard contracts expose safe not-ready states without filesystem paths or raw exception text.

**Tech Stack:** Python 3.12, Pydantic v2, sentence-transformers, SQLite, FastAPI, Streamlit, httpx, pytest, Pyright strict, Ruff, uv offline.

## Global Constraints

- Production/demo runtime always passes local_files_only=True and never downloads implicitly.
- Prewarm defaults to explicit download permission; --offline only validates an existing cache.
- Benchmark tools retain explicit download-capable behavior.
- Stable public error codes are embedding_model_cache_missing, embedding_model_cache_invalid, database_corrupt, and database_busy.
- Public errors contain no absolute paths, raw cache/database exceptions, tokens, or internal cache details.
- Readiness requires local model load, non-empty probe vector, and expected embedding dimension.
- SQLite lock handling is bounded and leaves no partial write.
- Reset is atomic and preserves the complete pre-reset dataset on failure.
- No request supplies runtime filesystem paths.
- Dashboard remains an HTTP client and must safely handle unreachable/not-ready APIs.
- Do not change matching thresholds, clustering uncertainty rules, priority evidence rules, or benchmark data.

## Current Evidence

- Task 9.1 commit: d4daf65.
- SentenceTransformerProvider currently constructs SentenceTransformer(model_name) without a cache-only option.
- Provider callers include runtime, prewarm, embedding benchmark, hybrid benchmark, seed generation, and unit tests.
- CivicPulseService.health already maps dependency failures to readiness components.
- SQLiteRepository already has transaction boundaries and failure hooks.
- Dashboard app already stops operational rendering when core readiness is false.

---

### Task 1: Add explicit embedding modes and stable cache errors

**Files:** Modify src/civicpulse/embeddings.py; test tests/unit/test_embeddings.py.

**Interfaces:**

- Constructor accepts local_files_only=False, expected_dimension=None, and the existing model_factory seam.
- for_runtime(...) always sets local_files_only=True.
- for_prewarm(..., offline=False) maps offline to local-only loading.
- for_benchmark(...) explicitly permits download behavior.
- ModelCacheUnavailable.code is embedding_model_cache_missing.
- ModelCacheInvalid.code is embedding_model_cache_invalid.

- [ ] Step 1: Write failing tests.

~~~python
def test_runtime_factory_forces_local_only(monkeypatch) -> None:
    observed = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name, **kwargs):
            observed.update(kwargs)

        def encode(self, inputs, *, normalize_embeddings, show_progress_bar):
            return [[1.0, 0.0, 0.0, 0.0] for _ in inputs]

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", FakeSentenceTransformer)
    provider = SentenceTransformerProvider.for_runtime(
        "cached-model", "normalization-v1", expected_dimension=4
    )
    provider.embed(["probe"])
    assert observed["local_files_only"] is True


def test_missing_cache_error_is_stable_and_sanitized(monkeypatch) -> None:
    class MissingModel:
        def __init__(self, model_name, **kwargs):
            raise OSError("C:/private/cache/secret-model/config.json missing")

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", MissingModel)
    provider = SentenceTransformerProvider.for_runtime("cached-model", "normalization-v1")

    with pytest.raises(ModelCacheUnavailable) as caught:
        provider.embed(["probe"])

    assert caught.value.code == "embedding_model_cache_missing"
    assert "C:/private" not in str(caught.value)
    assert "prewarm_model" in str(caught.value)


def test_expected_dimension_rejects_invalid_model() -> None:
    provider = SentenceTransformerProvider.for_runtime(
        "cached-model",
        "normalization-v1",
        expected_dimension=384,
        model_factory=FakeEncoder,
    )
    with pytest.raises(ModelCacheInvalid, match="embedding_model_cache_invalid"):
        provider.embed(["probe"])


def test_prewarmer_and_benchmark_keep_explicit_download_mode(monkeypatch) -> None:
    observed = []

    class FakeSentenceTransformer:
        def __init__(self, model_name, **kwargs):
            observed.append(kwargs["local_files_only"])

        def encode(self, inputs, *, normalize_embeddings, show_progress_bar):
            return [[1.0, 0.0] for _ in inputs]

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", FakeSentenceTransformer)
    SentenceTransformerProvider.for_prewarm("model", "normalization-v1").embed(["a"])
    SentenceTransformerProvider.for_prewarm(
        "model", "normalization-v1", offline=True
    ).embed(["b"])
    SentenceTransformerProvider.for_benchmark("model", "normalization-v1").embed(["c"])
    assert observed == [False, True, False]
~~~

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/unit/test_embeddings.py -v
~~~

Expected: failures because the mode factories, errors, and dimension contract do not exist.

- [ ] Step 3: Implement minimal provider policy.

Add ModelCacheUnavailable with a sanitized message containing the prewarm command, and ModelCacheInvalid with a stable code. Pass local_files_only to SentenceTransformer. In local-only mode, convert model load OSError/RuntimeError/ValueError to ModelCacheUnavailable without exposing the original text. Validate expected_dimension on the first vector and raise ModelCacheInvalid for empty, inconsistent, or wrong-size vectors.

- [ ] Step 4: Run GREEN and static checks.

~~~powershell
uv run --offline python -m pytest tests/unit/test_embeddings.py -v
uv run --offline pyright src/civicpulse/embeddings.py tests/unit/test_embeddings.py
uv run --offline ruff check src/civicpulse/embeddings.py tests/unit/test_embeddings.py
~~~

Expected: all focused tests pass and both static checks are clean.

---

### Task 2: Enforce cache-only startup in runtime

**Files:** Modify src/civicpulse/runtime.py, src/civicpulse/service.py, tests/integration/test_runtime_composition.py, and tests/integration/test_health.py.

**Interfaces:**

- build_runtime constructs SentenceTransformerProvider.for_runtime.
- Runtime validates the seed manifest embedding dimension and performs the fixed readiness probe before returning an app.
- Missing or invalid cache propagates a stable error before server composition.
- Health returns a generic not-ready component and recovery command uv run --offline python -m scripts.prewarm_model --offline.

- [ ] Step 1: Write failing tests.

~~~python
def test_runtime_passes_expected_dimension_to_cache_only_provider(monkeypatch, tmp_path):
    observed = {}

    class FakeProvider:
        model_name = "intfloat/multilingual-e5-small"
        normalization_version = "normalization-v1"

        def embed(self, texts):
            return tuple((1.0, *([0.0] * 383)) for _ in texts)

    def factory(*args, **kwargs):
        observed.update(kwargs)
        return FakeProvider()

    monkeypatch.setattr("civicpulse.runtime.SentenceTransformerProvider.for_runtime", factory)
    build_runtime(runtime_settings(tmp_path))
    assert observed["expected_dimension"] == 384


def test_runtime_missing_cache_fails_before_app_construction(monkeypatch, tmp_path):
    def unavailable(*args, **kwargs):
        raise ModelCacheUnavailable

    monkeypatch.setattr("civicpulse.runtime.SentenceTransformerProvider.for_runtime", unavailable)
    with pytest.raises(ModelCacheUnavailable) as caught:
        build_runtime(runtime_settings(tmp_path))
    assert caught.value.code == "embedding_model_cache_missing"
    assert "C:/" not in str(caught.value)
~~~

Add a health test with a provider that raises ModelCacheInvalid and assert HTTP 503 readiness_failure without the internal reason or path.

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/integration/test_runtime_composition.py tests/integration/test_health.py -v
~~~

Expected: runtime still uses the generic constructor and does not probe before app construction.

- [ ] Step 3: Implement.

Add a strict seed-manifest dimension loader that returns only the integer dimension and raises a generic configured-seed error. Construct for_runtime with that dimension, call the fixed readiness sentence before seeding or returning the app, and never retry through a network-capable constructor. Update health recovery text to the offline prewarm command and keep public messages path-free.

- [ ] Step 4: Run GREEN.

Run the Step 2 command. Expected: runtime, restart, missing-cache, invalid-cache, and existing health tests pass.

- [ ] Step 5: Verify import side-effect boundary.

~~~powershell
uv run --offline python -c "import civicpulse.runtime; print('imported')"
~~~

Expected: no database file, model load, seed, or server starts from import alone.

---

### Task 3: Preserve explicit prewarm and benchmark modes

**Files:** Modify scripts/prewarm_model.py, scripts/run_embedding_benchmark.py, scripts/run_hybrid_benchmark.py; create or modify tests/integration/test_model_modes.py.

**Interfaces:**

- prewarm(policy_path="config/matching_policy.json", *, offline=False, seed_path="data/seed_complaints.json") -> int.
- CLI adds --offline and --seed.
- run_real_benchmark uses for_benchmark.
- Existing benchmark report schema and exit behavior remain unchanged.

- [ ] Step 1: Write failing mode tests.

~~~python
def test_prewarm_offline_selects_local_only(monkeypatch):
    observed = []

    def factory(*args, **kwargs):
        observed.append(kwargs["offline"])
        return FakeProvider()

    monkeypatch.setattr("scripts.prewarm_model.SentenceTransformerProvider.for_prewarm", factory)
    assert prewarm(offline=True) == 0
    assert observed == [True]


def test_prewarm_default_allows_download(monkeypatch):
    observed = []

    def factory(*args, **kwargs):
        observed.append(kwargs["offline"])
        return FakeProvider()

    monkeypatch.setattr("scripts.prewarm_model.SentenceTransformerProvider.for_prewarm", factory)
    assert prewarm() == 0
    assert observed == [False]


def test_hybrid_benchmark_uses_benchmark_factory(monkeypatch):
    observed = []

    def factory(*args, **kwargs):
        observed.append(True)
        return FakeProvider()

    monkeypatch.setattr(
        "scripts.run_hybrid_benchmark.SentenceTransformerProvider.for_benchmark",
        factory,
    )
    run_real_benchmark(minimal_pairs(), load_matching_policy("config/matching_policy.json"))
    assert observed == [True]
~~~

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/integration/test_model_modes.py -v
~~~

Expected: failures because current scripts call the generic constructor and have no offline flag.

- [ ] Step 3: Implement explicit call sites.

Use for_prewarm with offline=args.offline and for_benchmark in both benchmark scripts. Validate non-empty prewarm output and expected seed dimension before printing readiness.

- [ ] Step 4: Verify.

~~~powershell
uv run --offline python -m pytest tests/integration/test_model_modes.py tests/unit/test_embeddings.py -v
uv run --offline python -m scripts.run_hybrid_benchmark
uv run --offline python -m scripts.prewarm_model --offline
~~~

Expected: tests pass, benchmark remains green, and cached offline prewarm prints a 384-dimensional readiness result.

- [ ] Step 5: Verify missing-cache offline prewarm.

Use a subprocess test with a constructor that raises OSError. Expected: non-zero exit, stable cache code/message, no absolute path, and no fallback download.

---

### Task 4: Add SQLite corruption and bounded-lock contracts

**Files:** Modify src/civicpulse/repository.py and src/civicpulse/api/routes/mutations.py; test tests/integration/test_repository.py and tests/contract/test_mutation_api.py.

**Interfaces:**

- DatabaseCorrupt.code is database_corrupt.
- DatabaseBusy.code is database_busy.
- SQLite connections use bounded timeout and PRAGMA busy_timeout.
- Lock translation occurs after rollback.
- Complaint/reset routes map DatabaseBusy to HTTP 503 without SQLite details.

- [ ] Step 1: Write failing tests.

~~~python
def test_corrupt_database_is_sanitized(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(DatabaseCorrupt) as caught:
        SQLiteRepository(path).initialize()
    assert caught.value.code == "database_corrupt"
    assert str(path) not in str(caught.value)


def test_locked_submission_has_no_partial_write(tmp_path):
    repository = SQLiteRepository(tmp_path / "locked.db")
    repository.initialize()
    with repository.connect() as lock:
        lock.execute("BEGIN EXCLUSIVE")
        with pytest.raises(DatabaseBusy):
            repository.add_complaint(valid_complaint(), "locked-key")
    assert repository.get_by_idempotency_key("locked-key") is None
    assert repository.list_complaints() == []
~~~

Add an API test asserting HTTP 503, code database_busy, and no raw SQLite text or absolute path.

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/integration/test_repository.py tests/contract/test_mutation_api.py -v
~~~

Expected: corrupt files expose raw SQLite errors and locks become generic internal errors.

- [ ] Step 3: Implement bounded translation.

Use sqlite3.connect(path, timeout=0.25) and PRAGMA busy_timeout=250. At every transactional write boundary, rollback on OperationalError containing locked or busy, then raise DatabaseBusy. Translate initialization DatabaseError to DatabaseCorrupt after rollback. Never delete or recreate a corrupt file.

- [ ] Step 4: Map API errors.

Catch DatabaseBusy before generic exceptions in complaint and reset routes. Return a stable 503 envelope. Keep database corruption a startup/readiness failure, not an automatic reset.

- [ ] Step 5: Run GREEN.

Run the Step 2 command. Expected: corruption, lock, sanitized envelope, rollback, and existing mutation tests pass.

---

### Task 5: Prove reset rollback and restart recovery

**Files:** Modify src/civicpulse/repository.py and src/civicpulse/api/routes/mutations.py; modify tests/integration/test_runtime_composition.py and tests/integration/test_seed_pipeline.py; create tests/integration/test_recovery_workflow.py.

**Interfaces:**

- replace_dataset remains one transaction and invokes failure_hook("after_dataset_delete") before commit.
- A non-empty build_runtime never reseeds or deletes state.
- Failed reset preserves complaints, idempotency records, embeddings, incidents, edges, and reviews.

- [ ] Step 1: Write failing rollback/restart tests.

~~~python
def test_reset_failure_preserves_submitted_state(tmp_path):
    settings = runtime_settings(tmp_path, admin_reset_enabled=True)
    runtime = build_runtime(settings, embedding_provider=FakeProvider())
    submitted = submit_one(runtime.app, key="recovery-key")
    runtime.repository.failure_hook = lambda event: (
        (_ for _ in ()).throw(RuntimeError("injected reset failure"))
        if event == "after_dataset_delete"
        else None
    )

    with pytest.raises(RuntimeError, match="injected reset failure"):
        runtime.service.reset_seed(settings.seed_path)

    assert runtime.repository.get_by_idempotency_key("recovery-key") is not None
    assert len(runtime.repository.list_complaints()) == 121


def test_restart_preserves_submission_and_resolution(tmp_path):
    settings = runtime_settings(tmp_path, admin_reset_enabled=True)
    first = build_runtime(settings, embedding_provider=FakeProvider())
    submitted = submit_one(first.app, key="restart-key")
    resolve_one_pending_review(first.app)

    restarted = build_runtime(settings, embedding_provider=FakeProvider())
    replay = submit_same_request(restarted.app, key="restart-key")

    assert replay.json()["replayed"] is True
    assert replay.json()["complaint"]["complaint_id"] == submitted.json()["complaint"]["complaint_id"]
    assert restarted.repository.get_submission_record("restart-key") is not None
~~~

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/integration/test_runtime_composition.py tests/integration/test_seed_pipeline.py tests/integration/test_recovery_workflow.py -v
~~~

Expected: the failure hook does not yet target dataset replacement and recovery assertions expose any partial-state behavior.

- [ ] Step 3: Add deterministic dataset failure hook.

Invoke failure_hook("after_dataset_delete") after old dataset rows are deleted but before new rows are inserted/committed. Let the surrounding transaction rollback restore all old rows.

- [ ] Step 4: Map reset lock/failure errors.

Catch DatabaseBusy as 503 database_busy. Keep seed validation failures as 503 seed_configuration_error. Preserve admin_reset_disabled as 403 and never expose the server seed path.

- [ ] Step 5: Run GREEN.

Expected: failed reset leaves every pre-reset table unchanged, and restart replay remains idempotent.

---

### Task 6: Add Dashboard not-ready and recovery contracts

**Files:** Create tests/contract/test_dashboard_recovery.py; modify Dashboard code only if a contract gap is exposed.

**Interfaces:**

- health_ready maps 503 readiness_failure without paths.
- Timeout/request failures remain api_unreachable.
- Streamlit warns and does not render operational views while core_ready is false.
- A later successful readiness response allows normal tabs.

- [ ] Step 1: Write failing client tests.

~~~python
def test_dashboard_maps_cache_not_ready_without_path():
    client = ApiClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                503,
                json={
                    "error": {
                        "code": "readiness_failure",
                        "message": "The embedding model is unavailable or not cached.",
                        "details": {},
                    }
                },
            )
        )
    )
    with pytest.raises(DashboardApiError) as caught:
        client.health_ready()
    assert caught.value.code == "readiness_failure"
    assert "C:/" not in caught.value.user_message


def test_dashboard_keeps_unreachable_behavior():
    client = ApiClient(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline"))
        )
    )
    with pytest.raises(DashboardApiError) as caught:
        client.health_ready()
    assert caught.value.code == "api_unreachable"
~~~

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/contract/test_dashboard_recovery.py tests/contract/test_dashboard_gateway.py -v
~~~

Expected: the new tests expose any error-envelope or not-ready rendering gap.

- [ ] Step 3: Implement only the smallest exposed fix.

Keep the Dashboard as an HTTP client. Do not add repository/service imports, backend paths, or custom local retry loops.

- [ ] Step 4: Run GREEN.

~~~powershell
uv run --offline python -m pytest tests/contract/test_dashboard_recovery.py tests/contract/test_dashboard_gateway.py tests/contract/test_dashboard_submission.py tests/contract/test_dashboard_review_mutations.py -v
~~~

Expected: unavailable, timeout, not-ready, and recovered-ready contracts pass.

---

### Task 7: Write the offline/fault/recovery runbook

**Files:** Create docs/demo-runbook.md; modify README.md; create tests/contract/test_documentation_boundaries.py.

**Interfaces:**

- Runbook documents online prewarm, offline prewarm, cache-only runtime, missing/invalid cache, corrupt database, bounded lock retry, atomic reset rollback, API restart, and Dashboard recovery.
- README links to the runbook and states runtime never downloads implicitly.

- [ ] Step 1: Write failing documentation assertions.

~~~python
def test_offline_recovery_boundaries_are_documented():
    text = Path("README.md").read_text(encoding="utf-8") + Path(
        "docs/demo-runbook.md"
    ).read_text(encoding="utf-8")
    for term in (
        "local_files_only",
        "embedding_model_cache_missing",
        "embedding_model_cache_invalid",
        "--offline",
        "database_busy",
        "database_corrupt",
        "reset rollback",
        "CIVICPULSE_DB_PATH",
    ):
        assert term in text
~~~

- [ ] Step 2: Run RED.

~~~powershell
uv run --offline python -m pytest tests/contract/test_documentation_boundaries.py -v
~~~

Expected: the runbook and explicit runtime policy statements are absent.

- [ ] Step 3: Write the runbook.

Include these commands and explain their distinct permissions:

~~~powershell
# Explicit online preparation
uv run python -m scripts.prewarm_model

# Offline cache validation
uv run --offline python -m scripts.prewarm_model --offline

# Production/demo cache-only runtime
uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000
~~~

Document stable error codes, safe recovery actions, no destructive automatic repair, restart preservation, and Dashboard not-ready behavior.

- [ ] Step 4: Run GREEN and inspect terms.

~~~powershell
uv run --offline python -m pytest tests/contract/test_documentation_boundaries.py -v
rg -n "local_files_only|embedding_model_cache_missing|database_busy|database_corrupt|reset rollback|--offline" README.md docs/demo-runbook.md
~~~

Expected: all required boundaries are visible.

---

### Task 8: Run the Task 9.2 quality gate

**Files:** Verification only, except defects directly exposed by Task 9.2 tests.

- [ ] Step 1: Run complete non-live suite.

~~~powershell
uv run --offline python -m pytest -m "not live" -q
~~~

Expected: all existing, model-mode, fault, recovery, and Dashboard tests pass.

- [ ] Step 2: Run strict type and changed-file lint.

~~~powershell
uv run --offline pyright src scripts
uv run --offline ruff check src/civicpulse/embeddings.py src/civicpulse/runtime.py src/civicpulse/repository.py src/civicpulse/service.py src/civicpulse/api/routes/mutations.py scripts/prewarm_model.py scripts/run_embedding_benchmark.py scripts/run_hybrid_benchmark.py tests/integration/test_model_modes.py tests/integration/test_recovery_workflow.py tests/contract/test_dashboard_recovery.py
~~~

Expected: Pyright has zero errors and changed-file Ruff is clean. Existing repository-wide Ruff findings remain recorded and are outside this scope.

- [ ] Step 3: Run benchmark and offline prewarm.

~~~powershell
uv run --offline python -m scripts.run_hybrid_benchmark
uv run --offline python -m scripts.prewarm_model --offline
~~~

Expected: zero false auto-merges, zero positive no-matches, clear-positive auto rate at least 0.75, and cached 384-dimensional offline readiness.

- [ ] Step 4: Prove no implicit runtime network path.

Run the provider mode tests with the model constructor patched to record local_files_only. Expected: runtime passes True, never invokes download fallback, and missing cache fails quickly.

- [ ] Step 5: Verify scope.

~~~powershell
git diff --check
git status --short
git diff --name-only
~~~

Expected: only provider/runtime policy, resilience tests, API/Dashboard contracts, runbook, README, and this plan are in scope. Do not stage or commit automatically; report evidence and wait for explicit approval.

- [ ] Step 6: Perform a disposable two-process recovery smoke.

Verify cache-only readiness, API restart preservation, bounded locked write with no partial row, reset rollback, and Dashboard recovery. Use disposable database/ports, stop both processes, and delete only disposable smoke artifacts.

## Task 9.2 Stop Conditions

- Stop if runtime attempts a download with local_files_only=True.
- Stop if a cache/database error exposes an absolute path or raw exception.
- Stop if a lock leaves any row behind.
- Stop if reset rollback changes any pre-reset state.
- Stop if benchmark construction accidentally becomes cache-only.
- Stop if Dashboard imports backend services or filesystem paths.
- Task 9.2 is complete only when runtime is cache-only and fail-fast, preparation/benchmark modes remain explicit, corruption/lock/reset/restart behavior is tested, Dashboard degradation is safe, and the full quality gate is green.

## Phase 9 Continuation

After Task 9.2 is verified and committed, write Task 9.3 separately for cached 180-complaint graph construction latency, warm submission latency, seed reset duration, and Dashboard map-row timing.
