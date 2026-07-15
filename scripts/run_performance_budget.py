"""Run the explicit CivicPulse performance-budget harness."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from subprocess import Popen
from typing import Literal, NamedTuple, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient

from civicpulse.performance import (
    MeasurementEnvironment,
    MetricEvaluation,
    MetricSummary,
    PerformanceBudget,
    PerformanceReport,
    evaluate_budget,
    load_budget,
    summarize,
)

MetricStatus = Literal["completed", "incomplete"]
SubmissionScenario = Literal["isolated", "auto_match", "review_required"]
ROOT = Path(__file__).resolve().parents[1]
STARTUP_DEADLINE_SECONDS = 90.0


class DashboardTiming(NamedTuple):
    dashboard_seconds: list[float]
    full_demo_seconds: list[float]


class StartupMeasurement(NamedTuple):
    cold_process_seconds: list[float]
    warm_readiness_seconds: list[float]
    profiles: list[dict[str, float]]


def derive_startup_profile_metrics(profile: Mapping[str, float]) -> tuple[float, float]:
    """Separate application composition from one-time local model verification."""
    application_seconds = sum(
        profile.get(name, 0.0)
        for name in (
            "settings_and_policy_loading",
            "database_and_seed_initialization",
            "app_composition",
        )
    )
    cold_model_seconds = profile.get("model_provider_load", 0.0) + profile.get(
        "readiness_probe", 0.0
    )
    return application_seconds, cold_model_seconds


def dashboard_elapsed_seconds(
    *, api_process_started: float, dashboard_started: float, dashboard_usable: float
) -> tuple[float, float]:
    """Return dashboard-only and full-demo elapsed times from explicit boundaries."""
    if not api_process_started <= dashboard_started <= dashboard_usable:
        raise ValueError("Dashboard timing markers must be monotonic")
    return (
        dashboard_usable - dashboard_started,
        dashboard_usable - api_process_started,
    )


class ResponseLike(Protocol):
    status_code: int

    def json(self) -> object: ...


class ClientLike(Protocol):
    def get(self, url: str, *, params: Mapping[str, object] | None = None) -> ResponseLike: ...

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> ResponseLike: ...


def metric_run_count(metric: str, budget: PerformanceBudget) -> int:
    """Return the run count for a metric's cost class."""
    if metric in {
        "cached_process_readiness_seconds",
        "application_composition_seconds",
        "warm_readiness_seconds",
        "cold_cached_model_initialization_seconds",
        "cold_start_ms",
        "ready_rss_mb",
    }:
        return budget.startup_runs
    if metric in {"reset_seconds"}:
        return budget.reset_runs
    if metric in {"dashboard_first_usable_seconds", "dashboard_response_seconds"}:
        return budget.dashboard_runs
    return budget.measured_runs


def build_child_environment(
    parent: Mapping[str, str] | None = None,
    *,
    offline: bool = True,
) -> dict[str, str]:
    """Build a sanitized child environment with explicit offline policy."""
    child = dict(os.environ if parent is None else parent)
    if offline:
        child["HF_HUB_OFFLINE"] = "1"
    return child


def build_api_command(*, port: int) -> list[str]:
    """Build the documented factory command used for a fresh API process."""
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "civicpulse.runtime:create_runtime_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def measure_isolated_samples(
    *,
    reset: Callable[[], object],
    warm: Callable[[], object],
    operation: Callable[[], object],
    runs: int,
    clock: Callable[[], float] = time.perf_counter,
) -> list[float]:
    """Time one mutation per deterministic reset/warm cycle in milliseconds."""
    if runs < 1:
        raise ValueError("runs must be positive")
    samples: list[float] = []
    for _ in range(runs):
        reset()
        warm()
        started = clock()
        operation()
        samples.append((clock() - started) * 1000)
    return samples


def _timed_milliseconds(operation: Callable[[], object]) -> float:
    started = time.perf_counter()
    operation()
    return (time.perf_counter() - started) * 1000


