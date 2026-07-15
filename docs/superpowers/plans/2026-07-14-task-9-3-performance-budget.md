# Task 9.3 Performance Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Establish repeatable, environment-labelled performance evidence for the cached offline CivicPulse runtime and publish prototype budgets for startup, reads, mutations, reset, memory, and Dashboard responsiveness.

**Architecture:** Keep correctness tests and wall-clock performance measurements separate. A versioned JSON budget is loaded by an explicit performance harness that builds the real cached runtime, performs warm-ups, records raw samples, computes p50/p95/max and RSS growth, and emits JSON plus Markdown reports. Hard-budget failures exit non-zero; informational cold-start and platform-noise measurements are reported without blocking.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI/httpx, SQLite, Streamlit/browser smoke, sentence-transformers cached model, pytest performance marker, Pyright strict, Ruff, uv offline.

## Global Constraints

- Record OS, CPU, RAM, Python version, model, seed size, SQLite backend, offline mode, warm-up count, measured-run count, measurement method, timestamp, and git commit.
- Runtime measurements use HF_HUB_OFFLINE=1 and the cached model; first-ever download is informational only.
- Hard gates are application composition, warm readiness, cold cached-model initialization, incident-list p95, incident-detail p95, complaint-submission p95, review-resolution p95, deterministic reset duration, steady-state RSS, 20-mutation RSS growth, and Dashboard first usable render.
- Informational metrics are cold start including model import/download, Streamlit rerun variance, Windows filesystem/cache noise, and one-off vacuum or antivirus interference.
- Initial budgets: application composition <=5 s; warm readiness <=2 s; cold cached-model initialization <=25 s; incident-list p95 <=250 ms; incident-detail p95 <=200 ms; submission p95 <=2.5 s where the aggregate is the maximum of the three submission scenarios; review resolution p95 <=2.0 s where the aggregate is the maximum of approve/reject/merge; reset <=45 s; API ready RSS <=1536 MB; 20-mutation growth <=15%; Dashboard first usable render <=5 s after API readiness. The previous eight-second budget mixed application startup with first local Transformer initialization and is retained only as historical context.
- Incident-list fixtures contain 60 persisted incidents, use limit=50/default sorting, and run against a warm SQLite cache.
- Submission samples include isolated, clear auto-match, and review-required paths. Review samples include approve, reject, and approve-causing-merge.
- Reset timing includes seed validation, embedding reuse/load, matching, clustering, priority, and atomic replacement; the report states whether embeddings were regenerated.
- No optimization is added unless stable measurements identify a concrete budget breach. Full correctness tests and the hybrid benchmark remain quality gates.

## File Map

