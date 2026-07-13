"""Load the configured local embedding model and run one fixed readiness sentence."""

from __future__ import annotations

import argparse
from pathlib import Path

from civicpulse.config import load_matching_policy
from civicpulse.embeddings import SentenceTransformerProvider


def prewarm(policy_path: str | Path = "config/matching_policy.json") -> int:
    policy = load_matching_policy(policy_path)
    provider = SentenceTransformerProvider(policy.model_name, policy.normalization_version)
    vectors = provider.embed(["CivicPulse offline model readiness check"])
    if not vectors or not vectors[0]:
        raise RuntimeError("model returned an empty readiness vector")
    print(f"ready: {provider.model_name} ({len(vectors[0])} dimensions)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        default="config/matching_policy.json",
        help="path to the versioned matching policy JSON",
    )
    args = parser.parse_args()
    return prewarm(args.policy)


if __name__ == "__main__":
    raise SystemExit(main())
