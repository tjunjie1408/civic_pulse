# CivicPulse-lite MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline-capable multilingual civic complaint clustering and triage demo that avoids false incident merges, explains every decision, and treats photo analysis as optional post-submission enrichment.

**Architecture:** A Python-first local modular monolith uses strict Pydantic contracts, a FastAPI delivery adapter, a service layer, SQLite persistence, cached SentenceTransformer embeddings, hard category/geography/time constraints, connected-component clustering, and a versioned priority policy. Streamlit is the first UI through a typed gateway that shares FastAPI DTOs; OpenAPI preserves a later Next.js + TypeScript migration path without forcing two frontend implementations into the MVP. The first delivery gate is a frozen hybrid-matching holdout benchmark; product work stops if that gate fails.

**Tech Stack:** Python 3.12, uv, Pydantic v2, FastAPI, sentence-transformers, NumPy, SQLite, Streamlit, PyDeck, Pillow, OpenAI Python SDK for the optional adapter, pytest, Hypothesis, Pyright strict, Ruff, pre-commit.

## Plan Revision

The roadmap is dependency-ordered rather than filesystem-ordered: Foundation → Matching → Clustering → Persistence → Priority → Application workflows → API → UI → Reliability → Optional enrichment. The original file had two `Phase 4` headings and omitted the persistent review workflow. This revision treats the logical plan as 39 tasks: the added review workflow is Task 6.2 and the explicit review API is Task 7.5.

## Global Constraints

- Core submission, clustering, ranking, and dashboard behavior must work offline after the embedding model is cached.
- Known category mismatch, distance greater than 500 metres, or time difference greater than seven days must never auto-merge.
- Unknown-category complaints require officer review and do not auto-merge.
- False merge prevention has priority over recall.
- The hybrid holdout gate is zero false automatic merges and zero positive examples forced to `no_match`; review-required positives remain visible for officer triage.
- Priority values are configurable prototype policy parameters and must be displayed as bands with reasons.
- Photo analysis is a separate post-submission action and never affects matching, priority, authenticity, or successful submission.
- Uploaded photos are JPEG or PNG, at most 5 MiB, and stored under generated names rather than supplied filenames.
- The MVP is single-process and single-user; multi-user concurrency is not part of acceptance.
- Python is pinned to 3.12.x in `.python-version` and `requires-python = ">=3.12,<3.13"`.
- Core Python passes Pyright strict and Ruff. `Any`, `dict[str, object]`, and `# type: ignore` are prohibited in core modules unless the exact external-boundary reason is documented inline.
- Pydantic validates all domain/API boundaries; SQLite independently enforces critical nullability, range, enum, uniqueness, and foreign-key constraints.
- FastAPI OpenAPI is the source contract for any future TypeScript client; client types must be generated, not handwritten duplicates.
- Every behavior change follows RED -> GREEN -> REFACTOR, with the focused test observed failing before implementation.

---

## Target File Structure

```text
.python-version
.pre-commit-config.yaml
app.py
config/
  matching_policy.json
  normalization_aliases.json
  priority_policy.json
data/
  seed_complaints.json
  sensitive_locations.json
benchmarks/
  manglish_complaint_pairs.json
  benchmark_manifest.json
  reports/
src/civicpulse/
  __init__.py
  domain.py
  api.py
  api_models.py
  gateway.py
  config.py
  normalize.py
  categorize.py
  geo.py
  embeddings.py
  matching.py
  clustering.py
  priority.py
  repository.py
  service.py
  api/
    app.py
    dependencies.py
    errors.py
    dto/
    routes/
  photos.py
  vision_openai.py
tests/
  conftest.py
  unit/
  integration/
  e2e/
  live/
  contract/
```

## Phase 1 — Project Foundation and Contracts

### Task 1.1: Lock Runtime and Development Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `.python-version`
- Create: `.pre-commit-config.yaml`
- Create: `.gitignore`

**Interfaces:**
- Produces the reproducible environment used by every later task.

**Test area:** Environment smoke test and dependency import test.

**Acceptance scope:**
- `uv sync --frozen` succeeds under Python 3.12.x from the lock file.
- Imports succeed for `pydantic`, `fastapi`, `sentence_transformers`, `streamlit`, `PIL`, `openai`, `pytest`, and `hypothesis`.
- `pyproject.toml` contains Pyright strict, Ruff target `py312`, strict pytest markers/config, and package source paths.
- pre-commit runs Ruff format, Ruff lint, Pyright, and the non-live test suite.
- `.venv/`, caches, local databases, uploads, secrets, and generated benchmark reports are ignored.

- [ ] **Step 1: Add a failing dependency smoke test**

