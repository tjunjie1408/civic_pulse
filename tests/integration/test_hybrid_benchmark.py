from civicpulse.config import load_matching_policy
from scripts.run_hybrid_benchmark import evaluate_pairs
from scripts.run_embedding_benchmark import load_pairs


POLICY = load_matching_policy("config/matching_policy.json")


def test_calibration_threshold_does_not_use_holdout_scores():
    pairs = load_pairs("benchmarks/manglish_complaint_pairs.json")
    scores = {
        pair.id: (0.90 if pair.semantic_expected == "match" else 0.50)
        for pair in pairs
    }
    scores.update({"P11": 0.89, "N13": 0.95})

    report = evaluate_pairs(pairs, scores, POLICY)

    assert report.calibration_threshold == 0.90
    assert report.holdout_false_auto_merges == 1
    assert report.holdout_positive_no_matches == 0
    assert report.clear_positive_auto_rate == 0
    assert report.passed is False


def test_hybrid_gate_passes_with_zero_false_merges_and_four_true_matches():
    pairs = load_pairs("benchmarks/manglish_complaint_pairs.json")
    scores = {
        pair.id: (0.90 if pair.semantic_expected == "match" else 0.50)
        for pair in pairs
    }
    scores.update({pair_id: 0.95 for pair_id in ("P16", "P17", "P18", "P19")})

    report = evaluate_pairs(pairs, scores, POLICY)

    assert report.holdout_false_auto_merges == 0
    assert report.holdout_positive_no_matches == 0
    assert report.holdout_clear_auto_matches == 4
    assert report.clear_positive_auto_rate == 1
    assert report.holdout_review_required >= 1
    assert report.passed is True
