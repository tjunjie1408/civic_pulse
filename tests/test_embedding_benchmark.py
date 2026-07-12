from pathlib import Path
import unittest

from scripts.run_embedding_benchmark import find_best_threshold, load_pairs


DATA_PATH = Path("benchmarks/manglish_complaint_pairs.json")


class EmbeddingBenchmarkTest(unittest.TestCase):
    def test_benchmark_contains_expected_semantic_pair_coverage(self):
        pairs = load_pairs(DATA_PATH)

        self.assertEqual(len(pairs), 40)
        self.assertEqual({pair.semantic_expected for pair in pairs}, {"match", "non_match"})
        self.assertEqual(sum(pair.semantic_expected == "match" for pair in pairs), 22)
        self.assertEqual(sum(pair.semantic_expected == "non_match" for pair in pairs), 18)

    def test_time_window_cases_are_semantic_matches_but_incident_non_matches(self):
        pairs_by_id = {pair.id: pair for pair in load_pairs(DATA_PATH)}

        for pair_id in ("N09", "N15"):
            self.assertEqual(pairs_by_id[pair_id].semantic_expected, "match")
            self.assertEqual(pairs_by_id[pair_id].incident_expected, "non_match")

    def test_threshold_selection_prefers_a_threshold_with_no_false_merges_when_possible(self):
        labeled_scores = [
            (0.93, "match"),
            (0.88, "match"),
            (0.82, "match"),
            (0.66, "non_match"),
            (0.61, "non_match"),
            (0.55, "non_match"),
        ]

        result = find_best_threshold(labeled_scores)

        self.assertEqual(result["false_merges"], 0)
        self.assertGreater(result["threshold"], 0.66)
        self.assertLessEqual(result["threshold"], 0.82)
