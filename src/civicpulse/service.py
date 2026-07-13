"""Application orchestration over matching, clustering, persistence, and priority."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID
from uuid import NAMESPACE_URL, uuid5

from civicpulse.categorize import classify_category
from civicpulse.clustering import ClusteringRelationship, build_incidents
from civicpulse.config import MatchingPolicy, PriorityPolicy
from civicpulse.domain import (
    ClusteringStatus,
    Category,
    Complaint,
    ComplaintInput,
    MatchState,
    RelationshipDecisionSource,
    RelationshipEdge,
    ReviewRecord,
    ReviewStatus,
    PriorityAssessment,
    ReviewResolution,
    SubmissionResult,
    SensitiveLocation,
    StrictModel,
)
from civicpulse.embeddings import EmbeddingProvider, cosine_similarity
from civicpulse.geo import haversine_metres, temporal_gap_seconds
from civicpulse.matching import match_pair
from civicpulse.normalize import normalize_text
from civicpulse.priority import assess_priority
from civicpulse.repository import SQLiteRepository
from pydantic import Field


class SeedManifest(StrictModel):
    seed_version: str = Field(min_length=1)
    content_sha256: str = Field(min_length=64, max_length=64)
    normalization_version: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    matching_policy_version: str = Field(min_length=1)
    priority_policy_version: str = Field(min_length=1)


class SeedComplaint(StrictModel):
    seed_key: str = Field(min_length=1)
    text: str = Field(min_length=3, max_length=2000)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    reported_at: datetime
    category: Category | None = None
    photo_path: str | None = None


class SeedReviewResolution(StrictModel):
    left_seed_key: str = Field(min_length=1)
    right_seed_key: str = Field(min_length=1)
    final_state: MatchState
    reviewer_id: str = Field(min_length=1)
    note: str | None = None


class SeedResult(StrictModel):
    seed_version: str
    content_sha256: str
    complaint_count: int = Field(ge=0)
    incident_ids: tuple[UUID, ...]
    review_ids: tuple[UUID, ...]
    priorities: tuple[PriorityAssessment, ...]


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class HealthComponent(StrictModel):
    status: HealthStatus
    message: str
    recovery_command: str | None = None


class HealthReport(StrictModel):
    status: HealthStatus
    core_ready: bool
    database: HealthComponent
    policies: HealthComponent
    embedding_model: HealthComponent
    seed: HealthComponent
    photo_provider: HealthComponent


class CivicPulseService:
    """Keep UI clients away from persistence and algorithmic state transitions."""

    def __init__(
        self,
        repository: SQLiteRepository,
        matching_policy: MatchingPolicy,
        priority_policy: PriorityPolicy,
        embedding_provider: EmbeddingProvider,
        sensitive_locations: Sequence[SensitiveLocation] = (),
        *,
        photo_healthcheck: Callable[[], None] | None = None,
    ) -> None:
        self.repository = repository
        self.matching_policy = matching_policy
        self.priority_policy = priority_policy
        self.embedding_provider = embedding_provider
        self.sensitive_locations = tuple(sensitive_locations)
        self.photo_healthcheck = photo_healthcheck

    @staticmethod
    def _component(
        status: HealthStatus,
        message: str,
        recovery_command: str | None = None,
    ) -> HealthComponent:
        return HealthComponent(
            status=status,
            message=message,
            recovery_command=recovery_command,
        )

    def health(self) -> HealthReport:
        """Check offline readiness without allowing optional photo failure to block core use."""
        try:
            self.repository.health_check()
            database = self._component(HealthStatus.HEALTHY, "database schema is available")
        except Exception:
            database = self._component(
                HealthStatus.UNAVAILABLE,
                "database is unavailable or has an unsupported schema",
                "uv run --offline python -c \"from civicpulse.repository import SQLiteRepository; SQLiteRepository('data/civicpulse.db').initialize()\"",
            )

        policy_errors: list[str] = []
        if self.matching_policy.model_name != self.embedding_provider.model_name:
            policy_errors.append("matching policy model does not match embedding provider")
        if self.matching_policy.normalization_version != self.embedding_provider.normalization_version:
            policy_errors.append("matching policy normalization version does not match embedding provider")
        if policy_errors:
            policies = self._component(
                HealthStatus.UNAVAILABLE,
                "; ".join(policy_errors),
                "Review config/matching_policy.json and reload the configured policy",
            )
        else:
            policies = self._component(
                HealthStatus.HEALTHY,
                f"matching {self.matching_policy.policy_version}; priority {self.priority_policy.policy_version}",
            )

        try:
            vectors = self.embedding_provider.embed(["CivicPulse offline model readiness check"])
            if not vectors or not vectors[0]:
                raise ValueError("empty embedding vector")
            embedding_model = self._component(
                HealthStatus.HEALTHY,
                f"{self.embedding_provider.model_name} is loaded and produced a vector",
            )
        except Exception:
            embedding_model = self._component(
                HealthStatus.UNAVAILABLE,
                "embedding model is unavailable or not cached",
                "uv run --offline python -m scripts.prewarm_model",
            )

        try:
            complaint_count = len(self.repository.list_complaints())
            incident_count = len(self.repository.list_incidents())
            if complaint_count == 0 or incident_count == 0:
                raise ValueError("seed state is empty")
            seed = self._component(
                HealthStatus.HEALTHY,
                f"seed state contains {complaint_count} complaints and {incident_count} incidents",
            )
        except Exception:
            seed = self._component(
                HealthStatus.UNAVAILABLE,
                "seed state is missing or cannot be read",
                "Call service.initialize_seed('data/seed_complaints.json') before serving traffic",
            )

        if self.photo_healthcheck is None:
            photo_provider = self._component(
                HealthStatus.DEGRADED,
                "optional photo provider is not configured; core workflow remains available",
            )
        else:
            try:
                self.photo_healthcheck()
                photo_provider = self._component(
                    HealthStatus.HEALTHY,
                    "optional photo provider is available",
                )
            except Exception:
                photo_provider = self._component(
                    HealthStatus.DEGRADED,
                    "optional photo provider is unavailable; core workflow remains available",
                )

        core_components = (database, policies, embedding_model, seed)
        core_ready = all(item.status is HealthStatus.HEALTHY for item in core_components)
        status = (
            HealthStatus.UNAVAILABLE
            if not core_ready
            else HealthStatus.DEGRADED
            if photo_provider.status is HealthStatus.DEGRADED
            else HealthStatus.HEALTHY
        )
        return HealthReport(
            status=status,
            core_ready=core_ready,
            database=database,
            policies=policies,
            embedding_model=embedding_model,
            seed=seed,
            photo_provider=photo_provider,
        )

    @staticmethod
    def _to_complaint(payload: ComplaintInput) -> Complaint:
        normalized = normalize_text(payload.text)
        prediction = classify_category(normalized)
        return Complaint(
            text=payload.text,
            normalized_text=normalized,
            latitude=payload.latitude,
            longitude=payload.longitude,
            reported_at=payload.reported_at,
            category=payload.category or prediction.category,
            photo_path=payload.photo_path,
        )

    def _relationships(self, complaints: Sequence[Complaint], vectors: Sequence[Sequence[float]]) -> list[ClusteringRelationship]:
        relationships: list[ClusteringRelationship] = []
        for index, first in enumerate(complaints):
            for second_index in range(index + 1, len(complaints)):
                second = complaints[second_index]
                first_category = first.category or Category.OTHER
                second_category = second.category or Category.OTHER
                if first_category is not Category.OTHER and second_category is not Category.OTHER and first_category is not second_category:
                    continue
                if haversine_metres(first.latitude, first.longitude, second.latitude, second.longitude) > self.matching_policy.geographic_radius_metres:
                    continue
                if temporal_gap_seconds(first.reported_at, second.reported_at) > self.matching_policy.temporal_window_days * 24 * 60 * 60:
                    continue
                decision = match_pair(
                    first,
                    second,
                    cosine_similarity(vectors[index], vectors[second_index]),
                    self.matching_policy,
                )
                relationships.append(
                    ClusteringRelationship(left_id=first.id, right_id=second.id, decision=decision)
                )
        return relationships

    @staticmethod
    def _graph_version(relationships: Sequence[ClusteringRelationship]) -> str:
        material = "|".join(
            f"{min(str(item.left_id), str(item.right_id))}:{max(str(item.left_id), str(item.right_id))}:{item.decision.decision.value}"
            for item in sorted(relationships, key=lambda value: (str(value.left_id), str(value.right_id)))
        )
        return sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _override_relationship(
        relationship: ClusteringRelationship,
        final_state: MatchState,
    ) -> ClusteringRelationship:
        decision = relationship.decision.model_copy(
            update={
                "decision": final_state,
                "auto_match": final_state is MatchState.AUTO_MATCH,
                "review_required": False,
                "decision_source": RelationshipDecisionSource.OFFICER_REVIEW,
                "matcher_recommendation": MatchState.REVIEW_REQUIRED,
                "reasons": (*relationship.decision.reasons, f"officer final decision: {final_state.value}"),
            }
        )
        return ClusteringRelationship(
            left_id=relationship.left_id,
            right_id=relationship.right_id,
            decision=decision,
            decision_source=RelationshipDecisionSource.OFFICER_REVIEW,
            matcher_recommendation=MatchState.REVIEW_REQUIRED,
        )

    def _apply_review_overrides(
        self,
        relationships: Sequence[ClusteringRelationship],
        current_review_id: UUID | None = None,
        current_final_state: MatchState | None = None,
    ) -> list[ClusteringRelationship]:
        overrides = {
            tuple(sorted((review.left_id, review.right_id), key=str)): review.final_relationship_state
            for review in self.repository.list_reviews()
            if review.status is not ReviewStatus.PENDING and review.final_relationship_state is not None
        }
        if current_review_id is not None and current_final_state is not None:
            current = self.repository.get_review(current_review_id)
            if current is not None:
                overrides[tuple(sorted((current.left_id, current.right_id), key=str))] = current_final_state
        return [
            self._override_relationship(item, overrides[key])
            if (key := tuple(sorted((item.left_id, item.right_id), key=str))) in overrides
            else item
            for item in relationships
        ]

    @staticmethod
    def _seed_content_hash(complaints: Sequence[SeedComplaint], resolutions: Sequence[SeedReviewResolution]) -> str:
        payload = {
            "complaints": [item.model_dump(mode="json") for item in sorted(complaints, key=lambda value: value.seed_key)],
            "review_resolutions": [
                item.model_dump(mode="json")
                for item in sorted(resolutions, key=lambda value: (value.left_seed_key, value.right_seed_key))
            ],
        }
        material = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(material).hexdigest()

    def _load_seed(self, path: str | Path) -> tuple[SeedManifest, list[SeedComplaint], list[SeedReviewResolution]]:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            manifest = SeedManifest.model_validate(payload["manifest"])
            complaints = [SeedComplaint.model_validate(item) for item in payload["complaints"]]
            resolutions = [SeedReviewResolution.model_validate(item) for item in payload.get("review_resolutions", [])]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid seed file: {exc}") from exc
        if manifest.content_sha256 != self._seed_content_hash(complaints, resolutions):
            raise ValueError("seed content checksum does not match manifest")
        if manifest.normalization_version != self.embedding_provider.normalization_version:
            raise ValueError("seed normalization version does not match embedding provider")
        if manifest.embedding_model != self.embedding_provider.model_name:
            raise ValueError("seed embedding model does not match embedding provider")
        if manifest.matching_policy_version != self.matching_policy.policy_version:
            raise ValueError("seed matching policy version does not match configured policy")
        if manifest.priority_policy_version != self.priority_policy.policy_version:
            raise ValueError("seed priority policy version does not match configured policy")
        return manifest, complaints, resolutions

    def initialize_seed(self, path: str | Path) -> SeedResult:
        return self._import_seed(path)

    def reset_seed(self, path: str | Path) -> SeedResult:
        return self._import_seed(path)

    def _import_seed(self, path: str | Path) -> SeedResult:
        manifest, records, resolutions = self._load_seed(path)
        ordered_records = sorted(records, key=lambda value: value.seed_key)
        if not ordered_records:
            raise ValueError("seed must contain at least one complaint")
        if len({record.seed_key for record in ordered_records}) != len(ordered_records):
            raise ValueError("seed_key values must be unique")
        complaints: list[Complaint] = []
        id_by_key: dict[str, UUID] = {}
        for record in ordered_records:
            complaint_id = uuid5(NAMESPACE_URL, f"civicpulse-seed:{manifest.seed_version}:{record.seed_key}")
            id_by_key[record.seed_key] = complaint_id
            complaints.append(
                Complaint(
                    id=complaint_id,
                    text=record.text,
                    normalized_text=normalize_text(record.text),
                    latitude=record.latitude,
                    longitude=record.longitude,
                    reported_at=record.reported_at,
                    category=record.category or classify_category(normalize_text(record.text)).category,
                    photo_path=record.photo_path,
                )
            )
        vectors = self.embedding_provider.embed([item.normalized_text for item in complaints])
        if len(vectors) != len(complaints) or not vectors:
            raise ValueError("seed embedding provider returned an unexpected row count")
        if any(len(vector) != manifest.embedding_dimension for vector in vectors):
            raise ValueError("seed embedding dimension does not match manifest")
        baseline_relationships = self._relationships(complaints, vectors)
        baseline_incidents = build_incidents(complaints, baseline_relationships)
        review_edges: dict[tuple[UUID, UUID], RelationshipEdge] = {}
        for incident in baseline_incidents:
            for edge in incident.review_candidates:
                left_id, right_id = edge.left_id, edge.right_id
                pair = (
                    (left_id, right_id)
                    if str(left_id) < str(right_id)
                    else (right_id, left_id)
                )
                review_edges[pair] = edge
        resolution_by_pair: dict[tuple[UUID, UUID], SeedReviewResolution] = {}
        for resolution in resolutions:
            if resolution.left_seed_key not in id_by_key or resolution.right_seed_key not in id_by_key:
                raise ValueError("seed review resolution references an unknown seed_key")
            if resolution.left_seed_key == resolution.right_seed_key:
                raise ValueError("seed review resolution cannot reference the same complaint twice")
            left_id = id_by_key[resolution.left_seed_key]
            right_id = id_by_key[resolution.right_seed_key]
            pair: tuple[UUID, UUID] = (
                (left_id, right_id) if str(left_id) < str(right_id) else (right_id, left_id)
            )
            if pair in resolution_by_pair:
                raise ValueError("duplicate seed review resolution")
            resolution_by_pair[pair] = resolution
        unknown_resolution = set(resolution_by_pair) - set(review_edges)
        if unknown_resolution:
            raise ValueError("seed review resolution does not reference a pending review")
        review_records: list[ReviewRecord] = []
        for pair, edge in sorted(review_edges.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))):
            resolution = resolution_by_pair.get(pair)
            if resolution is not None and resolution.final_state not in (MatchState.AUTO_MATCH, MatchState.NO_MATCH):
                raise ValueError("seed review resolution must be auto_match or no_match")
            created_at = min(item.reported_at for item in complaints)
            review_records.append(
                ReviewRecord(
                    review_id=uuid5(NAMESPACE_URL, "civicpulse-review-v1:" + ":".join(str(value) for value in pair)),
                    left_id=pair[0],
                    right_id=pair[1],
                    matcher_recommendation=MatchState.REVIEW_REQUIRED,
                    matcher_reasons=edge.reasons,
                    status=ReviewStatus.APPROVED if resolution and resolution.final_state is MatchState.AUTO_MATCH else ReviewStatus.REJECTED if resolution else ReviewStatus.PENDING,
                    created_at=created_at,
                    resolved_at=created_at if resolution else None,
                    reviewed_by=resolution.reviewer_id if resolution else None,
                    review_note=resolution.note if resolution else None,
                    final_relationship_state=resolution.final_state if resolution else None,
                    decision_source=RelationshipDecisionSource.OFFICER_REVIEW if resolution else None,
                    graph_version_at_creation=self._graph_version(baseline_relationships),
                    version=2 if resolution else 1,
                )
            )
        final_relationships = list(baseline_relationships)
        for resolution in resolutions:
            left_id = id_by_key[resolution.left_seed_key]
            right_id = id_by_key[resolution.right_seed_key]
            pair: tuple[UUID, UUID] = (
                (left_id, right_id) if str(left_id) < str(right_id) else (right_id, left_id)
            )
            final_relationships = [
                self._override_relationship(item, resolution.final_state) if tuple(sorted((item.left_id, item.right_id), key=str)) == pair else item
                for item in final_relationships
            ]
        incidents = build_incidents(complaints, final_relationships)
        seed_now = max(item.reported_at for item in complaints)
        priorities = tuple(
            assess_priority(incident, complaints, self.sensitive_locations, self.priority_policy, seed_now)
            for incident in incidents
        )
        embedding_map = {complaint.id: vector for complaint, vector in zip(complaints, vectors, strict=True)}
        self.repository.replace_dataset(
            complaints,
            embedding_map,
            incidents,
            review_records,
            f"seed:{manifest.seed_version}",
            self.embedding_provider.model_name,
            self.embedding_provider.normalization_version,
        )
        return SeedResult(
            seed_version=manifest.seed_version,
            content_sha256=manifest.content_sha256,
            complaint_count=len(complaints),
            incident_ids=tuple(sorted((incident.incident_id for incident in incidents), key=str)),
            review_ids=tuple(sorted((review.review_id for review in review_records), key=str)),
            priorities=priorities,
        )

    def submit_complaint(
        self,
        payload: ComplaintInput,
        idempotency_key: str,
        *,
        now: datetime | None = None,
    ) -> SubmissionResult:
        existing = self.repository.get_by_idempotency_key(idempotency_key)
        candidate = existing or self._to_complaint(payload)
        current = self.repository.list_complaints()
        if existing is None:
            current = [*current, candidate]

        # Model work happens before the first write for a new command.
        vectors = self.embedding_provider.embed([item.normalized_text for item in current])
        if existing is None:
            try:
                self.repository.add_complaint(candidate, idempotency_key)
                self.repository.save_embedding(
                    candidate.id,
                    vectors[-1],
                    self.embedding_provider.model_name,
                    self.embedding_provider.normalization_version,
                )
            except Exception:
                self.repository.delete_complaint(candidate.id)
                raise

        try:
            relationships = self._relationships(current, vectors)
            incidents = build_incidents(current, relationships)
            self.repository.replace_incidents(incidents)
            graph_version = self._graph_version(relationships)
            created_at = now or datetime.now(timezone.utc)
            for incident in incidents:
                for edge in incident.review_candidates:
                    self.repository.create_review(edge, created_at, graph_version)
        except Exception:
            if existing is None:
                self.repository.delete_complaint(candidate.id)
            raise

        target = next(incident for incident in incidents if candidate.id in incident.complaint_ids)
        priority = assess_priority(
            target,
            current,
            self.sensitive_locations,
            self.priority_policy,
            now or datetime.now(timezone.utc),
        )
        return SubmissionResult(
            complaint=candidate,
            incident=target,
            priority=priority,
            created=existing is None,
        )

    def resolve_review(
        self,
        review_id: UUID,
        *,
        approve: bool,
        reviewer_id: str,
        note: str | None = None,
        now: datetime | None = None,
    ) -> ReviewResolution:
        review = self.repository.get_review(review_id)
        if review is None:
            raise ValueError("unknown review")
        if review.status is not ReviewStatus.PENDING:
            raise ValueError("review is not pending")
        final_state = MatchState.AUTO_MATCH if approve else MatchState.NO_MATCH
        previous_incidents = self.repository.list_incidents()
        complaints = self.repository.list_complaints()
        vectors = self.embedding_provider.embed([item.normalized_text for item in complaints])
        relationships = self._relationships(complaints, vectors)
        relationships = self._apply_review_overrides(relationships, review_id, final_state)
        incidents = build_incidents(complaints, relationships)
        clock = now or datetime.now(timezone.utc)
        affected_ids = tuple(sorted((review.left_id, review.right_id), key=str))
        affected_incidents = tuple(
            incident for incident in incidents if set(affected_ids) & set(incident.complaint_ids)
        )
        priorities = tuple(
            assess_priority(incident, complaints, self.sensitive_locations, self.priority_policy, clock)
            for incident in affected_incidents
        )
        self.repository.apply_review_resolution(
            review_id,
            final_state,
            reviewer_id,
            note,
            clock,
            incidents,
        )
        previous_ids = tuple(
            sorted(
                (incident.incident_id for incident in previous_incidents if set(affected_ids) & set(incident.complaint_ids)),
                key=str,
            )
        )
        new_ids = tuple(sorted((incident.incident_id for incident in affected_incidents), key=str))
        conflict_status = (
            ClusteringStatus.CONFLICT
            if any(incident.status is ClusteringStatus.CONFLICT for incident in affected_incidents)
            else None
        )
        return ReviewResolution(
            review_id=review_id,
            previous_status=ReviewStatus.PENDING,
            final_status=ReviewStatus.APPROVED if approve else ReviewStatus.REJECTED,
            final_relationship_state=final_state,
            affected_complaint_ids=affected_ids,
            previous_incident_ids=previous_ids,
            new_incident_ids=new_ids,
            conflict_status=conflict_status,
            resulting_priorities=priorities,
            reviewer_id=reviewer_id,
            note=note,
        )
