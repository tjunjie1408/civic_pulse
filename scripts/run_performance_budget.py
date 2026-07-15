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
from typing import Literal, Protocol, cast
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
ROOT = Path(__file__).resolve().parents[1]


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
    if metric in {"cached_process_readiness_seconds", "cold_start_ms", "ready_rss_mb"}:
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


def _complaint_payload(text: str) -> dict[str, object]:
    return {
        "text": text,
        "category": "blocked_drain",
        "latitude": 3.2501,
        "longitude": 101.7501,
        "reported_at": datetime.now(UTC).isoformat(),
    }


def _submit(client: ClientLike, text: str, key: str) -> None:
    response = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": key},
        json=_complaint_payload(text),
    )
    if response.status_code != 201:
        raise RuntimeError(f"performance submission failed with status {response.status_code}")


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

    for _ in range(runs):
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
        samples["submission_isolated_p95_ms"].append(
            _timed_milliseconds(
                lambda: _submit(client, f"isolated-{time.perf_counter_ns()}", "isolated-key")
            )
        )
        _reset(client)
        _submit(client, "Pothole at Block A Jalan Ampang", "auto-seed")
        samples["submission_auto_match_p95_ms"].append(
            _timed_milliseconds(
                lambda: _submit(client, "Road hole at Blok A Jln Ampang", "auto-measured")
            )
        )
        _reset(client)
        _submit(client, "Pothole at Block A Jalan Ampang", "review-seed")
        samples["submission_review_required_p95_ms"].append(
            _timed_milliseconds(lambda: _submit(client, "Pothole near school", "review-measured"))
        )

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
    return children[0] if children else parent_pid


def measure_cached_process_readiness(*, runs: int, warmup_runs: int = 0) -> list[float]:
    """Measure fresh API child process startup through a ready health response."""
    if warmup_runs:
        measure_cached_process_readiness(runs=warmup_runs)
    samples: list[float] = []
    for _ in range(runs):
        with tempfile.TemporaryDirectory(prefix="civicpulse-perf-") as directory:
            port = _free_port()
            environment = build_child_environment()
            environment["CIVICPULSE_DB_PATH"] = str(Path(directory) / "runtime.db")
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
                deadline = time.perf_counter() + 30.0
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
                    raise RuntimeError("API child process did not become ready within 30 seconds")
                samples.append(time.perf_counter() - started)
            finally:
                if process is not None:
                    _terminate_process_tree(process)
    return samples


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
                deadline = time.perf_counter() + 30.0
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


def measure_dashboard_first_usable(*, runs: int, warmup_runs: int = 0) -> list[float]:
    """Measure API/Dashboard startup to a visible operational marker."""
    from streamlit.testing.v1 import AppTest

    if warmup_runs:
        measure_dashboard_first_usable(runs=warmup_runs)
    samples: list[float] = []
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
            started = time.perf_counter()
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
                samples.append(time.perf_counter() - started)
            finally:
                if previous_url is None:
                    os.environ.pop("CIVICPULSE_API_URL", None)
                else:
                    os.environ["CIVICPULSE_API_URL"] = previous_url
                if dashboard_process is not None:
                    _terminate_process_tree(dashboard_process)
                _terminate_process_tree(api_process)
    return samples


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
        readiness = measure_cached_process_readiness(
            runs=budget.startup_runs, warmup_runs=budget.warmup_runs
        )
        raw_samples = {"cached_process_readiness_seconds": readiness}
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
        raw_samples["dashboard_first_usable_seconds"] = measure_dashboard_first_usable(
            runs=budget.dashboard_runs, warmup_runs=budget.warmup_runs
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
            "time.perf_counter with API readiness, Streamlit root response, and AppTest marker"
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
        raise SystemExit(
            "Use --offline; the performance harness never downloads models implicitly."
        )
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
        raise SystemExit(f"performance measurement infrastructure failed: {exc}") from exc
    raise SystemExit(
        classify_exit_code(
            measurement_status=report.measurement_status,
            hard_gate_passed=report.hard_gate_passed,
        )
    )


if __name__ == "__main__":
    main()
