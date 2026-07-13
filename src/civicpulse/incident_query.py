"""Read-side incident queries that keep API routes free of domain calculations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from civicpulse.config import PriorityPolicy
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    Complaint,
    Incident,
    PriorityAssessment,
    PriorityLevel,
    SensitiveLocation,
)
from civicpulse.priority import assess_priority
from civicpulse.repository import SQLiteRepository


@dataclass(frozen=True)
class IncidentListQuery:
    limit: int = 50
    offset: int = 0
    status: ClusteringStatus | None = None
    priority: PriorityLevel | None = None
    category: Category | None = None


@dataclass(frozen=True)
class IncidentRead:
    incident: Incident
    priority: PriorityAssessment | None
    policy_version: str


@dataclass(frozen=True)
class IncidentPage:
    items: tuple[IncidentRead, ...]
    limit: int
    offset: int
    total: int


class IncidentQueryService:
    """Build stable read models from persisted incident snapshots and evidence."""

    def __init__(
        self,
        repository: SQLiteRepository,
        priority_policy: PriorityPolicy,
        sensitive_locations: tuple[SensitiveLocation, ...] = (),
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.priority_policy = priority_policy
        self.sensitive_locations = sensitive_locations
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def _read(self, incident: Incident, complaints: list[Complaint]) -> IncidentRead:
        priority = (
            None
            if incident.status is ClusteringStatus.CONFLICT
            else assess_priority(
                incident,
                complaints,
                self.sensitive_locations,
                self.priority_policy,
                self.now_provider(),
            )
        )
        return IncidentRead(
            incident=incident,
            priority=priority,
            policy_version=self.priority_policy.policy_version,
        )

    @staticmethod
    def _priority_rank(read: IncidentRead) -> int:
        if read.priority is None:
            return -1
        return {
            PriorityLevel.CRITICAL: 3,
            PriorityLevel.HIGH: 2,
            PriorityLevel.MEDIUM: 1,
            PriorityLevel.LOW: 0,
            PriorityLevel.REVIEW_REQUIRED: -1,
        }[read.priority.level]

    def list_incidents(self, query: IncidentListQuery) -> IncidentPage:
        complaints = self.repository.list_complaints()
        reads = [self._read(incident, complaints) for incident in self.repository.list_incidents()]
        filtered = [
            read
            for read in reads
            if (query.status is None or read.incident.status is query.status)
            and (
                query.priority is None
                or (read.priority is not None and read.priority.level is query.priority)
            )
            and (query.category is None or query.category in read.incident.category_summary)
        ]
        ordered = sorted(
            filtered,
            key=lambda read: (
                -self._priority_rank(read),
                -read.incident.latest_reported_at.timestamp(),
                str(read.incident.incident_id),
            ),
        )
        return IncidentPage(
            items=tuple(ordered[query.offset : query.offset + query.limit]),
            limit=query.limit,
            offset=query.offset,
            total=len(ordered),
        )

    def get_incident(self, incident_id: UUID) -> IncidentRead | None:
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            return None
        return self._read(incident, self.repository.list_complaints())