Create `tests/test_dependencies.py` that imports every direct runtime package and asserts `sys.version_info[:2] == (3, 12)`.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m pytest tests/test_dependencies.py -v`
Expected: FAIL because the new direct packages and pytest are not all declared.

- [ ] **Step 3: Add exact dependencies**

Run:

```powershell
uv python install 3.12
uv python pin 3.12
uv add pydantic fastapi uvicorn httpx streamlit pandas pillow openai
uv add --dev pytest pytest-cov hypothesis ruff pyright pre-commit
```

Add `.gitignore` entries for `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage`, `data/civicpulse.db`, `data/uploads/`, `.env`, and `benchmarks/reports/*.json`.

Add these exact tool policies:

```toml
[tool.pyright]
typeCheckingMode = "strict"
reportUnknownMemberType = true
reportUnknownArgumentType = true
reportUnknownVariableType = true
reportMissingTypeStubs = false

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "ANN"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
markers = ["live: requires external credentials and network", "performance: local latency budget"]
```

- [ ] **Step 4: Verify GREEN**

Run: `uv sync --frozen`
Run: `uv run python -m pytest tests/test_dependencies.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add pyproject.toml uv.lock .python-version .pre-commit-config.yaml .gitignore tests/test_dependencies.py
git commit -m "build: lock civicpulse runtime and test dependencies"
```

### Task 1.2: Define Domain Models and Input Validation

**Files:**
- Create: `src/civicpulse/__init__.py`
- Create: `src/civicpulse/domain.py`
- Create: `tests/unit/test_domain.py`

**Interfaces:**
- Produces `Category`, `ComplaintInput`, `Complaint`, `MatchDecision`, `Incident`, `PriorityAssessment`, `PhotoAssessment`, and `SubmissionResult`.
- `ComplaintInput` accepts `text`, `latitude`, `longitude`, `reported_at`, and optional `photo_path`.

**Test area:** Unit validation and serialization.

**Acceptance scope:**
- Text is stripped and must contain 3-2000 Unicode characters.
- Latitude is -90..90; longitude is -180..180; non-finite numbers are rejected.
- Timestamps must be timezone-aware and no more than five minutes in the future.
- Category values are exactly `pothole`, `blocked_drain`, `flooding`, `rubbish`, `street_light`, and `other`.
- No name, phone, email, identity number, or citizen account field exists.
- Public model fields are fully typed; core models do not expose `Any` or unstructured dictionaries.

- [ ] **Step 1: Write failing model tests**

Tests must cover one valid Manglish complaint, whitespace-only text, 1001 characters, NaN latitude, longitude 181, naive datetime, and future datetime.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'civicpulse'` or missing model symbols.

- [ ] **Step 3: Implement exact contracts**

Use Pydantic models and this public enum:

```python
class Category(StrEnum):
    POTHOLE = "pothole"
    BLOCKED_DRAIN = "blocked_drain"
    FLOODING = "flooding"
    RUBBISH = "rubbish"
    STREET_LIGHT = "street_light"
    OTHER = "other"
```

Add a pytest configuration entry to `pyproject.toml` with `pythonpath = ["src"]`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_domain.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse pyproject.toml tests/unit/test_domain.py
git commit -m "feat: define validated civic complaint domain models"
```

### Task 1.3: Add Versioned Matching and Priority Configuration

**Files:**
- Create: `config/matching_policy.json`
- Create: `config/priority_policy.json`
- Create: `src/civicpulse/config.py`
- Create: `tests/unit/test_config.py`

**Interfaces:**
- Produces `load_matching_policy(path) -> MatchingPolicy`.
- Produces `load_priority_policy(path) -> PriorityPolicy`.

**Test area:** Configuration schema, boundaries, and failure messages.

**Acceptance scope:**
- Matching defaults are radius 500 metres, time window seven days, initial semantic threshold 0.88, model `intfloat/multilingual-e5-small`, and policy version `matching-v1`.
- Priority rules exactly match the design document and use policy version `priority-v1`.
- Missing keys, unknown keys, negative thresholds, inverted bands, and invalid JSON fail at startup with the file path in the error.
- Both files include a `prototype_parameters` disclaimer string.

- [ ] **Step 1: Write failing config tests**

Test valid files, missing `semantic_threshold`, radius zero, semantic threshold 1.1, and priority bands where High is below Medium.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL because loaders do not exist.

- [ ] **Step 3: Implement typed loaders and exact JSON values**

Reject unknown keys with Pydantic `extra="forbid"`. Return immutable models.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add config src/civicpulse/config.py tests/unit/test_config.py
git commit -m "feat: add versioned matching and priority policies"
```

## Phase 2 — Hybrid Matching Evidence Gate

### Task 2.1: Complete and Freeze the Incident Benchmark Schema

**Files:**
- Modify: `benchmarks/manglish_complaint_pairs.json`
- Create: `benchmarks/benchmark_manifest.json`
- Modify: `benchmarks/README.md`
- Modify: `scripts/run_embedding_benchmark.py`
- Modify: `tests/test_embedding_benchmark.py`
- Create: `tests/unit/test_benchmark_schema.py`

**Interfaces:**
- Produces typed Pydantic `BenchmarkPair` and `BenchmarkManifest` models rather than untyped mapping records.
- Each pair contains `category_a`, `category_b`, `latitude_a`, `longitude_a`, `latitude_b`, `longitude_b`, `reported_at_a`, `reported_at_b`, `semantic_expected`, `incident_expected`, and `split`.

**Test area:** Dataset schema and partition integrity.

**Acceptance scope:**
- All 40 pairs have complete metadata.
- P01-P10 and N01-N10 are calibration; P11-P15 and N11-N15 are holdout.
- Holdout has exactly five incident matches and five incident non-matches.
- Semantic labels preserve the two time-window semantic matches.
- IDs are unique and manifest SHA-256 matches the dataset bytes.
- Existing benchmark runner and README use uv commands and pass Pyright strict without `Any`.

- [ ] **Step 1: Write failing schema tests**

Assert required fields, exact split membership, balanced incident labels in each split, unique IDs, valid coordinates/timestamps, and manifest checksum.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_benchmark_schema.py -v`
Expected: FAIL because most metadata and the manifest are absent.

- [ ] **Step 3: Add exact metadata and frozen split**

Place positive pairs within 100-450 metres and 0-72 hours. Encode negative cases with one decisive failing condition: category mismatch, distance 600-3000 metres, or time gap 8-60 days. Preserve text exactly unless correcting an identified typo; record any correction in the manifest. Refactor `load_pairs` to return `list[BenchmarkPair]` and document `uv run python scripts/run_embedding_benchmark.py`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_benchmark_schema.py tests/test_embedding_benchmark.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add benchmarks scripts/run_embedding_benchmark.py tests/test_embedding_benchmark.py tests/unit/test_benchmark_schema.py
git commit -m "test: freeze hybrid incident matching benchmark"
```

### Task 2.2: Implement Conservative Text Normalization

**Files:**
- Create: `config/normalization_aliases.json`
- Create: `src/civicpulse/normalize.py`
- Create: `tests/unit/test_normalize.py`

**Interfaces:**
- Produces `normalize_text(text: str) -> str`.
- Produces `NORMALIZATION_VERSION = "normalization-v1"`.

**Test area:** Example, Unicode, boundary, and property tests.

**Acceptance scope:**
- Uses Unicode NFKC, lowercase, whitespace compaction, punctuation separation, and token/phrase aliases.
- Includes `jln -> jalan`, `skolah -> sekolah`, `dpn -> depan`, `lampu jln -> lampu jalan`, and `longkang sumbat -> longkang tersumbat`.
- Preserves numbers and landmark tokens.
- Is idempotent for arbitrary Unicode strings up to 1000 characters.
- Does not translate full sentences or infer category facts.

- [ ] **Step 1: Write failing normalization tests**

Add exact examples plus a Hypothesis property: `normalize_text(normalize_text(text)) == normalize_text(text)`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_normalize.py -v`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement deterministic normalization**

Load aliases once, apply longest phrases before single tokens, and return a single-space-separated string.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_normalize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add config/normalization_aliases.json src/civicpulse/normalize.py tests/unit/test_normalize.py
git commit -m "feat: normalize Malaysian complaint text deterministically"
```

### Task 2.3: Implement Explainable Category Detection

**Files:**
- Create: `src/civicpulse/categorize.py`
- Create: `tests/unit/test_categorize.py`

**Interfaces:**
- Produces `classify_category(normalized_text: str) -> CategoryPrediction`.
- `CategoryPrediction` contains `category`, `matched_terms`, and `review_required`.

**Test area:** Unit classification, conflicting signals, and other/unclassified input.

**Acceptance scope:**
- Each of five categories has BM, English, and common Manglish terms.
- A unique highest category returns that category and matching terms.
- Equal top scores or no signals return `other` with `review_required=True`.
- Location tokens alone never determine category.

- [ ] **Step 1: Write failing category tests**

Cover `longkang tersumbat`, `drain blocked`, `jalan berlubang`, `sampah tak kutip`, `lampu jalan rosak`, a mixed drain/street-light sentence, and a vague sentence.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_categorize.py -v`
Expected: FAIL because the classifier is absent.

- [ ] **Step 3: Implement token and phrase scoring**

Return all matched terms in stable lexical order so the UI can explain the classification.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_categorize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/categorize.py tests/unit/test_categorize.py
git commit -m "feat: classify complaint categories with explainable rules"
```

### Task 2.4: Implement Geographic and Temporal Hard Constraints

**Files:**
- Create: `src/civicpulse/geo.py`
- Create: `tests/unit/test_geo.py`

**Interfaces:**
- Produces `haversine_metres(lat1, lon1, lat2, lon2) -> float`.
- Produces `within_time_window(a, b, max_days) -> bool`.

**Test area:** Numerical boundary and timezone tests.

**Acceptance scope:**
- Same point returns 0 metres.
- Known coordinate fixture is within 1 metre of its expected distance.
- Exactly 500 metres passes; greater than 500 metres fails when the matcher applies policy.
- Exactly seven days passes; seven days and one second fails.
- Aware timestamps in different offsets compare correctly.

- [ ] **Step 1: Write failing geo/time tests**

Use fixed Kuala Lumpur coordinates and UTC/Asia-Singapore timestamps.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_geo.py -v`
Expected: FAIL because functions are absent.

- [ ] **Step 3: Implement pure functions**

Use Earth radius 6,371,008.8 metres and absolute UTC time difference.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_geo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/geo.py tests/unit/test_geo.py
git commit -m "feat: add geographic and temporal match constraints"
```

### Task 2.5: Extract a Cached Embedding Provider

**Files:**
- Create: `src/civicpulse/embeddings.py`
- Create: `tests/unit/test_embeddings.py`
- Modify: `scripts/run_embedding_benchmark.py`

**Interfaces:**
- Produces `EmbeddingProvider.embed(texts: Sequence[str]) -> np.ndarray`.
- Produces `SentenceTransformerProvider(model_name, cache_dir)`.
- Produces `cosine_similarity(a, b) -> float`.
- Cache key includes model name, normalization version, and normalized text SHA-256.

**Test area:** Unit provider contract, cache behavior, shape validation, and offline failure.

**Acceptance scope:**
- Repeated text uses the cache and does not call the model twice.
- Wrong embedding dimension or non-finite output raises a contextual domain error.
- A missing model cache while offline reports the model name and prewarm command.
- Existing benchmark behavior uses the provider rather than duplicate model-loading code.

- [ ] **Step 1: Write failing provider tests using a counting fake model**

Assert cache hit count, normalized output shape `(n, d)`, and failure for NaN output.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_embeddings.py -v`
Expected: FAIL because the provider is absent.

- [ ] **Step 3: Implement provider and refactor benchmark**

Use dependency injection so unit tests never download a model. Keep model loading lazy.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_embeddings.py tests/test_embedding_benchmark.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/embeddings.py scripts/run_embedding_benchmark.py tests
git commit -m "refactor: centralize cached multilingual embeddings"
```

### Task 2.6: Implement the Hybrid Pair Matcher

**Files:**
- Create: `src/civicpulse/matching.py`
- Create: `tests/unit/test_matching.py`

**Interfaces:**
- Produces `match_pair(a, b, similarity, policy) -> MatchDecision`.
- Decision fields are `auto_match`, `review_required`, `category_compatible`, `distance_metres`, `time_gap_seconds`, `semantic_similarity`, and ordered `reasons`.

**Test area:** Decision table, exact boundaries, and rejection explanation.

**Acceptance scope:**
- Known category mismatch rejects before semantic score.
- `other` category produces review-required and no auto-merge.
- Greater than 500 metres rejects.
- Greater than seven days rejects.
- Similarity equal to threshold passes; below threshold rejects.
- Every decision contains stable human-readable reasons.

- [ ] **Step 1: Write a failing decision-table test**

Parametrize category, distance, time, and similarity so each failing constraint is isolated.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_matching.py -v`
Expected: FAIL because `match_pair` is absent.

- [ ] **Step 3: Implement ordered short-circuit evaluation**

Order checks as category, distance, time, semantic threshold. Record computed values even when the final semantic check fails.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_matching.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/matching.py tests/unit/test_matching.py
git commit -m "feat: match incidents with hard constraints and semantics"
```

### Task 2.7: Calibrate and Enforce the Holdout Gate

**Files:**
- Create: `scripts/run_hybrid_benchmark.py`
- Create: `tests/integration/test_hybrid_benchmark.py`
- Modify: `config/matching_policy.json`
- Generate locally: `benchmarks/reports/hybrid-matching-v1.json`

**Interfaces:**
- Produces `evaluate_split(pairs, split, provider, policy) -> BenchmarkResult`.
- Produces JSON metrics with benchmark checksum, model, policy version, normalization version, threshold, confusion matrix, and per-pair decisions.

**Test area:** Integration benchmark, calibration isolation, and acceptance-gate logic.

**Acceptance scope:**
- Threshold selection reads calibration pairs only.
- Holdout IDs never influence threshold selection.
- Benchmark contains 40 labelled pairs: 20 positives and 20 hard negatives, with a balanced 10/10 holdout.
- Matching is tri-state: `auto_match`, `no_match`, or `review_required`.
- Compatible explicit entities use a separate `strong_entity_semantic_threshold`; the global threshold is not lowered for ambiguous locations.
- Holdout has zero false automatic merges and zero positive examples forced to `no_match`; positive examples may be auto-matches or review-required.
- Report includes separate counts for automatic matches, no-matches, review-required decisions, false automatic merges, and positive no-matches.
- Failure returns a non-zero process exit code and explicitly blocks Phase 3.

- [ ] **Step 1: Write failing integration tests with deterministic scored fixtures**

Verify calibration/holdout separation and both passing and failing gate exit behavior.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_hybrid_benchmark.py -v`
Expected: FAIL because the runner is absent.

- [ ] **Step 3: Implement calibration and report generation**

Choose the lowest calibration threshold that produces zero calibration false merges and maximum recall. Write that exact threshold to `matching_policy.json`, then evaluate holdout once. The threshold remains a configurable prototype parameter, not a production truth.

- [ ] **Step 4: Run real gate**

Run: `uv run python scripts/run_hybrid_benchmark.py`
Expected: exit 0 only when holdout acceptance passes. If it fails, stop this plan before Task 3.1 and record one controlled remediation experiment.

- [ ] **Step 5: Verify regression suite**

Run: `uv run pytest tests/unit tests/integration/test_hybrid_benchmark.py -v`
Expected: PASS.

- [ ] **Step 6: Commit boundary**

```powershell
git add scripts/run_hybrid_benchmark.py tests/integration/test_hybrid_benchmark.py config/matching_policy.json
git commit -m "test: enforce hybrid incident matching quality gate"
```

### Task 2.8: Add Explicit Location Entities and Tri-State Decisions

**Files:**
- Create: `src/civicpulse/location.py`
- Modify: `src/civicpulse/domain.py`
- Modify: `src/civicpulse/matching.py`
- Modify: `config/normalization_aliases.json`
- Create: `tests/unit/test_location.py`
- Modify: `tests/unit/test_matching.py`

**Interfaces:**
- `extract_location_entities(text) -> tuple[LocationEntity, ...]`.
- `compare_location_entities(first, second) -> LocationComparison`.
- `match_pair(...) -> MatchDecision` with explicit `MatchState` and `LocationCompatibility`.

**Test area:** Abbreviation normalization, block/unit/street/landmark extraction, conflicting explicit entities, missing-location unknown state, and matching state transitions.

**Acceptance scope:**
- Equivalent forms such as `Block A`/`Blok A` and `Jln Ampang`/`Jalan Ampang` are compatible.
- Explicit conflicting blocks, units, streets, or named landmarks are `no_match` even when semantic similarity is high.
- Missing or generic location evidence is `unknown` and produces `review_required`, never silent compatibility.
- Match decisions expose semantic, geographic, temporal, category, extracted-entity, location-compatibility, and final-state reasons.

**Phase 2 gate:** Do not make confirmed clustering claims unless Tasks 2.7–2.9 pass. If only the safety gate passes, review UI scaffolding may proceed but confirmed incident clustering remains blocked. If the automation gate fails, compare raw and normalized error cases; change only the alias lexicon, category rules, or one alternate encoder per experiment.

### Task 2.9: Enforce the Automation Capability Gate

**Files:**
- Modify: `config/matching_policy.json`
- Modify: `src/civicpulse/config.py`
- Modify: `src/civicpulse/matching.py`
- Modify: `scripts/run_embedding_benchmark.py`
- Modify: `scripts/run_hybrid_benchmark.py`
- Modify: `benchmarks/manglish_complaint_pairs.json`
- Modify: `tests/integration/test_hybrid_benchmark.py`

**Interfaces:**
- `MatchingPolicy.strong_entity_semantic_threshold`.
- Benchmark positive labels: `clear` or `ambiguous`.
- Report fields: `clear_positive_auto_rate`, `holdout_clear_auto_matches`, and `holdout_clear_positive_no_matches`.

**Test area:** Clear-positive automatic matching, ambiguous-positive review routing, explicit-conflict rejection, and false-automatic-merge prevention.

**Acceptance scope:**
- Clear positives require compatible explicit location entities, compatible category, passing geography/time constraints, and semantic similarity at the strong-entity threshold.
- Ambiguous positives may remain `review_required`, but must not become `no_match`.
- Holdout clear-positive auto-match rate is at least 75%.
- False automatic merges remain zero and explicit conflicts remain `no_match`.
- The report distinguishes confirmed automatic edges from review-candidate edges; review edges are not confirmed incidents.

**Updated Phase 2 gate:** Tasks 2.7–2.9 must pass before formal clustering claims. If the safety gate passes but the automation gate fails, UI scaffolding and review workflows may proceed, but confirmed incident clustering and “N complaints became one incident” claims remain blocked.

## Phase 3 — Incident Clustering and Explanations

### Task 3.1: Build Deterministic Connected-Component Clustering

**Files:**
- Create: `src/civicpulse/clustering.py`
- Create: `tests/unit/test_clustering.py`

**Interfaces:**
- Produces `build_incidents(complaints, relationships) -> list[Incident]`.
- Produces stable incident IDs from sorted member complaint IDs using a versioned UUID5 namespace.

**Test area:** Unit graph construction and property tests.

**Acceptance scope:**
- Every complaint belongs to exactly one incident.
- Input order does not change memberships or incident IDs.
- A-B and B-C accepted edges produce one component, and the explanation retains both edges.
- `REVIEW_REQUIRED` edges remain review candidates and never bridge confirmed components.
- `NO_MATCH` edges never appear as incident membership or review candidates.
- An internal `AUTO_MATCH`/`NO_MATCH` contradiction produces explicit `conflict` status and conflict reasons; it is not finalized as a confirmed incident.
- Incident output includes confirmed edges, review candidates, centroid, time bounds, category summary, status, and conflict reasons.
- A single complaint forms a valid one-member incident.

- [ ] **Step 1: Write failing example and Hypothesis tests**

Add chain, isolated node, reordered input, and duplicate complaint-ID cases.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_clustering.py -v`
Expected: FAIL because clustering is absent.

- [ ] **Step 3: Implement connected components without hidden global state**

Store accepted edge decisions on each incident for later officer inspection.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_clustering.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/clustering.py tests/unit/test_clustering.py
git commit -m "feat: cluster matched complaints deterministically"
```

### Task 3.2: Compute Incident Summaries and Map Geometry

**Files:**
- Modify: `src/civicpulse/clustering.py`
- Create: `tests/unit/test_incident_summary.py`

**Interfaces:**
- Produces `summarize_incident(members, accepted_edges) -> Incident`.
- Incident contains category, centroid, radius metres, first/last report time, report count, representative text, and matching explanations.

**Test area:** Aggregate calculation and deterministic tie-breaking.

**Acceptance scope:**
- Centroid is arithmetic mean of member coordinates.
- Radius is maximum Haversine distance from centroid.
- Representative text is the earliest complaint among the most common normalized text; ties use complaint ID.
- Category must be identical for auto-clustered known members.
- Report count equals unique member IDs.

- [ ] **Step 1: Write failing summary tests**

Use a three-member fixture with known centroid, radius, timestamps, and tie.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_incident_summary.py -v`
Expected: FAIL because summary fields are absent.

- [ ] **Step 3: Implement pure aggregation**

Keep display formatting outside the domain function.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_incident_summary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/clustering.py tests/unit/test_incident_summary.py
git commit -m "feat: summarize incident evidence and map geometry"
```

## Phase 4 — Transactional Persistence

**Execution note:** This persistence phase is the next product phase after priority (referred to as Phase 5 in the current architecture discussion). It treats Phase 3 incident IDs as membership-derived cluster snapshot IDs, not permanent case identities.

### Task 4.1: Create SQLite Schema and Migration Bootstrap

**Files:**
- Create: `src/civicpulse/repository.py`
- Create: `tests/integration/test_repository_schema.py`

**Interfaces:**
- Produces `SQLiteRepository(path)` and `initialize()`.
- Tables: `schema_version`, `complaints`, `embeddings`, `incidents`, `incident_members`, `match_edges`, `photo_assessments`, and `submission_keys`.

**Test area:** Temporary-database integration tests and schema idempotency.

**Acceptance scope:**
- Foreign keys are enabled.
- Repeated `initialize()` calls are safe.
- Schema version is exactly 1.
- Complaint IDs, submission keys, and incident memberships have uniqueness constraints.
- Embeddings store model and normalization versions.
- SQLite rejects text shorter than 3 characters, out-of-range coordinates, invalid category values, negative distances, and orphaned memberships even when Python validation is bypassed.

- [ ] **Step 1: Write failing schema tests**

Inspect `sqlite_master`, foreign-key pragma, unique violations, every CHECK constraint, orphan insertion, and repeated initialization.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_repository_schema.py -v`
Expected: FAIL because the repository is absent.

- [ ] **Step 3: Implement explicit schema transaction**

Use `BEGIN IMMEDIATE`, rollback on error, and context-managed connections. Define category CHECK values as `pothole`, `blocked_drain`, `flooding`, `rubbish`, `street_light`, and `other`; define coordinate CHECK ranges in SQL in addition to Pydantic validation.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_repository_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/repository.py tests/integration/test_repository_schema.py
git commit -m "feat: create transactional civicpulse sqlite schema"
```

### Task 4.2: Persist Complaints Idempotently

**Files:**
- Modify: `src/civicpulse/repository.py`
- Create: `tests/integration/test_repository_complaints.py`

**Interfaces:**
- Produces `add_complaint(complaint, idempotency_key) -> Complaint`.
- Produces `list_complaints() -> list[Complaint]`.
- Produces `save_embedding(complaint_id, vector, model_version, normalization_version)`.

**Test area:** CRUD, duplicate operation, serialization, and rollback.

**Acceptance scope:**
- Same idempotency key returns the original complaint without a second row.
- Different keys can store identical complaint content.
- Time zones round-trip without loss.
- Failed embedding write does not corrupt an existing complaint.
- Vector dimension and finite values are validated before writing.

- [ ] **Step 1: Write failing repository tests**

Cover fresh insert, replay, identical content with new key, timezone round-trip, and invalid vector.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_repository_complaints.py -v`
Expected: FAIL because CRUD methods are absent.

- [ ] **Step 3: Implement parameterized SQL only**

Serialize vectors as NumPy bytes with dtype and dimension metadata. Never interpolate user text into SQL.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_repository_complaints.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/repository.py tests/integration/test_repository_complaints.py
git commit -m "feat: persist complaints and embeddings idempotently"
```

### Task 4.3: Replace Cluster State Atomically

**Files:**
- Modify: `src/civicpulse/repository.py`
- Create: `tests/integration/test_repository_clusters.py`

**Interfaces:**
- Produces `replace_incidents(incidents) -> None`.
- Produces `list_incidents() -> list[Incident]` and `get_incident(id) -> Incident | None`.

**Test area:** Transaction, fault injection, referential integrity, and stale-state removal.

**Acceptance scope:**
- A successful replacement leaves every complaint in exactly one incident.
- An injected failure after deleting old memberships rolls back to the previous complete state.
- Removed incidents and edges do not remain stale.
- Unknown complaint references are rejected.

- [ ] **Step 1: Write failing atomicity test**

Inject an exception between incident insertion and membership insertion and assert the old state remains byte-for-byte equivalent through repository reads.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_repository_clusters.py -v`
Expected: FAIL because replacement is absent.

- [ ] **Step 3: Implement one-transaction replacement**

Delete and insert incident-derived tables inside `BEGIN IMMEDIATE`; do not modify complaint rows.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_repository_clusters.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/repository.py tests/integration/test_repository_clusters.py
git commit -m "feat: replace incident cluster state atomically"
```

## Phase 5 — Explainable Priority Policy

### Task 5.1: Detect Explicit Safety Signals

**Files:**
- Create: `src/civicpulse/priority.py`
- Create: `tests/unit/test_safety_signals.py`

**Interfaces:**
- Produces `detect_safety_signals(confirmed_complaints, policy) -> tuple[SafetySignal, ...]`.

**Test area:** Rule examples, negation guard, duplicate signals, and multilingual terms.

**Acceptance scope:**
- Signals include active flooding, accident/injury, blocked road, and exposed electrical hazard.
- Duplicate mentions yield one signal reason.
- Phrases such as `tiada kemalangan` and `no accident` do not trigger accident.
- Every signal records the matched phrase and complaint ID.

- [ ] **Step 1: Write failing safety-signal tests**

Include BM, English, Manglish, negated, and duplicated examples.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_safety_signals.py -v`
Expected: FAIL because detector is absent.

- [ ] **Step 3: Implement deterministic phrase rules**

Use policy-provided phrases and explicit local negation patterns; do not call an LLM.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_safety_signals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/priority.py tests/unit/test_safety_signals.py
git commit -m "feat: detect explainable civic safety signals"
```

### Task 5.2: Assess Priority Bands and Reasons

**Files:**
- Modify: `src/civicpulse/priority.py`
- Create: `data/sensitive_locations.json`
- Create: `tests/unit/test_priority.py`

**Interfaces:**
- Produces `assess_priority(incident, sensitive_locations, policy, now) -> PriorityAssessment`.

**Test area:** Decision table, exact thresholds, deterministic clock, and explanation coverage.

**Acceptance scope:**
- Applies configurable deterministic rule bands from confirmed report volume, safety signals, sensitive exposure, persistence, and evidence context.
- `REVIEW_REQUIRED` candidates are reported separately and cannot increase confirmed report count or priority.
- Conflict incidents return explicit review-required status and no normal operational priority.
- Every triggered rule produces a reason with source values and policy version.
- Assessment exposes normalized signals and triggered rules; no opaque weighted score is used as the primary decision.
- Same input, policy, and clock always return the same result.

- [ ] **Step 1: Write failing priority decision-table tests**

Cover every lower/upper boundary, a school at 250 metres, one just beyond 250 metres, and a full Critical example.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_priority.py -v`
Expected: FAIL because assessment is absent.

- [ ] **Step 3: Implement pure assessment**

Pass `now` explicitly. Sort reasons by policy factor order.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_priority.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/priority.py data/sensitive_locations.json tests/unit/test_priority.py
git commit -m "feat: rank incidents with configurable policy reasons"
```

## Phase 6 — Application Service & Operational Workflows

### Task 6.2: Persist and Apply Review Decisions

**Files:**
- Modify: `src/civicpulse/repository.py`
- Modify: `src/civicpulse/service.py`
- Modify: `src/civicpulse/domain.py`
- Create: `tests/integration/test_review_workflow.py`

**Interfaces:**
- `create_review(left_id, right_id, matcher_decision) -> ReviewRecord`.
- `resolve_review(review_id, approve, reviewer_id, note) -> ReviewResolution`.

**Test area:** Review state transitions, audit metadata, atomic graph recomputation, conflict detection, restart persistence, and stale/duplicate resolution.

**Acceptance scope:**
- Preserve the original matcher recommendation and reasons; store final relationship state and `officer_review` source separately.
- Only `pending` reviews may be resolved; repeated resolution is idempotent or returns an explicit domain conflict.
- Approval creates `AUTO_MATCH`, rejection creates `NO_MATCH`, then recomputes incidents and priorities atomically.
- Approval-induced contradictions remain `conflict` and receive no normal priority.
- Resolution returns previous/new snapshot IDs, affected complaint IDs, final status, and resulting priorities.

### Task 6.3: Import and Reset a Synthetic Seed Dataset

**Files:**
- Create: `data/seed_complaints.json`
- Create: `src/civicpulse/service.py`
- Create: `tests/integration/test_seed_pipeline.py`

**Interfaces:**
- Produces `CivicPulseService.initialize_seed(seed_path) -> SeedResult`.
- Produces `CivicPulseService.reset_seed(seed_path) -> SeedResult`.

**Test area:** End-to-end data validation, deterministic reset, checksum/version validation, rollback, order independence, review restoration, and embedding-cache independence.

**Acceptance scope:**
- Seed contains 120-180 complaints, five categories, three visible hotspots, BM/English/Manglish examples, and deliberate near-miss cases.
- Reset yields exact complaint count, IDs, relationships, review records, incident snapshot IDs, and priority outputs on repeated runs.
- Invalid seed input, checksum mismatch, schema error, or model/policy version mismatch leaves the previous database unchanged.
- Embeddings are cached and incident state is replaced atomically; candidate generation uses category/geo/time filtering rather than an unbounded all-pairs comparison.
- Seed import accepts pending/approved/rejected review resolutions and restores them without bypassing domain rules.

- [x] **Step 1: Write failing seed pipeline tests with a 12-record fixture**

Assert repeatability, invalid-record rollback, and expected cluster count.

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_seed_pipeline.py -v`
Expected: FAIL because service and seed import are absent.

- [x] **Step 3: Implement orchestration and full seed**

Validate every record before writing any. Precompute normalized text, category, and embeddings, then commit complaints and replace clusters.

- [x] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_seed_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add data/seed_complaints.json src/civicpulse/service.py tests/integration/test_seed_pipeline.py
git commit -m "feat: import and reset deterministic civic demo data"
```

### Task 6.1: Implement Idempotent Live Submission and Reclustering

**Files:**
- Modify: `src/civicpulse/service.py`
- Create: `tests/integration/test_submission_service.py`

**Interfaces:**
- Produces `submit_complaint(input, idempotency_key) -> SubmissionResult`.

**Test area:** Integration happy path, replay, cluster merge, failure isolation, and timing.

**Acceptance scope:**
- A valid submission is normalized, categorized, embedded, persisted, reclustered, prioritized, and returned.
- Replaying the same idempotency key returns the original result without increasing complaint count.
- A new Manglish complaint joins the expected seed incident and increases its report count by one.
- Model failure occurs before database writes and returns a contextual error.
- Cluster replacement failure rolls back the complaint insert and derived state as one service transaction boundary.

- [ ] **Step 1: Write failing service integration tests**

Use a fake embedding provider for deterministic behavior and inject repository failures.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_submission_service.py -v`
Expected: FAIL because submission is absent.

- [ ] **Step 3: Implement service transaction workflow**

Generate complaint ID and idempotency key at the UI boundary; compute fallible model work before opening the write transaction.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_submission_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/service.py tests/integration/test_submission_service.py
git commit -m "feat: submit complaints and refresh incidents safely"
```

### Task 6.4: Add Startup Health and Offline Readiness Checks

**Files:**
- Modify: `src/civicpulse/service.py`
- Create: `scripts/prewarm_model.py`
- Create: `tests/integration/test_health.py`

**Interfaces:**
- Produces `service.health() -> HealthReport`.
- Health checks database, policy versions, model cache, seed state, and optional photo provider separately.

**Test area:** Dependency failure and degraded-mode integration tests.

**Acceptance scope:**
- Core health is false when database or embedding model is unavailable.
- Photo provider failure reports degraded optional status without failing core health.
- Prewarm command loads model and embeds one fixed sentence.
- Error text includes a direct recovery command without leaking secrets.

- [x] **Step 1: Write failing health tests**

Simulate missing model cache, locked database, invalid policy, and missing photo key.

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_health.py -v`
Expected: FAIL because health reporting is absent.

- [x] **Step 3: Implement health report and prewarm script**

Use statuses `healthy`, `degraded`, and `unavailable` per component.

- [x] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_health.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/service.py scripts/prewarm_model.py tests/integration/test_health.py
git commit -m "feat: report offline and dependency readiness"
```

## Phase 7 — FastAPI Contract and Delivery Adapter

### Task 7.1: Define Versioned API DTOs and Application Factory

**Files:**
- Create: `src/civicpulse/api/app.py`
- Create: `src/civicpulse/api/dependencies.py`
- Create: `src/civicpulse/api/errors.py`
- Create: `src/civicpulse/api/dto/`
- Create: `src/civicpulse/api/routes/health.py`
- Create: `tests/contract/test_api_boundary.py`

**Interfaces:**
- Produces `create_app(settings: AppSettings | None = None, service: CivicPulseService | None = None) -> FastAPI`.
- Produces request/response DTOs `ComplaintCreateRequest`, `ComplaintResponse`, `IncidentSummaryResponse`, `IncidentDetailResponse`, `PriorityResponse`, `HealthResponse`, and `ApiErrorResponse`.

**Test area:** Contract unit tests, strict serialization, and application construction.

**Acceptance scope:**
- API prefix is `/api/v1`.
- DTOs use Pydantic v2 with `extra="forbid"` and explicit field descriptions/units.
- Latitude/longitude, metres, seconds, UTC timestamps, priority bands, and category enums cannot be confused by naming.
- DTO modules contain no `Any`, `dict[str, object]`, or duplicate enum definitions.
- App construction has no global database or model side effect.
- Importing `civicpulse.api` and calling `create_app()` have no database/model I/O; production dependency construction remains explicit.

- [x] **Step 1: Write failing DTO and app-factory tests**

Test one valid serialization, unknown field rejection, category serialization, timezone output, and side-effect-free app creation with a fake service.

- [x] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_api_boundary.py -v`
Expected: FAIL because API modules are absent.

- [x] **Step 3: Implement typed DTOs and factory**

Reuse domain enums and convert domain objects through explicit typed mapping functions. Do not return domain models directly from route functions.

- [x] **Step 4: Verify GREEN and strict typing**

Run: `uv run pytest tests/contract/test_api_boundary.py -v`
Run: `uv run pyright src/civicpulse/api scripts`
Expected: PASS with zero type errors.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/api.py src/civicpulse/api_models.py tests/contract/test_api_models.py
git commit -m "feat: define strict civicpulse api contracts"
```

### Task 7.2: Add Health and Incident Read Endpoints

**Files:**
- Modify: `src/civicpulse/api.py`
- Create: `tests/contract/test_api_read_endpoints.py`

**Interfaces:**
- `GET /api/v1/health`
- `GET /api/v1/incidents`
- `GET /api/v1/incidents/{incident_id}`

**Test area:** FastAPI TestClient contract and error mapping.

**Acceptance scope:**
- Health returns component statuses without secrets or filesystem paths.
- Incident list supports category, priority, and UTC time-range filters.
- Incident detail includes contributing complaints, accepted edges, and priority reasons.
- Missing incident returns a stable 404 `ApiErrorResponse`.
- Response bodies validate against their declared Pydantic response models.

- [ ] **Step 1: Write failing endpoint tests**

Use a fake service and assert status, exact JSON keys, filters passed to the service, and 404 body.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_api_read_endpoints.py -v`
Expected: FAIL because routes are absent.

- [ ] **Step 3: Implement thin route adapters**

Routes translate request/response data and domain errors only; matching, ranking, and SQL remain outside `api.py`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/contract/test_api_read_endpoints.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/api.py tests/contract/test_api_read_endpoints.py
git commit -m "feat: expose health and incident read api"
```

### Task 7.3: Add Submission and Reset Endpoints

**Files:**
- Modify: `src/civicpulse/api.py`
- Create: `tests/contract/test_api_write_endpoints.py`

**Interfaces:**
- `POST /api/v1/complaints`
- `POST /api/v1/demo/reset`
- Submission requires an `Idempotency-Key` header.

**Test area:** Contract validation, idempotency, error translation, and reset authorization-by-confirmation.

**Acceptance scope:**
- Missing or malformed idempotency key returns 400 and writes nothing.
- Invalid complaint input returns 422 with field locations.
- Successful submission returns 201 with complaint, incident outcome, and reasons.
- Replayed idempotency key returns 200 with the original response and no duplicate.
- Reset requires body `{"confirm": "RESET SYNTHETIC DATA"}` and returns seed count/checksum.
- Domain dependency failure maps to 503; state conflict maps to 409; unexpected error preserves server logs but returns sanitized 500.

- [ ] **Step 1: Write failing write-endpoint tests**

Cover all status codes, replay behavior, reset confirmation, and sanitized errors using a fake service.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_api_write_endpoints.py -v`
Expected: FAIL because write routes are absent.

- [ ] **Step 3: Implement typed routes and exception handlers**

Keep the API idempotency key as a UUID string and pass it unchanged to the service.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/contract/test_api_write_endpoints.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/api.py tests/contract/test_api_write_endpoints.py
git commit -m "feat: expose idempotent complaint write api"
```

### Task 7.4: Freeze and Validate the OpenAPI Contract

**Files:**
- Create: `docs/api/openapi.json`
- Create: `scripts/export_openapi.py`
- Create: `tests/contract/test_openapi.py`

**Interfaces:**
- Produces a deterministic OpenAPI 3 document for later generated clients.

**Test area:** Schema snapshot, operation IDs, and contract completeness.

**Acceptance scope:**
- Every route has a stable explicit `operation_id`.
- Every success and error response references a named schema.
- `docs/api/openapi.json` equals a normalized export from `create_app`.
- No schema contains unconstrained free-form objects for core data.
- A future TypeScript generator can consume the file without editing Python source.

- [ ] **Step 1: Write failing OpenAPI contract tests**

Assert route set, operation IDs, named response schemas, category enum, coordinate constraints, and snapshot equality.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_openapi.py -v`
Expected: FAIL because exporter and snapshot are absent.

- [ ] **Step 3: Implement deterministic exporter**

Sort JSON keys, use two-space indentation, and end with one newline.

- [ ] **Step 4: Verify GREEN**

Run: `uv run python scripts/export_openapi.py`
Run: `uv run pytest tests/contract/test_openapi.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add docs/api/openapi.json scripts/export_openapi.py tests/contract/test_openapi.py
git commit -m "test: freeze civicpulse openapi contract"
```

**Phase 7 gate:** FastAPI routes must be thin, strictly typed adapters with a stable OpenAPI snapshot before UI work begins.

### Task 7.5: Add Review Read and Resolution Endpoints

**Files:**
- Modify: `src/civicpulse/api_models.py`
- Modify: `src/civicpulse/api.py`
- Create: `tests/contract/test_review_api.py`

**Interfaces:**
- `GET /api/v1/reviews?status=pending`.
- `GET /api/v1/reviews/{review_id}`.
- `POST /api/v1/reviews/{review_id}/approve`.
- `POST /api/v1/reviews/{review_id}/reject`.

**Acceptance scope:**
- Requests include reviewer ID and optional note.
- Responses expose original matcher evidence, previous/final status, affected complaints, snapshot IDs, conflict status, and resulting priorities.
- Routes call the service workflow and do not mutate incidents directly.
- OpenAPI names all review request/response schemas.

## Phase 8 — Streamlit Operations Dashboard

### Task 8.1: Build Typed Gateway, Dashboard Shell, and Ranked Queue

**Files:**
- Create: `app.py`
- Create: `src/civicpulse/gateway.py`
- Create: `tests/e2e/test_app_queue.py`

**Interfaces:**
- App receives a `CivicPulseGateway` protocol. `InProcessGateway` maps service results through the same API DTOs used by FastAPI; an HTTP gateway can be added with a future TypeScript or separate-process client.

**Test area:** Streamlit AppTest UI integration.

**Acceptance scope:**
- Header labels the data as synthetic.
- Health status and optional-photo degradation are visible.
- Queue sorts by internal points descending, then oldest report, then incident ID.
- Each row shows priority band, category, report count, age, and top reasons.
- No unexplained decimal confidence appears.
- Gateway methods return API DTOs, so Streamlit cannot depend on repository or embedding internals.

- [ ] **Step 1: Write failing AppTest**

Load three fixed incidents and assert order and displayed fields.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_app_queue.py -v`
Expected: FAIL because `app.py` is absent.

- [ ] **Step 3: Implement shell and queue**

Cache only immutable resources and gateway construction; do not cache user submission results.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/e2e/test_app_queue.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add app.py src/civicpulse/gateway.py tests/e2e/test_app_queue.py
git commit -m "feat: display ranked civic incident queue"
```

### Task 8.2: Add Hotspot Map and Incident Detail Evidence

**Files:**
- Modify: `app.py`
- Create: `tests/e2e/test_app_incident_detail.py`

**Interfaces:**
- Map rows use incident centroid, radius, band, category, and count.
- Detail view reads one selected incident from the service.

**Test area:** UI integration and map-data contract.

**Acceptance scope:**
- Map displays one marker per incident, not every complaint by default.
- Marker size reflects report count and color reflects priority band.
- Detail shows all contributing complaints, timestamps, distances, accepted edges, and priority reasons.
- Connected-component chaining is visible through accepted edges.
- Empty state renders guidance instead of an exception.

- [ ] **Step 1: Write failing map/detail tests**

Assert marker row count, selected incident content, and empty state.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_app_incident_detail.py -v`
Expected: FAIL because map/detail views are absent.

- [ ] **Step 3: Implement PyDeck map and detail panel**

Keep map-row construction in a pure helper tested without browser rendering.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/e2e/test_app_incident_detail.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add app.py tests/e2e/test_app_incident_detail.py
git commit -m "feat: show incident hotspots and supporting evidence"
```

### Task 8.3: Add Live Complaint Submission Form

**Files:**
- Modify: `app.py`
- Create: `tests/e2e/test_app_submission.py`

**Interfaces:**
- Form creates one UUID idempotency key per submitted form state.

**Test area:** UI validation, success update, replay, and model failure.

**Acceptance scope:**
- Form collects text, latitude, longitude, timezone-aware timestamp, and optional photo.
- Invalid input displays field-specific errors and writes nothing.
- Successful submission shows matched/new incident outcome and reasons.
- Queue and detail refresh to the new count.
- Repeated Streamlit rerun does not duplicate the complaint.

- [ ] **Step 1: Write failing AppTest form tests**

Cover invalid coordinates, successful Manglish submission, and repeated rerun.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_app_submission.py -v`
Expected: FAIL because the form is absent.

- [ ] **Step 3: Implement form and stable idempotency state**

Store the pending key in `st.session_state`; replace it only after a terminal success.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/e2e/test_app_submission.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add app.py tests/e2e/test_app_submission.py
git commit -m "feat: submit and cluster live civic complaints"
```

### Task 8.4: Add Filters and Safe Demo Reset

**Files:**
- Modify: `app.py`
- Create: `tests/e2e/test_app_filters_reset.py`

**Interfaces:**
- Filters include category, priority band, and report-time range.
- Reset requires explicit confirmation and calls `reset_seed` once.

**Test area:** UI filter combinations and state-reset integration.

**Acceptance scope:**
- Filters affect queue and map consistently.
- Clearing filters restores all incidents.
- Reset without confirmation changes nothing.
- Confirmed reset restores exact seed count/checksum and clears selected stale incident.

- [ ] **Step 1: Write failing filter/reset tests**

Assert each filter, combined filters, cancelled reset, and confirmed reset.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_app_filters_reset.py -v`
Expected: FAIL because controls are absent.

- [ ] **Step 3: Implement shared filtered view state and confirmation**

Never delete the database file from the UI; reset through the service transaction.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/e2e/test_app_filters_reset.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add app.py tests/e2e/test_app_filters_reset.py
git commit -m "feat: filter incidents and reset demo state safely"
```

## Phase 9 — COMPLETE: Demo Reliability and Performance

**Core MVP — FROZEN FOR DEMO/RELEASE REHEARSAL**

Phase 9 completion is recorded by the separately executed Task 9.1, 9.2, 9.3, and 9.3A
plans plus the versioned performance report. The original checkbox outlines below are retained
as historical planning context; completion status follows the executable plans and verified
repository evidence rather than those superseded draft checkboxes.

### Task 9.1 — COMPLETE: Add Full Core Demo Regression

**Files:**
- Create: `tests/e2e/test_demo_scenario.py`

**Interfaces:**
- Exercises the real service, SQLite, cached model, seed data, and Streamlit app boundary.

**Test area:** End-to-end regression.

**Acceptance scope:**
- Seed dashboard shows at least three hotspots.
- Target blocked-drain incident begins with a known count.
- Submitting `Longkang dekat sekolah blocked lagi, hujan terus air naik.` joins that incident.
- Count increases by one and reasons include report volume, school proximity, and flood-related signal when policy conditions are met.
- No external LLM call occurs.

- [ ] **Step 1: Write failing scenario test**

Use fixed IDs and coordinates from seed data; assert exact before/after membership.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_demo_scenario.py -v`
Expected: FAIL until the integrated behavior is complete.

- [ ] **Step 3: Make only integration fixes exposed by the test**

Do not weaken expected incident membership or priority reasons to obtain a pass.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/e2e/test_demo_scenario.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add tests/e2e/test_demo_scenario.py
git commit -m "test: lock the civicpulse live demo scenario"
```

### Task 9.2 — COMPLETE: Verify Offline, Fault, and Recovery Behavior

**Files:**
- Create: `tests/integration/test_offline_recovery.py`
- Create: `docs/demo-runbook.md`

**Interfaces:**
- Runbook defines prewarm, seed reset, offline start, backup start, and recovery commands.

**Test area:** Fault injection and offline integration.

**Acceptance scope:**
- With model cached and outbound network blocked, seed, dashboard, and submission work.
- Missing model cache fails startup before accepting work and gives the prewarm command.
- Database lock produces a bounded error and no partial write.
- Photo provider outage leaves core health usable.
- Runbook includes `uv sync --frozen`, prewarm, reset, `uv run streamlit run app.py`, tests, and backup screenshot/video checklist.

- [ ] **Step 1: Write failing offline/fault tests**

Monkeypatch network clients to fail, remove only a temporary test cache, and hold a test database lock.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/integration/test_offline_recovery.py -v`
Expected: FAIL until recovery behavior is exposed correctly.

- [ ] **Step 3: Implement bounded error translation and runbook**

Keep original exception causes attached; do not log API keys or complaint photos.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/integration/test_offline_recovery.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add tests/integration/test_offline_recovery.py docs/demo-runbook.md
git commit -m "test: verify offline demo and recovery behavior"
```

### Task 9.3 — COMPLETE: Enforce Demo Performance Budgets

**Files:**
- Create: `tests/integration/test_performance_budget.py`
- Modify: `docs/demo-runbook.md`

**Interfaces:**
- Timed operations are cached recluster, warm submission, reset, and map-row construction.

**Test area:** Resource and performance integration on the reference development machine.

**Acceptance scope:**
- Cached reclustering of 180 complaints completes in at most 3 seconds.
- Warm submission without photo analysis completes in at most 5 seconds.
- Seed reset completes in at most 5 seconds.
- Map-row construction for all incidents completes in at most 500 milliseconds.
- Results record CPU, Python version, model, and complaint count in the runbook.

- [ ] **Step 1: Write performance tests with explicit markers**

Mark tests `performance` so normal unit runs remain fast.

- [ ] **Step 2: Verify the first measured result**

Run: `uv run pytest -m performance tests/integration/test_performance_budget.py -v`
Expected: measured pass or a specific failed budget, not a skipped test.

- [ ] **Step 3: Optimize only the failed measured path**

Prefer embedding/cache reuse and candidate prefiltering; keep O(n²) if it meets the budget.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest -m performance tests/integration/test_performance_budget.py -v`
Expected: PASS on the documented reference machine.

- [ ] **Step 5: Commit boundary**

```powershell
git add tests/integration/test_performance_budget.py docs/demo-runbook.md
git commit -m "perf: enforce civicpulse demo latency budgets"
```

**Phase 9 gate: PASS.** The full non-live suite, offline scenario, and active performance
budgets pass. The core MVP is demo-ready and frozen for rehearsal. Phase 10 may be omitted
without changing that verdict.

**Known repository quality debt:** Repository-wide pre-commit is not currently green.
Task-scoped tests, Pyright, benchmark, performance contracts, and diff checks pass, while
repository-wide Ruff/Pyright/pytest-hook baseline debt is deferred to a separate hygiene phase.

## Phase 10 — OPTIONAL, NON-BLOCKING: Photo Consistency

### Task 10.1: Validate and Store Photo Uploads Safely

**Files:**
- Create: `src/civicpulse/photos.py`
- Create: `tests/unit/test_photos.py`

**Interfaces:**
- Produces `validate_and_store_photo(data: bytes, declared_type: str, upload_dir: Path) -> StoredPhoto`.

**Test area:** File boundary, malformed input, size limit, and filename safety.

**Acceptance scope:**
- Accepts valid JPEG and PNG only.
- Rejects empty, malformed, polyglot-like, and payloads above 5 MiB.
- Verifies format by decoding with Pillow, not by filename or declared MIME alone.
- Re-encodes the image to remove attached metadata.
- Uses a generated UUID filename and never uses the supplied filename.

- [ ] **Step 1: Write failing photo tests**

Generate in-memory valid images and malformed/oversized payloads; assert no file remains after failure.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_photos.py -v`
Expected: FAIL because photo handling is absent.

- [ ] **Step 3: Implement bounded decode and atomic write**

Write to a temporary file under the upload directory and rename only after successful re-encoding.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_photos.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/photos.py tests/unit/test_photos.py
git commit -m "feat: validate and store complaint photos safely"
```

### Task 10.2: Define the Photo Analyzer Contract and Disabled Mode

**Files:**
- Modify: `src/civicpulse/photos.py`
- Create: `tests/unit/test_photo_analyzer.py`

**Interfaces:**
- Produces `PhotoAnalyzer.analyze(photo, complaint_category) -> PhotoAssessment` protocol.
- Produces `DisabledPhotoAnalyzer` and `FakePhotoAnalyzer`.

**Test area:** Provider contract and failure-state semantics.

**Acceptance scope:**
- Status values are `likely_consistent`, `unclear`, `likely_inconsistent`, `unavailable`, and `error`.
- `officer_review_required` is always true.
- Disabled mode returns `unavailable` and never raises.
- Fake analyzer supports deterministic UI and integration tests.
- No status can modify matching or priority inputs.

- [ ] **Step 1: Write failing contract tests**

Assert every status serializes, officer review is mandatory, and disabled mode is safe.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_photo_analyzer.py -v`
Expected: FAIL because the protocol and analyzers are absent.

- [ ] **Step 3: Implement provider-neutral contract**

Keep OpenAI imports out of `photos.py`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/test_photo_analyzer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/photos.py tests/unit/test_photo_analyzer.py
git commit -m "feat: define optional photo consistency contract"
```

### Task 10.3: Implement the OpenAI Vision Adapter

**Files:**
- Create: `src/civicpulse/vision_openai.py`
- Create: `tests/unit/test_vision_openai.py`
- Create: `tests/live/test_vision_openai_live.py`

**Interfaces:**
- Produces `OpenAIPhotoAnalyzer(client, model, timeout_seconds=8.0)`.
- Uses Responses API image input and Pydantic structured output.

**Test area:** Mocked provider contract, timeout/rate-limit/malformed-output faults, and opt-in live smoke test.

**Acceptance scope:**
- Adapter receives model from `OPENAI_VISION_MODEL`; enabled mode fails health when the variable is absent.
- Input uses a base64 data URL after local photo sanitization.
- Structured output contains only status, observed category, and a factual observation of at most 240 characters.
- Client timeout is eight seconds and automatic retries are disabled for the demo.
- Timeout, rate limit, refusal, and schema error return `error` or `unavailable` with sanitized context.
- Unit tests make no network calls; live test runs only with explicit `--run-live` and required environment variables.

- [ ] **Step 1: Write failing mocked adapter tests**

Use a fake Responses client to assert `input_image`, category prompt, parsed output, timeout, and four failure translations.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/test_vision_openai.py -v`
Expected: FAIL because the adapter is absent.

- [ ] **Step 3: Implement from official API patterns**

Use `client.responses.parse(...)`, a Pydantic response model, and an `input_image` data URL. Follow:

- `https://developers.openai.com/api/docs/guides/images-vision`
- `https://developers.openai.com/api/docs/guides/structured-outputs`

- [ ] **Step 4: Verify unit GREEN**

Run: `uv run pytest tests/unit/test_vision_openai.py -v`
Expected: PASS without credentials.

- [ ] **Step 5: Run opt-in live smoke test when credits/key are available**

Run: `uv run pytest --run-live tests/live/test_vision_openai_live.py -v`
Expected: one valid structured assessment or a clearly classified provider availability failure; this is not part of core MVP acceptance.

- [ ] **Step 6: Commit boundary**

```powershell
git add src/civicpulse/vision_openai.py tests/unit/test_vision_openai.py tests/live/test_vision_openai_live.py
git commit -m "feat: add optional openai photo consistency adapter"
```

### Task 10.4: Add Post-Submission Photo Analysis Action

**Files:**
- Modify: `src/civicpulse/service.py`
- Modify: `src/civicpulse/repository.py`
- Modify: `app.py`
- Create: `tests/e2e/test_app_photo_analysis.py`

**Interfaces:**
- Produces `service.analyze_photo(complaint_id) -> PhotoAssessment`.
- Analysis is invoked by an officer button after successful complaint submission.

**Test area:** UI integration, persistence, failure isolation, and core invariance.

**Acceptance scope:**
- Complaint exists before analysis starts.
- Analysis success stores and displays status, observation, model, and time.
- Analysis failure leaves complaint, incident membership, report count, and priority unchanged.
- UI always shows `Officer review required` and never uses `verified`, `authentic`, or `confirmed evidence`.
- Re-analysis creates a new assessment record while retaining history.

- [ ] **Step 1: Write failing UI and service tests with fake analyzer**

Capture incident and priority before success/error analysis and assert exact equality afterward.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_app_photo_analysis.py -v`
Expected: FAIL because the action is absent.

- [ ] **Step 3: Implement separate action and append-only assessment persistence**

Do not call the analyzer inside `submit_complaint`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/e2e/test_app_photo_analysis.py -v`
Expected: PASS.

- [ ] **Step 5: Commit boundary**

```powershell
git add src/civicpulse/service.py src/civicpulse/repository.py app.py tests/e2e/test_app_photo_analysis.py
git commit -m "feat: analyze photos without blocking civic triage"
```

## Final Verification Gate

- [ ] Run formatting and static checks:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run pyright src scripts tests
```

- [ ] Run all non-live tests:

```powershell
uv run pytest -m "not live" -v
```

- [ ] Run the hybrid quality gate:

```powershell
uv run python scripts/run_hybrid_benchmark.py
```

- [ ] Run performance checks:

```powershell
uv run pytest -m performance tests/integration/test_performance_budget.py -v
```

- [ ] Run offline demo from reset state:

```powershell
uv run python scripts/prewarm_model.py
uv run streamlit run app.py
```

- [ ] Run the FastAPI adapter smoke test separately:

```powershell
uv run uvicorn civicpulse.api:create_default_app --factory --host 127.0.0.1 --port 8000
```

- [ ] Run configured repository hooks:

```powershell
uv run pre-commit run --all-files
```

- [ ] Confirm final acceptance:

1. hybrid holdout has zero false automatic merges and zero positive `no_match` decisions;
2. 120-180 seed complaints form at least three visible hotspots;
3. live Manglish submission updates the intended incident exactly once;
4. every incident shows grouping evidence and priority reasons;
5. the core demo succeeds without internet and without OpenAI credentials;
6. optional photo failure cannot alter core state;
7. all non-live tests, Ruff checks, and performance budgets pass;
8. UI and documentation identify synthetic data and prototype policy parameters.

## Post-MVP TypeScript Frontend Decision

Do not build Streamlit and Next.js in parallel. After the final core gate passes, create a separate implementation plan for a TypeScript client only if the project is continuing as a portfolio product. That plan must consume `docs/api/openapi.json` through generated types/client code and should use Next.js, MapLibre or Leaflet, TanStack Query, and Zod at browser-only boundaries. It must not manually redefine `Complaint`, `IncidentSummary`, `PriorityLevel`, or category enums.

Keep Streamlit when rapid demonstration and one-command local execution remain the priority. Move to Next.js when custom map/list interaction, product-grade layout, or independent frontend deployment is worth the second runtime and additional contract/E2E tests.

## Implementation Stop Rules

- Stop before Phase 3 if the hybrid holdout gate fails.
- Stop dashboard expansion if service idempotency or atomic cluster replacement tests fail.
- Stop demo-readiness claims if offline or performance gates fail.
- Omit Phase 10 if core MVP gates are not complete; photo analysis is never allowed to consume time required for core reliability.
