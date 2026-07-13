from datetime import datetime, timezone
from uuid import UUID

import pytest

from civicpulse.clustering import build_incidents
from civicpulse.domain import Category, Complaint, LocationCompatibility, MatchDecision, MatchState
from civicpulse.repository import SQLiteRepository


NOW = datetime(2026, 7, 12, 8, tzinfo=timezone.utc)


def complaint(ident: int) -> Complaint:
    return Complaint(
        id=UUID(f"00000000-0000-0000-0000-{ident:012d}"),
        text=f"Pothole at Block {ident}",
        normalized_text=f"pothole at block {ident}",
        category=Category.POTHOLE,
        latitude=3.1390 + ident * 0.00001,
        longitude=101.6869,
        reported_at=NOW,
    )


def auto(left: UUID, right: UUID):
    from civicpulse.clustering import ClusteringRelationship

    return ClusteringRelationship(
        left_id=left,
        right_id=right,
        decision=MatchDecision(
            decision=MatchState.AUTO_MATCH,
            auto_match=True,
            review_required=False,
            category_compatible=True,
            location_compatibility=LocationCompatibility.COMPATIBLE,
            first_location_entities=(),
            second_location_entities=(),
            distance_metres=10,
            time_gap_seconds=60,
            semantic_similarity=0.95,
            reasons=("same incident",),
        ),
    )


def test_replace_incidents_is_atomic_and_rejects_unknown_members(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    first = complaint(1)
    second = complaint(2)
    repository.add_complaint(first, "one")
    repository.add_complaint(second, "two")
    initial = build_incidents([first, second], [auto(first.id, second.id)])
    repository.replace_incidents(initial)

    repository.failure_hook = lambda event: (_ for _ in ()).throw(RuntimeError(event)) if event == "after_incident_insert" else None
    with pytest.raises(RuntimeError, match="after_incident_insert"):
        repository.replace_incidents(initial)
    assert repository.list_incidents() == initial

    unknown = complaint(3)
    with pytest.raises(ValueError, match="unknown complaint"):
        repository.replace_incidents(build_incidents([unknown], []))
    assert repository.list_incidents() == initial