def timed_milliseconds_with_result[T](
    operation: Callable[[], T],
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[float, T]:
    """Time an operation while returning its result for untimed validation."""
    started = clock()
    result = operation()
    return (clock() - started) * 1000, result


def submission_sample_text(scenario: SubmissionScenario, sample_index: int) -> str:
    """Return a deterministic uncached text while retaining scenario-defining entities."""
    if sample_index < 0:
        raise ValueError("sample_index must be non-negative")
    prefixes = {
        "isolated": "isolated performance sample",
        "auto_match": "Road hole at Blok A Jln Ampang pothole sample",
        "review_required": "Pothole near school sample",
    }
    return f"{prefixes[scenario]} {sample_index}"


def _complaint_payload(
    text: str,
    *,
    latitude: float = 3.2501,
    longitude: float = 101.7501,
) -> dict[str, object]:
    return {
        "text": text,
        "category": "blocked_drain",
        "latitude": latitude,
        "longitude": longitude,
        "reported_at": datetime.now(UTC).isoformat(),
    }


def _submit(
    client: ClientLike,
    text: str,
    key: str,
    *,
    latitude: float = 3.2501,
    longitude: float = 101.7501,
) -> ResponseLike:
    response = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": key},
        json=_complaint_payload(text, latitude=latitude, longitude=longitude),
    )
    if response.status_code != 201:
        raise RuntimeError(f"performance submission failed with status {response.status_code}")
    return response


def _submission_complaint_id(response: ResponseLike) -> str:
    try:
        payload = cast(dict[str, object], response.json())
        complaint = cast(dict[str, object], payload["complaint"])
        return str(complaint["complaint_id"])
    except (KeyError, TypeError) as exc:
        raise RuntimeError("performance submission returned an invalid complaint payload") from exc


def assert_submission_scenario(
    response: ResponseLike,
    *,
    expected_decision: SubmissionScenario,
    fixture_complaint_id: str | None = None,
) -> str:
    """Validate the named scenario from the API response after timing completes."""
    measured_complaint_id = _submission_complaint_id(response)
    try:
        payload = cast(dict[str, object], response.json())
        decisions = cast(list[dict[str, object]], payload["relationship_decisions"])
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "performance submission returned invalid relationship decisions"
        ) from exc

    if expected_decision == "isolated":
        if any(
            measured_complaint_id in {str(edge.get("left_id")), str(edge.get("right_id"))}
            for edge in decisions
        ):
            raise RuntimeError(
                "performance isolated scenario produced a relationship for the measured complaint"
            )
        return measured_complaint_id
    if fixture_complaint_id is None:
        raise ValueError("fixture_complaint_id is required for paired scenarios")

    expected_pair = {fixture_complaint_id, measured_complaint_id}
    if not any(
        {str(edge.get("left_id")), str(edge.get("right_id"))} == expected_pair
        and edge.get("decision") == expected_decision
        for edge in decisions
    ):
        raise RuntimeError(
            f"performance {expected_decision} scenario did not expose the expected pair decision"
        )
    return measured_complaint_id


