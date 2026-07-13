"""Generate a canonical OpenAPI document at an explicit output path."""

from __future__ import annotations

import argparse

try:
    from scripts.openapi_snapshot import write_openapi_snapshot
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from openapi_snapshot import write_openapi_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Path for the generated JSON document.")
    args = parser.parse_args()
    print(write_openapi_snapshot(args.output))


if __name__ == "__main__":
    main()
