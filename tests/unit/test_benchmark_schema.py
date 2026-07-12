import hashlib
import json

from scripts.run_embedding_benchmark import BenchmarkPair, load_pairs


def test_loader_returns_complete_typed_incident_pairs():
    pairs = load_pairs("benchmarks/manglish_complaint_pairs.json")

    assert len(pairs) == 40
    assert all(isinstance(pair, BenchmarkPair) for pair in pairs)
    assert all(pair.category_a is not None for pair in pairs)
    assert all(pair.reported_at_a.tzinfo is not None for pair in pairs)
    assert {pair.split for pair in pairs} == {"calibration", "holdout"}
    assert sum(pair.split == "holdout" and pair.incident_expected == "match" for pair in pairs) == 10
    assert sum(pair.split == "holdout" and pair.incident_expected == "non_match" for pair in pairs) == 10


def test_benchmark_split_and_incident_labels_are_frozen():
    pairs = {pair.id: pair for pair in load_pairs("benchmarks/manglish_complaint_pairs.json")}

    assert pairs["P01"].split == "calibration"
    assert pairs["P11"].split == "holdout"
    assert pairs["N10"].split == "calibration"
    assert pairs["N11"].split == "holdout"
    assert all(pair.incident_expected == "match" for pair_id, pair in pairs.items() if pair_id.startswith("P"))
    assert all(pair.incident_expected == "non_match" for pair_id, pair in pairs.items() if pair_id.startswith("N"))


def test_benchmark_manifest_matches_fixture_bytes():
    manifest = json.loads(open("benchmarks/benchmark_manifest.json", encoding="utf-8").read())

    text_hash = hashlib.sha256(open("benchmarks/manglish_complaint_pairs.json", "rb").read()).hexdigest()
    metadata_hash = hashlib.sha256(open("benchmarks/incident_pair_metadata.json", "rb").read()).hexdigest()

    assert manifest["text_pairs_sha256"] == text_hash
    assert manifest["incident_metadata_sha256"] == metadata_hash
