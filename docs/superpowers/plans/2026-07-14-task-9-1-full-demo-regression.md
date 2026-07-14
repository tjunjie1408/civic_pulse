# Task 9.1 Full Core Demo Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the missing production runtime composition entrypoint and lock the complete seeded demo workflow through the real FastAPI boundary, cached multilingual embedding model, SQLite persistence, conservative review queue, officer approval, incident refresh, and priority explanations.

**Architecture:** Add a narrow composition root in `civicpulse.runtime` while keeping `civicpulse.api.app.create_app()` injection-only for contract tests and OpenAPI generation. The runtime initializes an empty database from the server-owned seed, preserves existing state on restart, loads synthetic sensitive locations, and injects one shared repository/service/query stack into FastAPI. The end-to-end regression uses the real cached embedding provider and follows the safe uncertainty boundary: the specified Manglish complaint is submitted with the Dashboard's explicit `blocked_drain` category, remains review evidence when automatic evidence is insufficient, and joins the intended seed incident only after officer approval.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI TestClient, SQLite, sentence-transformers, Streamlit's existing typed HTTP contracts, pytest, Pyright strict, Ruff.

## Global Constraints

- Do not change matching thresholds, location compatibility rules, category constraints, or the hybrid benchmark dataset to force this scenario to auto-match.
- `AUTO_MATCH` alone forms confirmed membership; `REVIEW_REQUIRED` remains candidate evidence until an officer resolves it.
- Priority must use confirmed complaints only; pending candidates never increase confirmed count or priority.
- The runtime may initialize the deterministic seed only when the database has no complaints. Restarting a non-empty database must preserve submissions and review decisions.
- The Dashboard remains an HTTP client and must not import `civicpulse.runtime`, repositories, services, SQLite, or domain models.
- The server owns policy, seed, sensitive-location, and database paths. No API request may supply a filesystem path.
- The default admin reset remains disabled.
- The Task 9.1 scenario requires the embedding model to be prewarmed. Network-blocked and missing-cache behavior belongs to Task 9.2.
- No OpenAI or photo-provider call is part of the core scenario.
- Incident IDs are membership-derived snapshot IDs. Tests must follow API-provided previous/current IDs instead of assuming a permanent case ID.
- Use fixed seed IDs, coordinates, report timestamps, and idempotency keys. Do not assert ordering unless the API contract defines it.

## Evidence That Governs This Plan

- Fresh Phase 8 gate before planning: `180 passed`, Pyright clean, Dashboard Ruff clean, hybrid gate passed with zero false automatic merges and `0.75` clear-positive auto rate.
- `master` and `origin/master` were synchronized at README commit `2fe819b`.
- `create_app()` currently stores injected dependencies but deliberately performs no runtime construction.
- The committed seed contains 120 complaints and currently produces 75 conservative incident snapshots with the real cached model.
- A disposable real-model probe showed the exact text `Longkang dekat sekolah blocked lagi, hujan terus air naik.` is classified as `flooding` when category is omitted.
- With the Dashboard-supported explicit category `blocked_drain`, the same text stays isolated and produces `REVIEW_REQUIRED` edges because similarity is approximately `0.846-0.847`, below the `0.880` threshold, and comparable location entities are incomplete.
- Therefore, direct automatic joining would violate the uncertainty boundary. The executable scenario must submit, locate the intended review, approve it, and then verify confirmed membership.
- `data/sensitive_locations.json` still uses the older Taman Maju coordinates near `3.1390, 101.6869`; it does not describe the current Seksyen Harmoni seed near `3.0801, 101.5185`.
- A disposable full-seed probe exposed `ReviewStale` while resolving a newly surfaced candidate. Treat this as the expected first integration failure. Fix review freshness; never disable or bypass stale-review protection.

---

### Task 1: Add strict runtime settings and sensitive-location loading

**Files:**
- Create: `src/civicpulse/runtime.py`
- Create: `tests/integration/test_runtime_composition.py`

