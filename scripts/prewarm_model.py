"""Load the configured local embedding model and run one fixed readiness sentence."""

from __future__ import annotations

import argparse
from pathlib import Path

from civicpulse.config import load_matching_policy
from civicpulse.embeddings import ModelCacheInvalid, SentenceTransformerProvider
from civicpulse.runtime import load_seed_manifest


def prewarm(
    policy_path: str | Path = "config/matching_policy.json",
    *,
    offline: bool = False,
    seed_path: str | Path = "data/seed_complaints.json",
) -> int:
    policy = load_matching_policy(policy_path)
    manifest = load_seed_manifest(seed_path)
    provider = SentenceTransformerProvider.for_prewarm(
        policy.model_name,
        policy.normalization_version,
        offline=offline,
        expected_dimension=manifest.embedding_dimension,
    )
    vectors = provider.embed(["CivicPulse offline model readiness check"])
    if (
        len(vectors) != 1
        or not vectors[0]
        or len(vectors[0]) != manifest.embedding_dimension
    ):
        raise ModelCacheInvalid("embedding_model_cache_invalid: readiness dimension mismatch")
    print(f"ready: {provider.model_name} ({len(vectors[0])} dimensions)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        default="config/matching_policy.json",
        help="path to the versioned matching policy JSON",
    )
    parser.add_argument(
        "--seed",
        default="data/seed_complaints.json",
        help="path to the seed manifest used for dimension validation",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="only use the local model cache; do not download",
    )
    args = parser.parse_args()
    return prewarm(args.policy, offline=args.offline, seed_path=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
