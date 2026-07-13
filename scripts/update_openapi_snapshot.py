"""Explicitly update the committed OpenAPI v1 snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.openapi_snapshot import write_openapi_snapshot
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from openapi_snapshot import write_openapi_snapshot


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "openapi-v1.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Snapshot path to update.")
    args = parser.parse_args()
    print(write_openapi_snapshot(args.output))


if __name__ == "__main__":
    main()