**Interfaces:**
- Produces immutable `RuntimeSettings` with `database_path`, `matching_policy_path`, `priority_policy_path`, `seed_path`, `sensitive_locations_path`, and `admin_reset_enabled`.
- Produces `RuntimeSettings.from_environment(environ: Mapping[str, str] | None = None) -> RuntimeSettings`.
- Produces `load_sensitive_locations(path: str | Path) -> tuple[SensitiveLocation, ...]`.
- Environment variables are `CIVICPULSE_DB_PATH`, `CIVICPULSE_MATCHING_POLICY_PATH`, `CIVICPULSE_PRIORITY_POLICY_PATH`, `CIVICPULSE_SEED_PATH`, `CIVICPULSE_SENSITIVE_LOCATIONS_PATH`, and `CIVICPULSE_ADMIN_RESET_ENABLED`.

- [ ] **Step 1: Write failing settings and loader tests**

Add these cases to `tests/integration/test_runtime_composition.py`:

```python
import json
from pathlib import Path

import pytest

from civicpulse.runtime import RuntimeSettings, load_sensitive_locations


def test_runtime_settings_read_server_owned_paths_and_safe_reset_flag(tmp_path: Path) -> None:
    settings = RuntimeSettings.from_environment(
        {
            "CIVICPULSE_DB_PATH": str(tmp_path / "demo.db"),
            "CIVICPULSE_SEED_PATH": "approved/seed.json",
            "CIVICPULSE_SENSITIVE_LOCATIONS_PATH": "approved/locations.json",
            "CIVICPULSE_ADMIN_RESET_ENABLED": "true",
        }
    )

    assert settings.database_path == tmp_path / "demo.db"
    assert settings.seed_path == Path("approved/seed.json")
    assert settings.sensitive_locations_path == Path("approved/locations.json")
    assert settings.admin_reset_enabled is True


def test_runtime_settings_reject_invalid_boolean() -> None:
    with pytest.raises(ValueError, match="CIVICPULSE_ADMIN_RESET_ENABLED"):
        RuntimeSettings.from_environment({"CIVICPULSE_ADMIN_RESET_ENABLED": "sometimes"})


def test_sensitive_location_loader_is_strict_and_names_the_path(tmp_path: Path) -> None:
    path = tmp_path / "locations.json"
    path.write_text(json.dumps([{"id": "school", "kind": "school", "latitude": 91, "longitude": 1}]), encoding="utf-8")

    with pytest.raises(ValueError, match="locations.json"):
        load_sensitive_locations(path)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
uv run --offline python -m pytest tests/integration/test_runtime_composition.py -v
```

Expected: collection fails because `civicpulse.runtime` does not exist.

- [ ] **Step 3: Implement the settings and loader at the top of `src/civicpulse/runtime.py`**

Use this exact shape:

```python
"""Production composition root for the local CivicPulse demo."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from civicpulse.domain import SensitiveLocation


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database_path: Path = Path("data/civicpulse.db")
    matching_policy_path: Path = Path("config/matching_policy.json")
    priority_policy_path: Path = Path("config/priority_policy.json")
    seed_path: Path = Path("data/seed_complaints.json")
    sensitive_locations_path: Path = Path("data/sensitive_locations.json")
    admin_reset_enabled: bool = False

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> RuntimeSettings:
        source = os.environ if environ is None else environ
        raw_reset = source.get("CIVICPULSE_ADMIN_RESET_ENABLED", "false").casefold()
        if raw_reset not in {"true", "false", "1", "0"}:
            raise ValueError(
                "CIVICPULSE_ADMIN_RESET_ENABLED must be true, false, 1, or 0"
            )
        return cls(
            database_path=Path(source.get("CIVICPULSE_DB_PATH", "data/civicpulse.db")),
            matching_policy_path=Path(
                source.get("CIVICPULSE_MATCHING_POLICY_PATH", "config/matching_policy.json")
            ),
            priority_policy_path=Path(
                source.get("CIVICPULSE_PRIORITY_POLICY_PATH", "config/priority_policy.json")
            ),
            seed_path=Path(source.get("CIVICPULSE_SEED_PATH", "data/seed_complaints.json")),
            sensitive_locations_path=Path(
                source.get(
                    "CIVICPULSE_SENSITIVE_LOCATIONS_PATH",
                    "data/sensitive_locations.json",
                )
            ),
            admin_reset_enabled=raw_reset in {"true", "1"},
        )


_SENSITIVE_LOCATIONS = TypeAdapter(tuple[SensitiveLocation, ...])


def load_sensitive_locations(path: str | Path) -> tuple[SensitiveLocation, ...]:
    resolved = Path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        locations = _SENSITIVE_LOCATIONS.validate_python(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid sensitive-location fixture: {resolved}") from exc
    if not locations:
        raise ValueError(f"sensitive-location fixture is empty: {resolved}")
    return locations
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command. Expected: all three tests pass.

- [ ] **Step 5: Run strict static checks on the new module**

Run:

```powershell
uv run --offline pyright src/civicpulse/runtime.py
uv run --offline ruff check src/civicpulse/runtime.py tests/integration/test_runtime_composition.py
```

Expected: no errors.

---

### Task 2: Compose the real runtime without resetting existing state

**Files:**
- Modify: `src/civicpulse/runtime.py`
- Modify: `tests/integration/test_runtime_composition.py`

**Interfaces:**
- Produces frozen `RuntimeBundle` containing `settings`, `repository`, `service`, `incident_query_service`, and `app`.
- Produces `build_runtime(settings: RuntimeSettings | None = None, *, embedding_provider: EmbeddingProvider | None = None) -> RuntimeBundle`.
- Produces Uvicorn factory `create_runtime_app() -> FastAPI`.
- `build_runtime()` loads policies and sensitive locations once, initializes the SQLite schema, seeds only an empty complaint table, and injects the same objects into `create_app()`.

- [ ] **Step 1: Add failing composition and restart-preservation tests**

Add a deterministic 384-dimensional fake provider and these assertions:

```python
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from civicpulse.api.dto.complaints import ComplaintCreateRequest
from civicpulse.runtime import RuntimeSettings, build_runtime


