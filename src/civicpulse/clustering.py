"""Constrained incident resolution over typed pairwise relationships.

Only ``AUTO_MATCH`` edges form confirmed connected components. Review edges are
retained as candidate evidence and never bridge components; ``NO_MATCH`` edges
are excluded except when they expose a contradiction inside an auto component.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from uuid import UUID, NAMESPACE_URL, uuid5

from civicpulse.domain import (
    ClusteringStatus,
    Category,
    Complaint,
    Incident,
    MatchDecision,
    RelationshipDecisionSource,
    MatchState,
    RelationshipEdge,
    StrictModel,
)
from civicpulse.geo import haversine_metres


class ClusteringRelationship(StrictModel):
    """A pairwise matcher result addressed to two complaint IDs."""

    left_id: UUID
    right_id: UUID
    decision: MatchDecision
    decision_source: RelationshipDecisionSource = RelationshipDecisionSource.AUTOMATED
    matcher_recommendation: MatchState | None = None


class _DisjointSet:
    def __init__(self, values: Iterable[UUID]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: UUID) -> UUID:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, first: UUID, second: UUID) -> None:
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root != second_root:
            self.parent[second_root] = first_root


def _pair(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    return (left, right) if str(left) < str(right) else (right, left)


def _edge(relationship: ClusteringRelationship) -> RelationshipEdge:
    left_id, right_id = _pair(relationship.left_id, relationship.right_id)
    return RelationshipEdge(
        left_id=left_id,
        right_id=right_id,
        decision=relationship.decision.decision,
        reasons=relationship.decision.reasons,
        decision_source=relationship.decision_source,
        matcher_recommendation=relationship.matcher_recommendation or relationship.decision.matcher_recommendation,
    )


def _incident_id(member_ids: tuple[UUID, ...]) -> UUID:
    payload = "civicpulse-incident-v1:" + ",".join(str(member_id) for member_id in member_ids)
    return uuid5(NAMESPACE_URL, payload)


def _summarize(
    members: tuple[Complaint, ...],
    confirmed_edges: tuple[RelationshipEdge, ...],
    review_candidates: tuple[RelationshipEdge, ...],
    conflict_reasons: tuple[str, ...],
) -> Incident:
    complaint_ids = tuple(sorted((member.id for member in members), key=str))
    centroid_latitude = sum(member.latitude for member in members) / len(members)
    centroid_longitude = sum(member.longitude for member in members) / len(members)
    radius_metres = max(
        haversine_metres(
            centroid_latitude,
            centroid_longitude,
            member.latitude,
            member.longitude,
        )
        for member in members
    )
    categories_set: set[Category] = {
        member.category or Category.OTHER for member in members
    }
    categories = tuple(sorted(categories_set, key=lambda value: value.value))
    if conflict_reasons:
        status = ClusteringStatus.CONFLICT
    elif confirmed_edges:
        status = ClusteringStatus.CONFIRMED
    else:
        status = ClusteringStatus.ISOLATED
    candidate_ids = tuple(
        sorted(
            {
                edge.right_id if edge.left_id in complaint_ids else edge.left_id
                for edge in review_candidates
                if edge.left_id in complaint_ids or edge.right_id in complaint_ids
            },
            key=str,
        )
    )
    return Incident(
        incident_id=_incident_id(complaint_ids),
        complaint_ids=complaint_ids,
        report_count=len(complaint_ids),
        confirmed_edges=confirmed_edges,
        review_candidate_ids=candidate_ids,
        review_candidates=review_candidates,
        centroid_latitude=centroid_latitude,
        centroid_longitude=centroid_longitude,
        radius_metres=radius_metres,
        earliest_reported_at=min(member.reported_at for member in members),
        latest_reported_at=max(member.reported_at for member in members),
        category_summary=categories,
        status=status,
        conflict_reasons=conflict_reasons,
    )


def build_incidents(
    complaints: Sequence[Complaint],
    relationships: Iterable[ClusteringRelationship],
) -> list[Incident]:
    """Build stable incident components without transitive review contamination."""
    by_id = {complaint.id: complaint for complaint in complaints}
    if len(by_id) != len(complaints):
        raise ValueError("duplicate complaint IDs are not allowed")
    if not by_id:
        return []

    normalized: dict[tuple[UUID, UUID], RelationshipEdge] = {}
    for relationship in relationships:
        if relationship.left_id == relationship.right_id:
            raise ValueError("self relationships are not allowed")
        if relationship.left_id not in by_id or relationship.right_id not in by_id:
            raise ValueError("relationship references an unknown complaint")
        edge = _edge(relationship)
        key = (edge.left_id, edge.right_id)
        previous = normalized.get(key)
        if previous is not None:
            if previous.decision is not edge.decision:
                raise ValueError(f"contradictory duplicate relationship for {key[0]} and {key[1]}")
            continue
        normalized[key] = edge

    all_edges = tuple(sorted(normalized.values(), key=lambda value: (str(value.left_id), str(value.right_id))))
    auto_edges = tuple(edge for edge in all_edges if edge.decision is MatchState.AUTO_MATCH)
    review_edges = tuple(edge for edge in all_edges if edge.decision is MatchState.REVIEW_REQUIRED)
    rejected_edges = tuple(edge for edge in all_edges if edge.decision is MatchState.NO_MATCH)

    disjoint = _DisjointSet(by_id)
    for edge in auto_edges:
        disjoint.union(edge.left_id, edge.right_id)

    components: dict[UUID, list[Complaint]] = defaultdict(list)
    for complaint in by_id.values():
        components[disjoint.find(complaint.id)].append(complaint)

    incidents: list[Incident] = []
    for component_members in components.values():
        member_ids = {member.id for member in component_members}
        component_edges = tuple(
            edge
            for edge in auto_edges
            if edge.left_id in member_ids and edge.right_id in member_ids
        )
        component_review_edges = tuple(
            edge
            for edge in review_edges
            if edge.left_id in member_ids or edge.right_id in member_ids
        )
        contradictions = tuple(
            sorted(
                (
                    f"no_match contradicts confirmed component for {edge.left_id} and {edge.right_id}: "
                    + "; ".join(edge.reasons)
                )
                for edge in rejected_edges
                if edge.left_id in member_ids and edge.right_id in member_ids
            )
        )
        incidents.append(
            _summarize(
                tuple(component_members),
                component_edges,
                component_review_edges,
                contradictions,
            )
        )

    return sorted(incidents, key=lambda incident: tuple(map(str, incident.complaint_ids)))
