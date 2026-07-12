import json

import pytest
from pydantic import ValidationError

from civicpulse.config import load_matching_policy, load_priority_policy


def test_versioned_policies_load_from_json_files():
    matching = load_matching_policy("config/matching_policy.json")
    priority = load_priority_policy("config/priority_policy.json")

    assert matching.policy_version == "matching-v1"
    assert matching.geographic_radius_metres == 500
    assert priority.policy_version == "priority-v1"
    assert priority.band_thresholds.critical == 7


def test_missing_matching_key_is_rejected(tmp_path):
    payload = json.loads(open("config/matching_policy.json", encoding="utf-8").read())
    del payload["semantic_threshold"]
    path = tmp_path / "matching.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="semantic_threshold"):
        load_matching_policy(path)


def test_unknown_priority_key_is_rejected(tmp_path):
    payload = json.loads(open("config/priority_policy.json", encoding="utf-8").read())
    payload["unexpected"] = True
    path = tmp_path / "priority.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected"):
        load_priority_policy(path)


def test_invalid_matching_threshold_is_rejected(tmp_path):
    payload = json.loads(open("config/matching_policy.json", encoding="utf-8").read())
    payload["semantic_threshold"] = 1.1
    path = tmp_path / "matching.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="semantic_threshold"):
        load_matching_policy(path)