class FakeProvider:
    model_name = "intfloat/multilingual-e5-small"
    normalization_version = "normalization-v1"

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, *([0.0] * 383)) for _ in texts)


def runtime_settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        database_path=tmp_path / "civicpulse.db",
        seed_path=Path("data/seed_complaints.json"),
        sensitive_locations_path=Path("data/sensitive_locations.json"),
    )


def test_runtime_composes_ready_api_from_empty_database(tmp_path: Path) -> None:
    runtime = build_runtime(runtime_settings(tmp_path), embedding_provider=FakeProvider())
    response = TestClient(runtime.app).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["core_ready"] is True
    assert len(runtime.repository.list_complaints()) == 120
    assert runtime.app.state.service is runtime.service
    assert runtime.app.state.repository is runtime.repository
    assert runtime.app.state.incident_query_service is runtime.incident_query_service


def test_runtime_restart_preserves_non_empty_state(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path)
    first = build_runtime(settings, embedding_provider=FakeProvider())
    response = TestClient(first.app).post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "runtime-restart"},
        json=ComplaintCreateRequest(
            text="Blocked drain at Block A",
            category="blocked_drain",
            latitude=3.08011,
            longitude=101.51847,
            reported_at=datetime(2026, 7, 11, 8, tzinfo=UTC),
        ).model_dump(mode="json"),
    )
    assert response.status_code == 201

    restarted = build_runtime(settings, embedding_provider=FakeProvider())

    assert len(restarted.repository.list_complaints()) == 121
```

- [ ] **Step 2: Run the two new tests and verify RED**

Run:

```powershell
uv run --offline python -m pytest tests/integration/test_runtime_composition.py -v
```

Expected: failure because `RuntimeBundle`, `build_runtime`, and `create_runtime_app` do not exist.

- [ ] **Step 3: Add the composition implementation below the loader**

Implement this exact object graph:

```python
from dataclasses import dataclass

from fastapi import FastAPI

from civicpulse.api.app import AppSettings, create_app
from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.embeddings import EmbeddingProvider, SentenceTransformerProvider
from civicpulse.incident_query import IncidentQueryService
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService


@dataclass(frozen=True, slots=True)
class RuntimeBundle:
    settings: RuntimeSettings
    repository: SQLiteRepository
    service: CivicPulseService
    incident_query_service: IncidentQueryService
    app: FastAPI


