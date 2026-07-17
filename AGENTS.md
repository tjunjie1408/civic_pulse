# Repository Guidelines

## Project Structure

- `src/civicpulse/`: typed domain models and core logic for normalization, matching, location extraction, clustering, priority policy, persistence, and service orchestration.
- `tests/unit/`: focused deterministic tests for domain and algorithms.
- `tests/integration/`: SQLite, submission-service, and benchmark integration tests.
- `benchmarks/`: frozen multilingual complaint pairs, metadata, manifests, and generated reports.
- `config/`: versioned matching, normalization, and priority policies.
- `data/`: synthetic sensitive-location fixtures and future seed data.
- `scripts/`: runnable benchmark and maintenance commands.
- `docs/`: design specifications and implementation plans.

## Build, Test, and Development Commands

Use Python 3.12 through `uv` and the repository `.venv`:

```powershell
uv sync --offline
uv run --offline python -m pytest tests/unit tests/integration -q
uv run --offline pyright src scripts
uv run --offline python -m scripts.run_hybrid_benchmark
uv run --offline pre-commit run --all-files
```

The benchmark command is a quality gate; inspect its exit code and report before changing matching policy.

## Coding Style & Naming

Use four spaces, Python type annotations, and small pure functions. Keep Pydantic models strict (`extra="forbid"`) and use `snake_case` for modules, functions, and fields; use `PascalCase` for classes and `UPPER_SNAKE_CASE` for constants. Ruff enforces the configured E/F/I/B/UP/SIM/RUF/ANN rules with a 100-character line limit. Pyright runs in strict mode.

Preserve the uncertainty boundary: `AUTO_MATCH` may form confirmed incidents, `REVIEW_REQUIRED` is candidate evidence only, and `NO_MATCH` is excluded. Priority must use confirmed evidence only.

## Testing Guidelines

Name tests `test_<behavior>.py` and test functions `test_<expected_result>`. Add unit tests for pure logic and integration tests for SQLite/service boundaries. Changes to matching, clustering, or priority must include negative/conflict cases and rerun the full suite, Pyright, and the hybrid benchmark.

## Commit & Pull Requests

Use concise imperative Conventional Commit-style subjects, matching history such as `feat: ...` and `test: ...`. Keep commits focused. Pull requests should explain the behavior change, list verification commands and benchmark results, identify policy/config changes, and call out remaining uncertainty. Do not include secrets, API keys, generated databases, or model caches.

## Architecture Notes

Incident IDs are membership-derived snapshot identifiers, not permanent case IDs. `review_candidate_ids` is an index derived from full candidate relationships. The SCM-inspired priority layer is a transparent policy model, not causal discovery; keep future risk-propagation work separate from incident resolution.