def _pending_review_page(
    response: ResponseLike,
    left_complaint_id: str,
    right_complaint_id: str,
) -> tuple[bool, int, int]:
    if response.status_code != 200:
        raise RuntimeError(f"pending review lookup failed with status {response.status_code}")
    try:
        payload = cast(dict[str, object], response.json())
        items = cast(list[dict[str, object]], payload["items"])
        total = int(cast(int, payload["total"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("pending review lookup returned an invalid payload") from exc
    expected_pair = {left_complaint_id, right_complaint_id}
    found = any(
        {str(item.get("left_complaint_id")), str(item.get("right_complaint_id"))} == expected_pair
        for item in items
    )
    return found, len(items), total


def assert_pending_review_pair(
    response: ResponseLike,
    left_complaint_id: str,
    right_complaint_id: str,
) -> None:
    """Require one pending-review API page to expose the measured complaint pair."""
    found, _, _ = _pending_review_page(response, left_complaint_id, right_complaint_id)
    if not found:
        raise RuntimeError("performance review_required scenario did not expose a pending review")


def assert_pending_review_pair_via_api(
    client: ClientLike,
    left_complaint_id: str,
    right_complaint_id: str,
    *,
    page_size: int = 100,
) -> None:
    """Page through pending reviews until the measured pair is found or exhausted."""
    if page_size < 1:
        raise ValueError("page_size must be positive")
    offset = 0
    while True:
        response = client.get(
            "/api/v1/reviews",
            params={"status": "pending", "limit": page_size, "offset": offset},
        )
        found, item_count, total = _pending_review_page(
            response,
            left_complaint_id,
            right_complaint_id,
        )
        if found:
            return
        offset += item_count
        if item_count == 0 or offset >= total:
            raise RuntimeError(
                "performance review_required scenario did not expose a pending review"
            )


def _reset(client: ClientLike) -> None:
    response = client.post("/api/v1/admin/reset")
    if response.status_code != 200:
        raise RuntimeError(f"performance reset failed with status {response.status_code}")


def measure_api_workflows(
    database_path: Path,
    *,
    runs: int,
    reset_runs: int,
    warmup_runs: int = 0,
) -> dict[str, list[float]]:
    """Measure stable in-process reads and isolated mutation workflows."""
    from civicpulse.runtime import RuntimeSettings, build_runtime

    settings = RuntimeSettings(database_path=database_path, admin_reset_enabled=True)
    bundle = build_runtime(settings)
    client = cast(ClientLike, TestClient(bundle.app))
    samples: dict[str, list[float]] = {
        "runtime_composition_seconds": [],
        "incident_list_p95_ms": [],
        "incident_detail_p95_ms": [],
        "submission_isolated_p95_ms": [],
        "submission_auto_match_p95_ms": [],
        "submission_review_required_p95_ms": [],
        "review_approve_p95_ms": [],
        "review_reject_p95_ms": [],
        "review_merge_p95_ms": [],
        "reset_seconds": [],
    }

    for _ in range(warmup_runs):
        client.get("/api/v1/incidents", params={"limit": 50, "offset": 0})
        _reset(client)

    for sample_index in range(runs):
        list_started = time.perf_counter()
        page = client.get("/api/v1/incidents", params={"limit": 50, "offset": 0})
        if page.status_code != 200:
            raise RuntimeError(f"incident list failed with status {page.status_code}")
        samples["incident_list_p95_ms"].append((time.perf_counter() - list_started) * 1000)
        page_payload = cast(dict[str, object], page.json())
        items = cast(list[dict[str, object]], page_payload["items"])
        incident_id = str(items[0]["incident_id"])
        samples["incident_detail_p95_ms"].append(
            _timed_milliseconds(
                lambda incident_id=incident_id: client.get(f"/api/v1/incidents/{incident_id}")
            )
        )

        _reset(client)
        isolated_elapsed, isolated_response = timed_milliseconds_with_result(
            lambda sample_index=sample_index: _submit(
                client,
                submission_sample_text("isolated", sample_index),
                "isolated-key",
                latitude=0.0,
                longitude=0.0,
            )
        )
        samples["submission_isolated_p95_ms"].append(isolated_elapsed)
        assert_submission_scenario(isolated_response, expected_decision="isolated")

        _reset(client)
        auto_seed_response = _submit(client, "Pothole at Block A Jalan Ampang", "auto-seed")
        auto_seed_id = _submission_complaint_id(auto_seed_response)
        auto_elapsed, auto_response = timed_milliseconds_with_result(
            lambda sample_index=sample_index: _submit(
                client,
                submission_sample_text("auto_match", sample_index),
                "auto-measured",
            )
        )
        samples["submission_auto_match_p95_ms"].append(auto_elapsed)
        assert_submission_scenario(
            auto_response,
            expected_decision="auto_match",
            fixture_complaint_id=auto_seed_id,
        )

        _reset(client)
        review_seed_response = _submit(client, "Pothole at Block A Jalan Ampang", "review-seed")
        review_seed_id = _submission_complaint_id(review_seed_response)
        review_elapsed, review_response = timed_milliseconds_with_result(
            lambda sample_index=sample_index: _submit(
                client,
                submission_sample_text("review_required", sample_index),
                "review-measured",
            )
        )
        samples["submission_review_required_p95_ms"].append(review_elapsed)
        review_complaint_id = assert_submission_scenario(
            review_response,
            expected_decision="review_required",
            fixture_complaint_id=review_seed_id,
        )
        assert_pending_review_pair_via_api(client, review_seed_id, review_complaint_id)

        for metric, endpoint in (
            ("review_approve_p95_ms", "approve"),
            ("review_reject_p95_ms", "reject"),
            ("review_merge_p95_ms", "approve"),
        ):
            _reset(client)
            _submit(client, "Pothole at Block A Jalan Ampang", f"{metric}-seed")
            _submit(client, "Pothole near school", f"{metric}-review")
            reviews = client.get("/api/v1/reviews", params={"status": "pending"})
            review_payload = cast(dict[str, object], reviews.json())
            review_items = cast(list[dict[str, object]], review_payload["items"])
            if reviews.status_code != 200 or not review_items:
                raise RuntimeError("performance review fixture did not create a pending review")
            review_id = str(review_items[0]["review_id"])
            samples[metric].append(
                _timed_milliseconds(
                    lambda review_id=review_id, endpoint=endpoint: client.post(
                        f"/api/v1/reviews/{review_id}/{endpoint}",
                        json={"reviewer_id": "performance-officer"},
                    )
                )
            )

    for _ in range(reset_runs):
        started = time.perf_counter()
        _reset(client)
        samples["reset_seconds"].append(time.perf_counter() - started)
    return samples


def _free_port() -> int:
    import socket

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _terminate_process_tree(process: Popen[bytes]) -> None:
    """Terminate uvicorn plus its Windows child worker without touching other PIDs."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except TimeoutError:
        process.kill()
        process.wait(timeout=5)


def _api_worker_pid(parent_pid: int) -> int:
    """Resolve the uvicorn worker PID whose RSS contains the loaded model."""
    if os.name != "nt":
        return parent_pid
    query = (
        "(Get-CimInstance Win32_Process "
        f"-Filter 'ParentProcessId={parent_pid}').ProcessId"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", query],
        check=False,
        capture_output=True,
        text=True,
    )
    children = [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]
    candidates = [parent_pid, *children]
    rss_by_pid: list[tuple[float, int]] = []
    for pid in candidates:
        try:
            rss_by_pid.append((read_process_rss_mb(pid), pid))
        except OSError:
            continue
    return max(rss_by_pid, default=(0.0, parent_pid))[1]


def measure_cached_process_readiness(
    *, runs: int, warmup_runs: int = 0, profile_path: Path | None = None
) -> StartupMeasurement:
    """Measure cold process startup, warm health reads, and per-run startup spans."""
    if warmup_runs:
        measure_cached_process_readiness(runs=warmup_runs)
    cold_samples: list[float] = []
    warm_samples: list[float] = []
    profiles: list[dict[str, float]] = []
    for _ in range(runs):
        with tempfile.TemporaryDirectory(prefix="civicpulse-perf-") as directory:
            port = _free_port()
            environment = build_child_environment()
            environment["CIVICPULSE_DB_PATH"] = str(Path(directory) / "runtime.db")
            if profile_path is not None:
                environment["CIVICPULSE_STARTUP_PROFILE_PATH"] = str(profile_path)
            process: Popen[bytes] | None = None
            started = time.perf_counter()
            try:
                process = Popen(
                    build_api_command(port=port),
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                deadline = time.perf_counter() + STARTUP_DEADLINE_SECONDS
                ready = False
                while time.perf_counter() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("API child process exited before readiness")
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=0.25
                        ) as response:
                            if response.status == 200:
                                ready = True
                                break
                    except (OSError, URLError):
                        time.sleep(0.05)
                if not ready:
                    raise RuntimeError(
                        "API child process did not become ready within "
                        f"{STARTUP_DEADLINE_SECONDS:.0f} seconds"
                    )
                cold_samples.append(time.perf_counter() - started)
                if profile_path is not None and profile_path.exists():
                    profiles.append(cast(dict[str, float], json.loads(profile_path.read_text())))
                warm_started = time.perf_counter()
                with urlopen(
                    f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=5
                ) as warm_response:
                    if warm_response.status != 200:
                        raise RuntimeError("warm readiness probe returned a non-ready status")
                warm_samples.append(time.perf_counter() - warm_started)
            finally:
                if process is not None:
                    _terminate_process_tree(process)
    return StartupMeasurement(cold_samples, warm_samples, profiles)


def _post_child_json(url: str, payload: dict[str, object], key: str) -> None:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Idempotency-Key": key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            if response.status != 201:
                raise RuntimeError(f"child submission returned {response.status}")
    except HTTPError as exc:
        raise RuntimeError(f"child submission returned {exc.code}") from exc


def measure_api_process_memory(
    *, runs: int, mutations: int = 20, warmup_runs: int = 0
) -> tuple[list[float], list[float]]:
    """Measure API child RSS at ready and after sequential mutations."""
    if warmup_runs:
        measure_api_process_memory(runs=warmup_runs, mutations=mutations)
    ready_samples: list[float] = []
    post_mutation_samples: list[float] = []
    for run in range(runs):
        with tempfile.TemporaryDirectory(prefix="civicpulse-rss-") as directory:
            port = _free_port()
            environment = build_child_environment()
            environment["CIVICPULSE_DB_PATH"] = str(Path(directory) / "runtime.db")
            process = Popen(
                build_api_command(port=port),
                cwd=ROOT,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.perf_counter() + STARTUP_DEADLINE_SECONDS
                while time.perf_counter() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("API child process exited before RSS readiness")
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=0.25
                        ) as response:
                            if response.status == 200:
                                break
                    except (OSError, URLError):
                        time.sleep(0.05)
                else:
                    raise RuntimeError("API child process did not become ready for RSS")
                ready_samples.append(read_process_rss_mb(_api_worker_pid(process.pid)))
                for index in range(mutations):
                    _post_child_json(
                        f"http://127.0.0.1:{port}/api/v1/complaints",
                        _complaint_payload(f"rss mutation {run}-{index}"),
                        f"rss-{run}-{index}",
                    )
                post_mutation_samples.append(read_process_rss_mb(_api_worker_pid(process.pid)))
            finally:
                _terminate_process_tree(process)
    return ready_samples, post_mutation_samples


def measure_dashboard_first_usable(
    *, runs: int, warmup_runs: int = 0
) -> DashboardTiming:
    """Measure API/Dashboard startup to a visible operational marker."""
    from streamlit.testing.v1 import AppTest

    if warmup_runs:
        measure_dashboard_first_usable(runs=warmup_runs)
    dashboard_samples: list[float] = []
    full_demo_samples: list[float] = []
    for _ in range(runs):
        with tempfile.TemporaryDirectory(prefix="civicpulse-dashboard-") as directory:
            port = _free_port()
            environment = build_child_environment()
            environment["CIVICPULSE_DB_PATH"] = str(Path(directory) / "runtime.db")
            api_process = Popen(
                build_api_command(port=port),
                cwd=ROOT,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            dashboard_process: Popen[bytes] | None = None
            previous_url = os.environ.get("CIVICPULSE_API_URL")
            api_process_started = time.perf_counter()
            try:
                deadline = time.perf_counter() + 30.0
                while time.perf_counter() < deadline:
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=0.25
                        ) as response:
                            if response.status == 200:
                                break
                    except (OSError, URLError):
                        time.sleep(0.05)
                else:
                    raise RuntimeError("API child process did not become ready for Dashboard")
                dashboard_started = time.perf_counter()
                os.environ["CIVICPULSE_API_URL"] = f"http://127.0.0.1:{port}/api/v1"
                dashboard_port = _free_port()
                dashboard_environment = build_child_environment()
                dashboard_environment["CIVICPULSE_API_URL"] = (
                    f"http://127.0.0.1:{port}/api/v1"
                )
                dashboard_process = Popen(
                    [
                        sys.executable,
                        "-m",
                        "streamlit",
                        "run",
                        str(ROOT / "src" / "civicpulse_dashboard" / "app.py"),
                        "--server.headless",
                        "true",
                        "--server.address",
                        "127.0.0.1",
                        "--server.port",
                        str(dashboard_port),
                    ],
                    cwd=ROOT,
                    env=dashboard_environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                dashboard_deadline = time.perf_counter() + 30.0
                while time.perf_counter() < dashboard_deadline:
                    if dashboard_process.poll() is not None:
                        raise RuntimeError("Dashboard process exited before root response")
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{dashboard_port}", timeout=0.25
                        ) as response:
                            if response.status == 200:
                                break
                    except (OSError, URLError):
                        time.sleep(0.05)
                else:
                    raise RuntimeError("Dashboard did not return a root response")
                app = AppTest.from_file(str(ROOT / "src" / "civicpulse_dashboard" / "app.py"))
                app.run(timeout=30)
                captions = [str(item.value) for item in app.caption]
                if "CivicPulse operational queue ready" not in captions:
                    raise RuntimeError("Dashboard operational queue marker was not rendered")
                dashboard_usable = time.perf_counter()
                dashboard_seconds, full_demo_seconds = dashboard_elapsed_seconds(
                    api_process_started=api_process_started,
                    dashboard_started=dashboard_started,
                    dashboard_usable=dashboard_usable,
                )
                dashboard_samples.append(dashboard_seconds)
                full_demo_samples.append(full_demo_seconds)
            finally:
                if previous_url is None:
                    os.environ.pop("CIVICPULSE_API_URL", None)
                else:
                    os.environ["CIVICPULSE_API_URL"] = previous_url
                if dashboard_process is not None:
                    _terminate_process_tree(dashboard_process)
                _terminate_process_tree(api_process)
    return DashboardTiming(dashboard_samples, full_demo_samples)


def read_process_rss_mb(pid: int) -> float:
    """Read one process RSS sample using Windows APIs or Linux procfs."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        process_handle = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid)  # type: ignore[attr-defined]
        if not process_handle:
            raise OSError(f"cannot open process {pid}")
        try:
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(ProcessMemoryCounters)
            success = ctypes.windll.psapi.GetProcessMemoryInfo(  # type: ignore[attr-defined]
                process_handle,
                ctypes.byref(counters),
                counters.cb,
            )
            if not success:
                raise OSError(f"cannot read RSS for process {pid}")
            return counters.WorkingSetSize / (1024 * 1024)
        finally:
            ctypes.windll.kernel32.CloseHandle(process_handle)  # type: ignore[attr-defined]

    status_path = Path(f"/proc/{pid}/status")
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return float(line.split()[1]) / 1024
    raise OSError(f"RSS is unavailable for process {pid}")


def rss_growth(ready_rss_mb: float, post_mutation_rss_mb: float) -> tuple[float, float]:
    """Return absolute and percentage RSS growth for one API process."""
    if ready_rss_mb <= 0:
        raise ValueError("ready RSS must be positive")
    growth_mb = post_mutation_rss_mb - ready_rss_mb
    return growth_mb, growth_mb / ready_rss_mb * 100


def classify_exit_code(
    *,
    measurement_status: MetricStatus,
    hard_gate_passed: bool | None,
) -> int:
    """Return 0 for pass, 1 for completed breach, and 2 for infrastructure failure."""
    if measurement_status == "incomplete" or hard_gate_passed is None:
        return 2
    return 0 if hard_gate_passed else 1


def render_markdown_summary(
    *,
    budget_version: str,
    raw_json_path: str,
    hard_gate_passed: bool | None,
    environment: MeasurementEnvironment | None = None,
    summaries: Mapping[str, MetricSummary] | None = None,
    evaluations: Mapping[str, MetricEvaluation] | None = None,
    known_noise_sources: tuple[str, ...] = (),
    timestamp: str | None = None,
    git_commit: str | None = None,
    git_dirty: bool | None = None,
    startup_profile: Mapping[str, float] | None = None,
) -> str:
    """Render the concise report shell; raw arrays stay in the JSON source of truth."""
    result = (
        "PASS"
        if hard_gate_passed is True
        else "FAIL"
        if hard_gate_passed is False
        else "INCOMPLETE"
    )
    display_path = (
        "benchmarks/reports/performance-budget.json"
        if "performance-budget.json" in raw_json_path
        else raw_json_path.replace("\\", "/")
    )
    lines = [
        "# CivicPulse Performance Budget",
        "",
        f"- Budget version: `{budget_version}`",
        f"- Hard-gate result: **{result}**",
        f"- Raw samples are retained in `{display_path}`.",
        "",
    ]
    if timestamp is not None and git_commit is not None and git_dirty is not None:
        lines.extend(
            [
                f"- Measurement timestamp: {timestamp}",
                f"- Git commit: `{git_commit}` (dirty={git_dirty})",
                "",
            ]
        )
    if environment is not None:
        lines.extend(
            [
                "## Environment",
                "",
                f"- OS: {environment.os}",
                f"- CPU: {environment.cpu}",
                f"- RAM: {environment.ram_mb:.0f} MB",
                f"- Python: {environment.python_version}",
                f"- Model: {environment.model_name}",
                f"- Seed size: {environment.seed_size}",
                f"- Database: {environment.database_backend}",
                f"- Offline mode: {environment.offline_mode}",
                f"- Runs: warm-up={environment.warmup_runs}, measured={environment.measured_runs}",
                f"- Method: {environment.measurement_method}",
                "",
            ]
        )
    if summaries is not None and evaluations is not None:
        lines.extend(
            [
                "## Results",
                "",
                "| Metric | p50 | p95 | max | Limit | Hard | Result |",
                "|---|---:|---:|---:|---:|:---:|:---:|",
            ]
        )
        for name, summary in summaries.items():
            evaluation = evaluations.get(name)
            if evaluation is None:
                continue
            limit = "—" if evaluation.limit is None else f"{evaluation.limit:.2f}"
            lines.append(
                f"| {name} | {summary.p50:.2f} | {summary.p95:.2f} | "
                f"{summary.maximum:.2f} | {limit} | {evaluation.hard} | "
                f"{'PASS' if evaluation.passed else 'FAIL'} |"
            )
        aggregate_names = (
            "submission_p95_ms",
            "review_resolution_p95_ms",
            "mutation_memory_growth_percent",
        )
        for name in aggregate_names:
            evaluation = evaluations.get(name)
            if evaluation is not None:
                result_text = "PASS" if evaluation.passed else "FAIL"
                limit_text = "—" if evaluation.limit is None else f"{evaluation.limit:.2f}"
                lines.append(
                    f"| {name} | aggregate | {evaluation.observed:.2f} | — | "
                    f"{limit_text} | {evaluation.hard} | {result_text} |"
                )
        noise = ", ".join(known_noise_sources) or "none"
        lines.extend(["", f"Known noise sources: {noise}.", ""])
    if startup_profile:
        lines.extend(["## Cached readiness timing profile", ""])
        for name, seconds in startup_profile.items():
            lines.append(f"- {name}: {seconds:.3f} s")
        lines.append("")
    lines.extend(
        [
            "## Startup budget history",
            "",
            "- Prototype-1 originally defined cached process readiness as <=8 s.",
            "- Profiling showed that metric combined application composition with first "
            "cached-model initialization; it is retired as a hard gate, not silently widened.",
            "",
        ]
    )
    lines.extend(
        [
            "This Markdown report contains summaries only; the JSON file is the audit source.",
            "No optimization was performed where the measured result already met budget.",
            "",
        ]
    )
    return "\n".join(lines)


def _git_metadata() -> tuple[str, bool]:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip() or "unknown"
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


def _system_ram_mb() -> float:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return status.ullTotalPhys / (1024 * 1024)
    return 1.0


def run_performance_budget(
    *,
    budget_path: Path,
    output_json: Path,
    output_markdown: Path | None,
    offline: bool = True,
    warmup_runs: int | None = None,
    measured_runs: int | None = None,
    startup_runs: int | None = None,
    reset_runs: int | None = None,
    dashboard_runs: int | None = None,
) -> PerformanceReport:
    """Run the currently wired API measurements and emit an auditable report."""
    budget = load_budget(budget_path)
    updates = {
        key: value
        for key, value in {
            "warmup_runs": warmup_runs,
            "measured_runs": measured_runs,
            "startup_runs": startup_runs,
            "reset_runs": reset_runs,
            "dashboard_runs": dashboard_runs,
        }.items()
        if value is not None
    }
    if updates:
        budget = budget.model_copy(update=updates)
    if not offline:
        raise ValueError("The performance harness requires explicit offline mode.")
    with tempfile.TemporaryDirectory(prefix="civicpulse-performance-") as directory:
        database_path = Path(directory) / "performance.db"
        profile_path = Path(directory) / "startup-profile.json"
        startup = measure_cached_process_readiness(
            runs=budget.startup_runs,
            warmup_runs=budget.warmup_runs,
            profile_path=profile_path,
        )
        raw_samples = {
            "cached_process_readiness_seconds": startup.cold_process_seconds,
            "warm_readiness_seconds": startup.warm_readiness_seconds,
        }
        application_samples: list[float] = []
        cold_model_samples: list[float] = []
        for profile in startup.profiles:
            application_seconds, cold_model_seconds = derive_startup_profile_metrics(profile)
            application_samples.append(application_seconds)
            cold_model_samples.append(cold_model_seconds)
        if application_samples and cold_model_samples:
            raw_samples["application_composition_seconds"] = application_samples
            raw_samples["cold_cached_model_initialization_seconds"] = cold_model_samples
        raw_samples.update(
            measure_api_workflows(
                database_path,
                runs=budget.measured_runs,
                reset_runs=budget.reset_runs,
                warmup_runs=budget.warmup_runs,
            )
        )
        ready_rss, post_mutation_rss = measure_api_process_memory(
            runs=budget.startup_runs, warmup_runs=budget.warmup_runs
        )
        raw_samples["ready_rss_mb"] = ready_rss
        raw_samples["post_20_mutations_rss_mb"] = post_mutation_rss
        growth_samples = [
            max(0.0, rss_growth(ready, post)[1])
            for ready, post in zip(ready_rss, post_mutation_rss, strict=True)
        ]
        raw_samples["mutation_memory_growth_percent"] = growth_samples
        dashboard_timing = measure_dashboard_first_usable(
            runs=budget.dashboard_runs, warmup_runs=budget.warmup_runs
        )
        raw_samples["dashboard_first_usable_seconds"] = dashboard_timing.dashboard_seconds
        raw_samples["full_demo_cold_path_seconds"] = dashboard_timing.full_demo_seconds
        startup_profile = {}
        if startup.profiles:
            profile_names = sorted({name for profile in startup.profiles for name in profile})
            startup_profile = {
                name: summarize(
                    [profile[name] for profile in startup.profiles if name in profile]
                ).p95
                for name in profile_names
            }
            runtime_total = startup_profile.get("runtime_composition_total")
            if runtime_total is not None:
                startup_profile["process_to_ready_unattributed"] = max(
                    0.0,
                    summarize(startup.cold_process_seconds).p95 - runtime_total,
                )
    summaries = {name: summarize(values) for name, values in raw_samples.items() if values}
    commit, dirty = _git_metadata()
    growth_percent = max(raw_samples["mutation_memory_growth_percent"])
    evaluation = evaluate_budget(budget, summaries, rss_growth_percent=growth_percent)
    environment = MeasurementEnvironment(
        os=platform.platform(),
        cpu=platform.processor() or platform.machine(),
        ram_mb=_system_ram_mb(),
        python_version=platform.python_version(),
        model_name="intfloat/multilingual-e5-small",
        seed_size=120,
        database_backend="SQLite local file",
        offline_mode=True,
        warmup_runs=budget.warmup_runs,
        measured_runs=budget.measured_runs,
        measurement_method=(
            "time.perf_counter; cold process, warm readiness, and startup spans are "
            "separate; Dashboard timer starts after API readiness"
        ),
    )
    report = PerformanceReport(
        environment=environment,
        budget_version=budget.budget_version,
        timestamp=datetime.now(UTC).isoformat(),
        git_commit=commit,
        git_dirty=dirty,
        raw_samples=raw_samples,
        summaries=summaries,
        rss={
            "ready_rss_mb_max": max(ready_rss),
            "post_20_mutations_rss_mb_max": max(post_mutation_rss),
            "mutation_memory_growth_mb_max": max(
                post - ready for ready, post in zip(ready_rss, post_mutation_rss, strict=True)
            ),
        },
        evaluations=evaluation.metrics,
        startup_profile=startup_profile,
        known_noise_sources=(
            "Windows filesystem/cache variance",
            "Streamlit rerun variance not yet measured",
        ),
        measurement_status="completed",
        hard_gate_passed=evaluation.passed,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if output_markdown is not None:
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.write_text(
            render_markdown_summary(
                budget_version=report.budget_version,
                raw_json_path=str(output_json),
                hard_gate_passed=report.hard_gate_passed,
                environment=report.environment,
                summaries=report.summaries,
                evaluations=report.evaluations,
                known_noise_sources=report.known_noise_sources,
                timestamp=report.timestamp,
                git_commit=report.git_commit,
                git_dirty=report.git_dirty,
                startup_profile=report.startup_profile,
            ),
            encoding="utf-8",
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, default=ROOT / "config" / "performance_budget.json")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "benchmarks" / "reports" / "performance-budget.local.json",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=ROOT / "docs" / "performance-report.local.md",
    )
    parser.add_argument("--offline", action="store_true", default=False)
    parser.add_argument("--warmups", type=int)
    parser.add_argument("--runs", type=int)
    parser.add_argument("--startup-runs", type=int)
    parser.add_argument("--reset-runs", type=int)
    parser.add_argument("--dashboard-runs", type=int)
    parser.add_argument("--write-reference-report", action="store_true")
    args = parser.parse_args()
    output_json = args.output_json
    output_markdown = args.output_markdown
    if args.write_reference_report:
        output_json = ROOT / "benchmarks" / "reports" / "performance-budget.json"
        output_markdown = ROOT / "docs" / "performance-report.md"
    if not args.offline:
        parser.error("Use --offline; the performance harness never downloads models implicitly.")
    try:
        report = run_performance_budget(
            budget_path=args.budget,
            output_json=output_json,
            output_markdown=output_markdown,
            offline=True,
            warmup_runs=args.warmups,
            measured_runs=args.runs,
            startup_runs=args.startup_runs,
            reset_runs=args.reset_runs,
            dashboard_runs=args.dashboard_runs,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"performance measurement infrastructure failed: {exc}\n")
    raise SystemExit(
        classify_exit_code(
            measurement_status=report.measurement_status,
            hard_gate_passed=report.hard_gate_passed,
        )
    )


if __name__ == "__main__":
    main()