def build_runtime(
    settings: RuntimeSettings | None = None,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> RuntimeBundle:
    resolved = settings or RuntimeSettings.from_environment()
    matching_policy = load_matching_policy(resolved.matching_policy_path)
    priority_policy = load_priority_policy(resolved.priority_policy_path)
    sensitive_locations = load_sensitive_locations(resolved.sensitive_locations_path)
    repository = SQLiteRepository(resolved.database_path)
    repository.initialize()
    provider = embedding_provider or SentenceTransformerProvider(
        matching_policy.model_name,
        matching_policy.normalization_version,
    )
    service = CivicPulseService(
        repository,
        matching_policy,
        priority_policy,
        provider,
        sensitive_locations,
    )
    if not repository.list_complaints():
        service.initialize_seed(resolved.seed_path)
    incident_query_service = IncidentQueryService(
        repository,
        priority_policy,
        sensitive_locations,
    )
    app = create_app(
        AppSettings(
            admin_reset_enabled=resolved.admin_reset_enabled,
            seed_path=str(resolved.seed_path),
        ),
        service=service,
        repository=repository,
        health_service=service.health,
        incident_query_service=incident_query_service,
    )
    return RuntimeBundle(
        settings=resolved,
        repository=repository,
        service=service,
        incident_query_service=incident_query_service,
        app=app,
    )


def create_runtime_app() -> FastAPI:
    return build_runtime().app
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all runtime composition tests pass.

- [ ] **Step 5: Verify that injection-only API construction remains unchanged**

Run:

```powershell
uv run --offline python -m pytest tests/contract/test_api_boundary.py tests/contract/test_openapi_freeze.py -v
```

Expected: pass; OpenAPI construction must not load the model or seed.

---

### Task 3: Align synthetic sensitive locations with the current demo geography

**Files:**
- Modify: `data/sensitive_locations.json`
- Modify: `tests/integration/test_runtime_composition.py`

**Interfaces:**
- The fixture contains a synthetic school at the Seksyen Harmoni blocked-drain cluster and a synthetic hospital at Taman Seri Murni.
- Every location ID starts with `synthetic-` to prevent accidental presentation as live municipal data.

- [ ] **Step 1: Add a failing geography assertion**

```python
from civicpulse.geo import haversine_metres


def test_demo_sensitive_locations_align_with_current_synthetic_seed() -> None:
    locations = load_sensitive_locations("data/sensitive_locations.json")
    school = next(item for item in locations if item.kind == "school")

    assert all(item.id.startswith("synthetic-") for item in locations)
    assert haversine_metres(
        school.latitude,
        school.longitude,
        3.08011,
        101.51847,
    ) <= 250
```

- [ ] **Step 2: Run the geography assertion and verify RED**

Run:

```powershell
uv run --offline python -m pytest tests/integration/test_runtime_composition.py::test_demo_sensitive_locations_align_with_current_synthetic_seed -v
```

Expected: fail because the current school is approximately at `3.1390, 101.6869` and its ID is not explicitly synthetic.

- [ ] **Step 3: Replace the fixture with current synthetic coordinates**

```json
[
  {
    "id": "synthetic-school-seksyen-harmoni",
    "kind": "school",
    "latitude": 3.08011,
    "longitude": 101.51847
  },
  {
    "id": "synthetic-hospital-taman-seri-murni",
    "kind": "hospital",
    "latitude": 3.0940,
    "longitude": 101.5050
  }
]
```

- [ ] **Step 4: Run the full runtime composition file and verify GREEN**

Run the Task 2 Step 2 command. Expected: all tests pass.

- [ ] **Step 5: Re-run priority unit tests**

Run:

```powershell
uv run --offline python -m pytest tests/unit/test_priority.py -v
```

Expected: pass; confirmed-only priority invariants remain unchanged.

---

### Task 4: Lock the real full-demo scenario and repair review freshness

**Files:**
- Create: `tests/e2e/test_demo_scenario.py`
- Modify: `src/civicpulse/repository.py`
- Modify: `tests/integration/test_review_workflow.py`
- Modify: `pyproject.toml`

**Interfaces:**
- The E2E test uses `build_runtime()` with a temporary SQLite path and the real cached `SentenceTransformerProvider`.
- The target seed complaint ID is `uuid5(NAMESPACE_URL, "civicpulse-seed:shah-alam-demo-v1:complaint-025")`.
- The scenario submits the exact Manglish text with explicit category `blocked_drain`, finds the pending review connecting it to complaint 025, approves that review, and follows returned snapshot IDs.
- `SQLiteRepository.create_review(...)` refreshes evidence and `graph_version_at_creation` only for still-pending reviews that remain `REVIEW_REQUIRED`; resolved decisions remain immutable.

- [ ] **Step 1: Add the failing E2E scenario**

The test must perform these exact externally visible assertions:

```python
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from fastapi.testclient import TestClient

from civicpulse.runtime import RuntimeSettings, build_runtime


pytestmark = pytest.mark.e2e

TEXT = "Longkang dekat sekolah blocked lagi, hujan terus air naik."
TARGET_ID = uuid5(
    NAMESPACE_URL,
    "civicpulse-seed:shah-alam-demo-v1:complaint-025",
)


def incident_containing(client: TestClient, complaint_id: UUID) -> dict[str, object]:
    page = client.get("/api/v1/incidents", params={"limit": 100, "offset": 0})
    assert page.status_code == 200
    for item in page.json()["items"]:
        detail = client.get(f"/api/v1/incidents/{item['incident_id']}")
        assert detail.status_code == 200
        if str(complaint_id) in detail.json()["complaint_ids"]:
            return detail.json()
    raise AssertionError(f"complaint {complaint_id} is missing from incident snapshots")


def pending_review_for_pair(
    client: TestClient,
    left_id: UUID,
    right_id: UUID,
) -> dict[str, object]:
    offset = 0
    while True:
        response = client.get(
            "/api/v1/reviews",
            params={"status": "pending", "limit": 100, "offset": offset},
        )
        assert response.status_code == 200
        payload = response.json()
        for item in payload["items"]:
            pair = {item["left_complaint_id"], item["right_complaint_id"]}
            if pair == {str(left_id), str(right_id)}:
                return item
        offset += len(payload["items"])
        if offset >= payload["total"]:
            raise AssertionError("expected review pair was not surfaced")


def test_seed_submit_review_approve_and_refresh_full_demo(tmp_path: Path) -> None:
    runtime = build_runtime(
        RuntimeSettings(
            database_path=tmp_path / "civicpulse.db",
            seed_path=Path("data/seed_complaints.json"),
            sensitive_locations_path=Path("data/sensitive_locations.json"),
        )
    )
    client = TestClient(runtime.app)

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["core_ready"] is True
    before_page = client.get("/api/v1/incidents", params={"status": "confirmed", "limit": 100})
    assert before_page.status_code == 200
    assert before_page.json()["total"] >= 3
    before_target = incident_containing(client, TARGET_ID)
    before_count = before_target["confirmed_report_count"]

    request = {
        "text": TEXT,
        "category": "blocked_drain",
        "latitude": 3.08011,
        "longitude": 101.51847,
        "reported_at": "2026-07-11T08:00:00Z",
        "photo_path": None,
    }
    submitted = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "phase9-demo-scenario"},
        json=request,
    )
    replayed = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "phase9-demo-scenario"},
        json=request,
    )
    assert submitted.status_code == 201
    assert replayed.status_code == 201
    assert submitted.json()["created"] is True
    assert replayed.json()["created"] is False
    assert replayed.json()["replayed"] is True
    complaint_id = UUID(submitted.json()["complaint"]["complaint_id"])
    assert len(runtime.repository.list_complaints()) == 121

    review = pending_review_for_pair(client, complaint_id, TARGET_ID)
    approved = client.post(
        f"/api/v1/reviews/{review['review_id']}/approve",
        json={
            "reviewer_id": "demo-officer",
            "note": "Same synthetic school-access drain incident.",
        },
    )
    assert approved.status_code == 200
    payload = approved.json()
    assert payload["final_relationship_state"] == "auto_match"
    assert payload["previous_incident_snapshot_ids"]
    assert payload["new_incident_snapshot_ids"]

    after = incident_containing(client, complaint_id)
    assert str(TARGET_ID) in after["complaint_ids"]
    assert after["confirmed_report_count"] == before_count + 1
    assert after["priority"] is not None
    reasons = after["priority"]["reasons"]
    assert any("multi-report incident" in reason for reason in reasons)
    assert any("safety signal: active_flooding" in reason for reason in reasons)
    assert any("sensitive location" in reason for reason in reasons)
    assert runtime.service.photo_healthcheck is None
```

- [ ] **Step 2: Register and run the E2E marker to verify RED**

Add this marker to `pyproject.toml` because the repository enables strict marker validation:

```toml
"e2e: real cached-model full demo regression",
```

Run:

```powershell
uv run --offline python -m pytest tests/e2e/test_demo_scenario.py -v
```

Expected first failure: the newly surfaced review may return `409 review_stale`. Any different failure must be diagnosed before editing. Do not weaken assertions or matching policy.

- [ ] **Step 3: Add a focused pending-review refresh regression**

In `tests/integration/test_review_workflow.py`, reuse `create_pending_review`, reconstruct the same immutable candidate edge, and call `create_review` with a new graph version:

```python
from civicpulse.domain import RelationshipEdge


def test_pending_review_refreshes_graph_version_without_changing_evidence(tmp_path) -> None:
    _, repository, review = create_pending_review(tmp_path)
    edge = RelationshipEdge(
        left_id=review.left_id,
        right_id=review.right_id,
        decision=MatchState.REVIEW_REQUIRED,
        reasons=review.matcher_reasons,
        matcher_recommendation=review.matcher_recommendation,
        matcher_evidence=review.matcher_evidence,
    )

    repository.create_review(edge, NOW, "graph-v2")
    refreshed = repository.get_review(review.review_id)

    assert refreshed is not None
    assert refreshed.status is ReviewStatus.PENDING
    assert refreshed.graph_version_at_creation == "graph-v2"
    assert refreshed.matcher_recommendation is MatchState.REVIEW_REQUIRED
    assert refreshed.matcher_reasons == review.matcher_reasons
```

Add this second test to prove resolved decisions remain immutable:

```python
def test_resolved_review_is_not_refreshed_by_candidate_upsert(tmp_path) -> None:
    service, repository, review = create_pending_review(tmp_path)
    service.resolve_review(
        review.review_id,
        approve=False,
        reviewer_id="demo-officer",
        now=NOW,
    )
    before = repository.get_review(review.review_id)
    assert before is not None
    edge = RelationshipEdge(
        left_id=review.left_id,
        right_id=review.right_id,
        decision=MatchState.REVIEW_REQUIRED,
        reasons=review.matcher_reasons,
        matcher_recommendation=review.matcher_recommendation,
        matcher_evidence=review.matcher_evidence,
    )

    repository.create_review(edge, NOW, "graph-v3")
    after = repository.get_review(review.review_id)

    assert after is not None
    assert after.status is before.status
    assert after.final_relationship_state is before.final_relationship_state
    assert after.graph_version_at_creation == before.graph_version_at_creation
    assert after.version == before.version
```

- [ ] **Step 4: Replace `INSERT OR IGNORE` for review creation with a pending-only upsert**

In `SQLiteRepository.create_review`, use this conflict clause after the existing `VALUES` list:

```sql
ON CONFLICT(review_id) DO UPDATE SET
    matcher_recommendation=excluded.matcher_recommendation,
    matcher_reasons=excluded.matcher_reasons,
    matcher_evidence=excluded.matcher_evidence,
    graph_version_at_creation=excluded.graph_version_at_creation
WHERE reviews.status='pending'
```

Do not update `created_at`, `status`, resolution fields, decision source, or version. This keeps officer decisions immutable while allowing a still-valid pending candidate to be reviewed against the current graph.

- [ ] **Step 5: Run focused review and E2E tests**

Run:

```powershell
uv run --offline python -m pytest tests/integration/test_review_workflow.py -v
uv run --offline python -m pytest tests/e2e/test_demo_scenario.py -v
```

Expected: both pass. If E2E still reports `review_stale`, compare the stored and freshly recomputed graph hashes and stop; do not remove the stale check.

- [ ] **Step 6: Re-run the uncertainty-boundary regressions**

Run:

```powershell
uv run --offline python -m pytest tests/unit/test_matching.py tests/unit/test_clustering.py tests/unit/test_priority.py tests/integration/test_review_workflow.py -v
```

Expected: pass with review candidates excluded from confirmed membership and priority until approval.

---

### Task 5: Document the real launcher and Task 9.1 behavior

**Files:**
- Modify: `README.md`

**Interfaces:**
- Production API start command becomes `uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000`.
- README explains first-start seed initialization, restart preservation, server-owned paths, default-disabled reset, cached-model prerequisite, and the conservative submit-to-review workflow.

- [ ] **Step 1: Replace the current launcher limitation section**

Document two-terminal startup:

```powershell
# Terminal 1: composed API, SQLite, policies, seed, and cached embedding model
uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000

# Terminal 2: Dashboard HTTP client
uv run --offline streamlit run src/civicpulse_dashboard/app.py
```

State explicitly:

- an empty database is initialized from `data/seed_complaints.json`;
- an existing non-empty database is preserved;
- reset stays disabled unless `CIVICPULSE_ADMIN_RESET_ENABLED=true`;
- `CIVICPULSE_DB_PATH`, `CIVICPULSE_SEED_PATH`, and `CIVICPULSE_SENSITIVE_LOCATIONS_PATH` are server-side configuration;
- the example Manglish report is intentionally review-required until an officer approves the candidate relationship;
- Phase 9.2 will add the complete offline/fault runbook.

- [ ] **Step 2: Verify README commands and paths**

Run:

```powershell
rg -n "create_runtime_app|CIVICPULSE_DB_PATH|review-required|Phase 9.2" README.md
uv run --offline python -c "from civicpulse.runtime import create_runtime_app; app = create_runtime_app(); print(app.title)"
```

Expected: all required documentation terms are present and the factory prints `CivicPulse-lite API` with the model already cached.

---

### Task 6: Run the Task 9.1 quality gate

**Files:**
- Verify only. Make production edits only for defects directly exposed by Task 9.1 tests.

- [ ] **Step 1: Run the full non-live test suite including E2E**

```powershell
uv run --offline python -m pytest -m "not live" -q
```

Expected: all tests pass; the prior count of 180 increases by the new runtime, geography, review-refresh, and E2E cases.

- [ ] **Step 2: Run strict type and lint checks**

```powershell
uv run --offline pyright src scripts
uv run --offline ruff check src tests/integration/test_runtime_composition.py tests/e2e/test_demo_scenario.py
```

Expected: no errors.

- [ ] **Step 3: Re-run the hybrid matching gate**

```powershell
uv run --offline python -m scripts.run_hybrid_benchmark
```

Expected: exit `0`, zero false automatic merges, zero positive `no_match` decisions, clear-positive automatic rate at least `0.75`.

- [ ] **Step 4: Verify repository scope**

```powershell
git diff --check
git status --short
```

Expected Task 9.1 scope only:

- `src/civicpulse/runtime.py`
- `data/sensitive_locations.json`
- `tests/integration/test_runtime_composition.py`
- `tests/integration/test_review_workflow.py`
- `tests/e2e/test_demo_scenario.py`
- `pyproject.toml` only if the `e2e` marker was required
- `README.md`
- this implementation plan

- [ ] **Step 5: Perform a manual two-terminal browser smoke**

Start the runtime API and Dashboard with the documented commands. Verify readiness, at least three hotspots, one idempotent submission, a visible pending candidate, officer approval, snapshot refresh, and the sensitive-location/flooding priority reasons. Stop both processes after the check.

- [ ] **Step 6: Report evidence and wait for explicit commit approval**

Do not stage, commit, or push automatically. Report exact test counts, benchmark metrics, warning output, browser-smoke result, and any remaining uncertainty. After approval, use the commit subject:

```text
test: lock the composed CivicPulse demo scenario
```

## Task 9.1 Stop Conditions

- Stop if the real cached model is missing; run the documented prewarm command rather than substituting a fake in E2E.
- Stop if the hybrid benchmark regresses; do not tune policy inside Task 9.1.
- Stop if officer approval would require bypassing `ReviewStale`; repair freshness semantics or record the unresolved defect.
- Stop if the scenario can pass only by counting pending candidates as confirmed evidence.
- Task 9.1 is complete only when the composed runtime starts with a prewarmed cached model, restart preserves state, the real scenario passes through review and approval, the full non-live suite passes, and the hybrid quality gate remains green. Network-blocked startup is intentionally deferred to Task 9.2.

## Phase 9 Continuation

After Task 9.1 is verified and committed, write separate executable plans for:

1. **Task 9.2 — Offline, fault, and recovery:** local-only model loading, missing-cache startup failure, bounded SQLite lock translation with no partial write, degraded optional photo health, and `docs/demo-runbook.md`.
2. **Task 9.3 — Performance budgets:** cached 180-complaint relationship construction, warm submission, seed reset, and Dashboard map-row timing on the documented reference machine.