- Create: \`config/performance_budget.json\` — versioned thresholds.
- Create: \`src/civicpulse/performance.py\` — typed budget, environment, sample, percentile, RSS, and report models/functions.
- Create: \`scripts/run_performance_budget.py\` — explicit offline harness and CLI.
- Create: \`tests/unit/test_performance.py\` — deterministic statistics, budget, RSS-growth, and schema tests.
- Create: \`tests/performance/test_performance_contract.py\` — opt-in real cached-runtime contract tests marked \`performance\`.
- Create: \`docs/performance-report.md\` — concise checked-in reference report; raw samples remain in \`benchmarks/reports/performance-budget.json\`.
- Modify: \`README.md\` — command, report, hard/informational budget boundary.
- Verify/modify: \`pyproject.toml\` — register the strict \`performance\` marker if it is not already present.

---

### Task 1: Version the performance budget and typed measurement contract

**Files:** Create \`config/performance_budget.json\`, \`src/civicpulse/performance.py\`, and \`tests/unit/test_performance.py\`.

**Interfaces:**

- \`PerformanceBudget.load(path: Path) -> PerformanceBudget\`, including \`warmup_runs\`, \`measured_runs\`, \`startup_runs\`, \`reset_runs\`, and \`dashboard_runs\`.
- \`MeasurementEnvironment\` stores \`os\`, \`cpu\`, \`ram_mb\`, \`python_version\`, \`model_name\`, \`seed_size\`, \`database_backend\`, \`offline_mode\`, \`warmup_runs\`, \`measured_runs\`, and \`measurement_method\`.
- \`summarize(samples: Sequence[float]) -> MetricSummary\` returns count, p50, p95, maximum using deterministic nearest-rank selection.
- \`evaluate_budget(budget, summaries, rss_growth_percent) -> BudgetEvaluation\` explicitly maps \`submission_p95_ms = max(submission_isolated_p95_ms, submission_auto_match_p95_ms, submission_review_required_p95_ms)\` and \`review_resolution_p95_ms = max(review_approve_p95_ms, review_reject_p95_ms, review_merge_p95_ms)\` before applying aggregate thresholds.
- \`PerformanceReport\` serializes environment, budget version, timestamp, git commit, raw samples, summaries, RSS baselines/growth, evaluations, and known noise.

- [x] **Step 1: Write failing schema/statistics tests.**

~~~python
def test_p95_uses_deterministic_nearest_rank() -> None:
    assert summarize([10, 20, 30, 40]).p95 == 40


def test_hard_breach_fails_but_informational_breach_does_not() -> None:
    evaluation = evaluate_budget(
        load_budget("config/performance_budget.json"),
        {"incident_list_p95_ms": MetricSummary(count=3, p50=200, p95=300, maximum=300),
         "cold_start_ms": MetricSummary(count=3, p50=9000, p95=9000, maximum=9000)},
        rss_growth_percent=0.0,
    )
    assert evaluation.passed is False
    assert evaluation.metrics["incident_list_p95_ms"].hard is True
    assert evaluation.metrics["cold_start_ms"].hard is False
~~~

- [x] **Step 2: Run RED.**

~~~powershell
uv run --offline python -m pytest tests/unit/test_performance.py -q
~~~

Expected: failures because the models, loader, percentile rule, and evaluator do not exist.

- [x] **Step 3: Add the strict budget file and minimal implementation.**

~~~json
{
  "budget_version": "prototype-1",
  "warmup_runs": 3,
  "measured_runs": 20,
  "startup_runs": 5,
  "reset_runs": 5,
  "dashboard_runs": 5,
  "application_composition_seconds_max": 5.0,
  "warm_readiness_seconds_max": 2.0,
  "cold_cached_model_initialization_seconds_max": 25.0,
  "incident_list_p95_ms_max": 250.0,
  "incident_detail_p95_ms_max": 200.0,
  "submission_p95_ms_max": 2500.0,
  "review_resolution_p95_ms_max": 2000.0,
  "reset_seconds_max": 45.0,
  "ready_rss_mb_max": 1536.0,
  "mutation_memory_growth_percent_max": 15.0,
  "dashboard_first_usable_seconds_max": 5.0
}
~~~

Use strict Pydantic models, reject unknown budget fields, and map every metric to a hard or informational status explicitly. Keep this module free of process/network side effects on import.

- [x] **Step 4: Run GREEN and static checks.**

~~~powershell
uv run --offline python -m pytest tests/unit/test_performance.py -q
uv run --offline pyright src/civicpulse/performance.py tests/unit/test_performance.py
uv run --offline ruff check src/civicpulse/performance.py tests/unit/test_performance.py
~~~

---

### Task 2: Build the deterministic offline measurement harness

**Files:** Create \`scripts/run_performance_budget.py\`; test \`tests/performance/test_performance_contract.py\`; verify/modify \`pyproject.toml\` marker registration.

**Interfaces:**

- \`run_performance_budget(*, budget_path: Path, output_json: Path, output_markdown: Path | None, offline: bool = True) -> PerformanceReport\` loads per-metric run counts from the budget.
- CLI flags: \`--budget\`, \`--output-json\`, \`--output-markdown\`, \`--warmups\`, \`--runs\`, \`--startup-runs\`, \`--reset-runs\`, \`--dashboard-runs\`, \`--seed\`, \`--offline\`, and \`--write-reference-report\`.
- Exit code 0 means completed and all hard gates passed; 1 means completed with a hard-gate breach; 2 means incomplete measurement/configuration/infrastructure failure.
- A subprocess helper starts and reliably terminates child API/Dashboard processes, polls readiness/observable usability, captures child exit status, and cleans ports, browser contexts, and temporary databases.
- The harness uses a disposable SQLite database and existing runtime composition; it never mutates the checked-in database or downloads a model.

- [x] **Step 1: Write a command-contract test.** With a fake clock/provider seam, assert the emitted JSON includes environment fields, raw sample counts, summaries, and \`hard_gate_passed\`; assert \`--offline\` reaches runtime composition.
- [x] **Step 2: Run RED.**

~~~powershell
uv run --offline python -m pytest tests/performance/test_performance_contract.py -q
~~~

Expected: failure because the harness and report writer do not exist.

- [x] **Step 3: Implement fixture setup and timing.** Set \`HF_HUB_OFFLINE=1\`, load \`config/matching_policy.json\`, seed exactly 120 complaints through the existing reset path, and use \`time.perf_counter()\` around only declared operation boundaries. Use 20 runs for list/detail/submission/review, 5 fresh subprocess runs for cached readiness, 5 reset runs, and 5 Dashboard runs. Record cold start in separate subprocesses as informational and exclude first-ever download.
- [x] **Step 4: Implement report and exit behavior.** JSON is the source of truth and contains all raw samples; Markdown contains concise summaries and a link stating `Raw samples are retained in benchmarks/reports/performance-budget.json.` Only `--write-reference-report` may overwrite the checked-in reference paths. Record `measurement_status` as `completed` or `incomplete`, and set `hard_gate_passed` to true/false/null accordingly.
- [x] **Step 5: Run focused checks.**

~~~powershell
uv run --offline python -m pytest tests/performance/test_performance_contract.py -q
uv run --offline pyright scripts/run_performance_budget.py
uv run --offline ruff check scripts/run_performance_budget.py tests/performance/test_performance_contract.py
~~~

---

### Task 3: Measure cached API startup, reads, submissions, reviews, and reset

**Files:** Modify \`scripts/run_performance_budget.py\`; extend \`tests/performance/test_performance_contract.py\`.

**Interfaces:** Use existing \`compose_runtime()\`/\`create_app()\`, TestClient or in-process HTTP, \`IncidentQueryService.list_incidents(IncidentListQuery(limit=50, offset=0))\`, submission routes, review approve/reject routes, and the admin reset route. Do not introduce alternate production paths.

- [x] **Step 1: Add failing assertions for exact labels.** Require \`application_composition_seconds\`, \`warm_readiness_seconds\`, \`cold_cached_model_initialization_seconds\`, \`incident_list_p95_ms\`, \`incident_detail_p95_ms\`, \`submission_isolated_p95_ms\`, \`submission_auto_match_p95_ms\`, \`submission_review_required_p95_ms\`, \`review_approve_p95_ms\`, \`review_reject_p95_ms\`, \`review_merge_p95_ms\`, and \`reset_seconds\`.
- [x] **Step 2: Run the contract test and confirm missing labels fail.**
- [x] **Step 3: Implement exact boundaries.** Fresh API runs record process-to-ready as historical cold-path context, warm readiness as a timed health request after the first ready response, application composition from startup spans excluding model provider load and the first readiness encode, and cold cached-model initialization from the model-load plus one-time probe spans. Incident list uses 60 incidents, warm SQLite, limit 50, and default sorting. For each measured submission/review sample, reset to deterministic seed, warm required caches, execute exactly one mutation, and exclude reset time. Use independent pending-review fixtures for approve, reject, and merge.
- [x] **Step 3a: Implement explicit aggregate gate mapping.** Preserve all scenario summaries in the report, then set `submission_p95_ms` to the maximum of isolated/auto-match/review-required p95 values and `review_resolution_p95_ms` to the maximum of approve/reject/merge p95 values before applying the single budget threshold for each aggregate.
- [x] **Step 4: Run and inspect the focused test before any optimization.**

~~~powershell
uv run --offline python -m pytest tests/performance/test_performance_contract.py -q
~~~

---

### Task 4: Add RSS and Dashboard user-visible timing evidence

**Files:** Modify \`scripts/run_performance_budget.py\`; extend \`tests/performance/test_performance_contract.py\`; add a small browser timing helper under \`tests/performance/\` only if existing Dashboard smoke conventions require it.

**Interfaces:**

- \`read_process_rss_mb(pid: int) -> float\` reads \`psutil.Process(pid).memory_info().rss\`; add the supported psutil dependency if it is not already present.
- Report fields: API-process \`idle_rss_mb\`, \`ready_rss_mb\`, \`post_reset_rss_mb\`, \`post_20_mutations_rss_mb\`, \`mutation_memory_growth_percent\`, and informational \`mutation_memory_growth_mb\`; Dashboard RSS is separate and informational.
- Dashboard timing is wall-clock: process start -> root response -> API readiness -> stable `CivicPulse operational queue ready` marker visible. Record process-to-response and process-to-queue separately; only the latter is the hard gate.

- [x] **Step 1: Add failing RSS baseline/growth tests.** Verify ready RSS is sampled after model load and growth is \`(post_20 - ready) / ready * 100\`.
- [x] **Step 2: Run RED.**
- [x] **Step 3: Implement RSS sampling and Dashboard smoke timing.** Add the stable operational-queue marker in the Dashboard page if no existing observable signal is available. Clean Streamlit process, browser context, temporary database, and port after every run. Label Streamlit reruns, Windows filesystem/cache noise, and vacuum/Defender delays under \`known_noise_sources\`; do not turn them into hard failures.
- [x] **Step 4: Run focused tests and static checks.**

~~~powershell
uv run --offline python -m pytest tests/performance/test_performance_contract.py -q
uv run --offline pyright scripts/run_performance_budget.py
uv run --offline ruff check scripts/run_performance_budget.py tests/performance/test_performance_contract.py
~~~

---

### Task 5: Generate and document the reference report

**Files:** Create \`docs/performance-report.md\`; modify \`README.md\`; extend \`tests/contract/test_documentation_boundaries.py\`.

- [x] **Step 1: Add a documentation contract test.** Require the Markdown environment summary, budget version, timestamp, git commit and dirty state, p50/p95/max, RSS baseline/growth, hard/informational status, known noise, a link to `benchmarks/reports/performance-budget.json`, and the sentence: \`No optimization was performed where the measured result already met budget.\` The JSON contract, not Markdown, owns raw sample arrays.
- [x] **Step 2: Run RED.**
- [x] **Step 3: Run the real offline harness.**

~~~powershell
$env:HF_HUB_OFFLINE = "1"
uv run --offline python -m scripts.run_performance_budget --offline --write-reference-report --output-json benchmarks/reports/performance-budget.json --output-markdown docs/performance-report.md
~~~

The command records the reference environment and preserves raw samples. If a hard gate fails, document the observed breach and evidence-backed remediation decision; do not silently edit thresholds. Ordinary local runs must write user-specified temporary output and must not overwrite the checked-in reference report.

- [x] **Step 4: Update README.** Link the report and document the command, hard-gate behavior, informational metrics, and that cold-start/download numbers are not production SLA claims.
- [x] **Step 5: Run report and documentation tests.**

~~~powershell
uv run --offline python -m pytest tests/unit/test_performance.py tests/performance/test_performance_contract.py tests/contract/test_documentation_boundaries.py -q
~~~

---

### Task 6: Task 9.3 quality gate and handoff

**Files:** No new production files; update the plan/report only when evidence requires it.

- [x] **Step 1: Run correctness regression.**

~~~powershell
uv run --offline python -m pytest -m "not live and not performance" -q
~~~

- [x] **Step 2: Run static checks.**

~~~powershell
uv run --offline pyright src scripts
uv run --offline ruff check src/civicpulse/performance.py scripts/run_performance_budget.py tests/unit/test_performance.py tests/performance/test_performance_contract.py
~~~

- [x] **Step 3: Run the unchanged hybrid benchmark.**

~~~powershell
uv run --offline python -m scripts.run_hybrid_benchmark
~~~

- [x] **Step 4: Re-run the harness from a clean disposable database.** Confirm the same metadata, raw sample count, hard-gate result, and report paths.
- [x] **Step 4a: Run the opt-in performance suite separately.**

~~~powershell
uv run --offline python -m pytest -m performance tests/performance -q
~~~

- [x] **Step 4b: Compare repeated reports structurally, not byte-for-byte.** Environment structure and budget version must match; raw sample counts and metric labels must match; gate calculation must be reproducible; timestamps may change; `git_commit` should match for the same worktree and `git_dirty` must be recorded.
- [x] **Step 5: Review every breach for stability before changing code.** A breach is actionable only when repeated samples identify a concrete path; if all hard gates pass, record that no optimization was performed.
- [x] **Step 6: Run final repository checks.**

~~~powershell
git diff --check
git status --short
git diff --name-only
~~~

Expected: Task 9.3 files only in intended scope, report generated, all hard budgets explicitly pass/fail, correctness and hybrid benchmark green, and no unrelated files staged.

## Self-Review Checklist

- [x] Every hard metric has a versioned threshold, exact measurement boundary, raw samples, p50/p95/max, and pass/fail result.
- [x] Informational cold-start and Windows noise are reported but cannot block the phase.
- [x] Memory includes idle, ready, post-reset, and post-20-mutation observations plus growth percentage.
- [x] Dashboard timing is user-visible wall clock, not a false nanosecond microbenchmark.
- [x] The harness is explicit, offline-first, repeatable, and separate from ordinary pytest correctness runs.
- [x] No optimization is introduced without a stable measured breach.
