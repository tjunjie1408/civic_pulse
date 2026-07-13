"""SQLite persistence boundaries for complaints and derived incidents."""

from __future__ import annotations

import json
import sqlite3
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from collections.abc import Iterable, Mapping
from typing import Callable, Generator
from uuid import UUID, NAMESPACE_URL, uuid5

from civicpulse.domain import (
    Category,
    Complaint,
    Incident,
    MatchDecision,
    RelationshipDecisionSource,
    RelationshipEdge,
    ReviewRecord,
    ReviewStatus,
    MatchState,
)


@dataclass(frozen=True)
class SubmissionRecord:
    complaint: Complaint
    request_fingerprint: str | None
    result_payload: str | None


class SQLiteRepository:
    """Small transactional repository with explicit schema and rollback hooks."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.failure_hook: Callable[[str], None] | None = None

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
                current = connection.execute("SELECT version FROM schema_version").fetchone()
                if current is None:
                    connection.execute("INSERT INTO schema_version(version) VALUES(1)")
                elif current[0] != 1:
                    raise ValueError(f"unsupported schema version: {current[0]}")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS complaints (
                        id TEXT PRIMARY KEY,
                        text TEXT NOT NULL CHECK(length(trim(text)) >= 3),
                        normalized_text TEXT NOT NULL CHECK(length(trim(normalized_text)) >= 3),
                        latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
                        longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
                        reported_at TEXT NOT NULL,
                        category TEXT NOT NULL CHECK(category IN ('pothole','blocked_drain','flooding','rubbish','street_light','other')),
                        photo_path TEXT
                    );
                    CREATE TABLE IF NOT EXISTS embeddings (
                        complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                        vector BLOB NOT NULL,
                        dimension INTEGER NOT NULL CHECK(dimension > 0),
                        dtype TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        normalization_version TEXT NOT NULL,
                        PRIMARY KEY(complaint_id, model_version, normalization_version)
                    );
                    CREATE TABLE IF NOT EXISTS incidents (
                        incident_id TEXT PRIMARY KEY,
                        report_count INTEGER NOT NULL CHECK(report_count >= 1),
                        centroid_latitude REAL NOT NULL CHECK(centroid_latitude BETWEEN -90 AND 90),
                        centroid_longitude REAL NOT NULL CHECK(centroid_longitude BETWEEN -180 AND 180),
                        radius_metres REAL NOT NULL CHECK(radius_metres >= 0),
                        earliest_reported_at TEXT NOT NULL,
                        latest_reported_at TEXT NOT NULL,
                        category_summary TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('confirmed','isolated','conflict')),
                        conflict_reasons TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS incident_members (
                        incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
                        complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                        PRIMARY KEY(incident_id, complaint_id),
                        UNIQUE(complaint_id)
                    );
                    CREATE TABLE IF NOT EXISTS match_edges (
                        left_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                        right_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                        edge_kind TEXT NOT NULL CHECK(edge_kind IN ('confirmed','review','rejected')),
                        matcher_recommendation TEXT,
                        decision_source TEXT NOT NULL CHECK(decision_source IN ('automated','officer_review')),
                        reasons TEXT NOT NULL,
                        PRIMARY KEY(left_id, right_id, edge_kind)
                    );
                    CREATE TABLE IF NOT EXISTS photo_assessments (
                        complaint_id TEXT PRIMARY KEY REFERENCES complaints(id) ON DELETE CASCADE,
                        payload TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS submission_keys (
                        idempotency_key TEXT PRIMARY KEY,
                        complaint_id TEXT NOT NULL UNIQUE REFERENCES complaints(id) ON DELETE CASCADE
                        ,request_fingerprint TEXT
                        ,result_payload TEXT
                    );
                    CREATE TABLE IF NOT EXISTS reviews (
                        review_id TEXT PRIMARY KEY,
                        left_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                        right_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                        matcher_recommendation TEXT NOT NULL CHECK(matcher_recommendation='review_required'),
                        matcher_reasons TEXT NOT NULL,
                        matcher_evidence TEXT,
                        status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
                        created_at TEXT NOT NULL,
                        resolved_at TEXT,
                        reviewed_by TEXT,
                        review_note TEXT,
                        final_relationship_state TEXT,
                        decision_source TEXT,
                        graph_version_at_creation TEXT NOT NULL,
                        version INTEGER NOT NULL CHECK(version >= 1),
                        UNIQUE(left_id, right_id)
                    );
                    """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(submission_keys)").fetchall()
                }
                if "request_fingerprint" not in columns:
                    connection.execute("ALTER TABLE submission_keys ADD COLUMN request_fingerprint TEXT")
                if "result_payload" not in columns:
                    connection.execute("ALTER TABLE submission_keys ADD COLUMN result_payload TEXT")
                review_columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(reviews)").fetchall()
                }
                if "matcher_evidence" not in review_columns:
                    connection.execute("ALTER TABLE reviews ADD COLUMN matcher_evidence TEXT")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def health_check(self) -> None:
        """Raise when the database cannot be opened or has an unsupported schema."""
        with self.connect() as connection:
            row = connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None or row["version"] != 1:
                raise ValueError("unsupported or uninitialized database schema")
            connection.execute("SELECT 1 FROM complaints LIMIT 1").fetchone()

    @staticmethod
    def _complaint_from_row(row: sqlite3.Row) -> Complaint:
        return Complaint(
            id=UUID(row["id"]),
            text=row["text"],
            normalized_text=row["normalized_text"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            reported_at=datetime.fromisoformat(row["reported_at"]),
            category=Category(row["category"]),
            photo_path=row["photo_path"],
        )

    def add_complaint(
        self,
        complaint: Complaint,
        idempotency_key: str,
        request_fingerprint: str | None = None,
    ) -> Complaint:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT complaint_id FROM submission_keys WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    row = connection.execute(
                        "SELECT * FROM complaints WHERE id=?", (existing["complaint_id"],)
                    ).fetchone()
                    if row is None:
                        raise RuntimeError("idempotency key references missing complaint")
                    connection.commit()
                    return self._complaint_from_row(row)
                connection.execute(
                    "INSERT INTO complaints(id,text,normalized_text,latitude,longitude,reported_at,category,photo_path) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        str(complaint.id),
                        complaint.text,
                        complaint.normalized_text,
                        complaint.latitude,
                        complaint.longitude,
                        complaint.reported_at.isoformat(),
                        (complaint.category or Category.OTHER).value,
                        complaint.photo_path,
                    ),
                )
                connection.execute(
                    "INSERT INTO submission_keys(idempotency_key,complaint_id,request_fingerprint) VALUES(?,?,?)",
                    (idempotency_key, str(complaint.id), request_fingerprint),
                )
                connection.commit()
                return complaint
            except Exception:
                connection.rollback()
                raise

    def get_by_idempotency_key(self, idempotency_key: str) -> Complaint | None:
        record = self.get_submission_record(idempotency_key)
        return None if record is None else record.complaint

    def get_submission_record(self, idempotency_key: str) -> SubmissionRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT c.*,s.request_fingerprint,s.result_payload "
                "FROM complaints c JOIN submission_keys s ON s.complaint_id=c.id "
                "WHERE s.idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return SubmissionRecord(
            complaint=self._complaint_from_row(row),
            request_fingerprint=row["request_fingerprint"],
            result_payload=row["result_payload"],
        )

    def save_submission_result(self, idempotency_key: str, result_payload: str) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                updated = connection.execute(
                    "UPDATE submission_keys SET result_payload=? WHERE idempotency_key=?",
                    (result_payload, idempotency_key),
                )
                if updated.rowcount != 1:
                    raise ValueError("unknown idempotency key")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def delete_complaint(self, complaint_id: UUID) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("DELETE FROM complaints WHERE id=?", (str(complaint_id),))
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def list_complaints(self) -> list[Complaint]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM complaints ORDER BY id").fetchall()
        return [self._complaint_from_row(row) for row in rows]

    def save_embedding(
        self,
        complaint_id: UUID,
        vector: Iterable[float],
        model_version: str,
        normalization_version: str,
    ) -> None:
        values = tuple(float(value) for value in vector)
        if not values or not all(isfinite(value) for value in values):
            raise ValueError("embedding vector must contain finite values")
        payload = struct.pack(f"<{len(values)}f", *values)
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM complaints WHERE id=?", (str(complaint_id),)).fetchone() is None:
                    raise ValueError("unknown complaint for embedding")
                connection.execute(
                    "INSERT OR REPLACE INTO embeddings(complaint_id,vector,dimension,dtype,model_version,normalization_version) VALUES(?,?,?,?,?,?)",
                    (str(complaint_id), payload, len(values), "float32", model_version, normalization_version),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def replace_incidents(self, incidents: Iterable[Incident]) -> None:
        incident_list = list(incidents)
        with self.connect() as connection:
            existing_ids = {row["id"] for row in connection.execute("SELECT id FROM complaints").fetchall()}
            member_ids = [str(complaint_id) for incident in incident_list for complaint_id in incident.complaint_ids]
            if any(complaint_id not in existing_ids for complaint_id in member_ids):
                raise ValueError("unknown complaint referenced by incident")
            if len(member_ids) != len(set(member_ids)):
                raise ValueError("complaint belongs to multiple incidents")
            if set(member_ids) != existing_ids:
                raise ValueError("incident replacement must cover every stored complaint")
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM incident_members")
                connection.execute("DELETE FROM match_edges")
                connection.execute("DELETE FROM incidents")
                for incident in incident_list:
                    connection.execute(
                        "INSERT INTO incidents(incident_id,report_count,centroid_latitude,centroid_longitude,radius_metres,earliest_reported_at,latest_reported_at,category_summary,status,conflict_reasons,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            str(incident.incident_id),
                            incident.report_count,
                            incident.centroid_latitude,
                            incident.centroid_longitude,
                            incident.radius_metres,
                            incident.earliest_reported_at.isoformat(),
                            incident.latest_reported_at.isoformat(),
                            json.dumps([category.value for category in incident.category_summary]),
                            incident.status.value,
                            json.dumps(list(incident.conflict_reasons)),
                            incident.model_dump_json(),
                        ),
                    )
                    if self.failure_hook is not None:
                        self.failure_hook("after_incident_insert")
                    for complaint_id in incident.complaint_ids:
                        connection.execute(
                            "INSERT INTO incident_members(incident_id,complaint_id) VALUES(?,?)",
                            (str(incident.incident_id), str(complaint_id)),
                        )
                    for edge in (*incident.confirmed_edges, *incident.review_candidates):
                        edge_kind = "confirmed" if edge.decision.value == "auto_match" else "review"
                        connection.execute(
                            "INSERT OR IGNORE INTO match_edges(left_id,right_id,edge_kind,matcher_recommendation,decision_source,reasons) VALUES(?,?,?,?,?,?)",
                            (
                                str(edge.left_id),
                                str(edge.right_id),
                                edge_kind,
                                edge.matcher_recommendation.value if edge.matcher_recommendation else None,
                                edge.decision_source.value,
                                json.dumps(list(edge.reasons)),
                            ),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _review_id(left_id: UUID, right_id: UUID) -> UUID:
        ordered = sorted((str(left_id), str(right_id)))
        return uuid5(NAMESPACE_URL, "civicpulse-review-v1:" + ":".join(ordered))

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> ReviewRecord:
        return ReviewRecord(
            review_id=UUID(row["review_id"]),
            left_id=UUID(row["left_id"]),
            right_id=UUID(row["right_id"]),
            matcher_recommendation=MatchState(row["matcher_recommendation"]),
            matcher_reasons=tuple(json.loads(row["matcher_reasons"])),
            matcher_evidence=(
                MatchDecision.model_validate_json(row["matcher_evidence"])
                if row["matcher_evidence"]
                else None
            ),
            status=ReviewStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            reviewed_by=row["reviewed_by"],
            review_note=row["review_note"],
            final_relationship_state=MatchState(row["final_relationship_state"])
            if row["final_relationship_state"]
            else None,
            decision_source=RelationshipDecisionSource(row["decision_source"])
            if row["decision_source"]
            else None,
            graph_version_at_creation=row["graph_version_at_creation"],
            version=row["version"],
        )

    def create_review(self, edge: RelationshipEdge, created_at: datetime, graph_version: str) -> ReviewRecord:
        if edge.decision is not MatchState.REVIEW_REQUIRED:
            raise ValueError("only review-required edges can create review records")
        review_id = self._review_id(edge.left_id, edge.right_id)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT OR IGNORE INTO reviews(review_id,left_id,right_id,matcher_recommendation,matcher_reasons,matcher_evidence,status,created_at,graph_version_at_creation,version) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(review_id),
                        str(edge.left_id),
                        str(edge.right_id),
                        MatchState.REVIEW_REQUIRED.value,
                        json.dumps(list(edge.reasons)),
                        edge.matcher_evidence.model_dump_json() if edge.matcher_evidence else None,
                        ReviewStatus.PENDING.value,
                        created_at.isoformat(),
                        graph_version,
                        1,
                    ),
                )
                row = connection.execute("SELECT * FROM reviews WHERE review_id=?", (str(review_id),)).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        if row is None:
            raise RuntimeError("review insert returned no row")
        return self._review_from_row(row)

    def get_review(self, review_id: UUID) -> ReviewRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM reviews WHERE review_id=?", (str(review_id),)).fetchone()
        return None if row is None else self._review_from_row(row)

    def list_reviews(self, status: ReviewStatus | None = None) -> list[ReviewRecord]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute("SELECT * FROM reviews ORDER BY created_at, review_id").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM reviews WHERE status=? ORDER BY created_at, review_id",
                    (status.value,),
                ).fetchall()
        return [self._review_from_row(row) for row in rows]

    def apply_review_resolution(
        self,
        review_id: UUID,
        final_state: MatchState,
        reviewer_id: str,
        note: str | None,
        resolved_at: datetime,
        incidents: Iterable[Incident],
    ) -> ReviewRecord:
        if final_state not in (MatchState.AUTO_MATCH, MatchState.NO_MATCH):
            raise ValueError("review resolution must be auto_match or no_match")
        incident_list = list(incidents)
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT * FROM reviews WHERE review_id=?", (str(review_id),)).fetchone()
                if row is None:
                    raise ValueError("unknown review")
                current = self._review_from_row(row)
                if current.status is not ReviewStatus.PENDING:
                    raise ValueError("review is not pending")
                status = ReviewStatus.APPROVED if final_state is MatchState.AUTO_MATCH else ReviewStatus.REJECTED
                connection.execute(
                    "UPDATE reviews SET status=?,resolved_at=?,reviewed_by=?,review_note=?,final_relationship_state=?,decision_source=?,version=version+1 WHERE review_id=? AND status='pending'",
                    (
                        status.value,
                        resolved_at.isoformat(),
                        reviewer_id,
                        note,
                        final_state.value,
                        RelationshipDecisionSource.OFFICER_REVIEW.value,
                        str(review_id),
                    ),
                )
                self._replace_incidents_in_connection(connection, incident_list)
                updated = connection.execute("SELECT * FROM reviews WHERE review_id=?", (str(review_id),)).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        if updated is None:
            raise RuntimeError("review resolution returned no row")
        return self._review_from_row(updated)

    def replace_dataset(
        self,
        complaints: Iterable[Complaint],
        embeddings: Mapping[UUID, Iterable[float]],
        incidents: Iterable[Incident],
        reviews: Iterable[ReviewRecord],
        idempotency_prefix: str,
        model_version: str = "seed",
        normalization_version: str = "normalization-v1",
    ) -> None:
        """Atomically replace seed-derived complaints, edges, reviews, and snapshots."""
        complaint_list = list(complaints)
        incident_list = list(incidents)
        review_list = list(reviews)
        ids = {complaint.id for complaint in complaint_list}
        if len(ids) != len(complaint_list) or set(embeddings) != ids:
            raise ValueError("seed complaints and embeddings must have identical unique IDs")
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                for table in ("reviews", "submission_keys", "incident_members", "match_edges", "incidents", "embeddings", "complaints"):
                    connection.execute(f"DELETE FROM {table}")
                for complaint in sorted(complaint_list, key=lambda item: str(item.id)):
                    connection.execute(
                        "INSERT INTO complaints(id,text,normalized_text,latitude,longitude,reported_at,category,photo_path) VALUES(?,?,?,?,?,?,?,?)",
                        (str(complaint.id), complaint.text, complaint.normalized_text, complaint.latitude, complaint.longitude, complaint.reported_at.isoformat(), (complaint.category or Category.OTHER).value, complaint.photo_path),
                    )
                    connection.execute(
                        "INSERT INTO submission_keys(idempotency_key,complaint_id) VALUES(?,?)",
                        (f"{idempotency_prefix}:{complaint.id}", str(complaint.id)),
                    )
                    values = tuple(float(value) for value in embeddings[complaint.id])
                    if not values or not all(isfinite(value) for value in values):
                        raise ValueError("seed embedding vector must contain finite values")
                    connection.execute(
                        "INSERT INTO embeddings(complaint_id,vector,dimension,dtype,model_version,normalization_version) VALUES(?,?,?,?,?,?)",
                        (str(complaint.id), struct.pack(f"<{len(values)}f", *values), len(values), "float32", model_version, normalization_version),
                    )
                if self.failure_hook is not None:
                    self.failure_hook("after_seed_complaints")
                self._replace_incidents_in_connection(connection, incident_list)
                for review in review_list:
                    connection.execute(
                        "INSERT INTO reviews(review_id,left_id,right_id,matcher_recommendation,matcher_reasons,matcher_evidence,status,created_at,resolved_at,reviewed_by,review_note,final_relationship_state,decision_source,graph_version_at_creation,version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(review.review_id), str(review.left_id), str(review.right_id), review.matcher_recommendation.value, json.dumps(list(review.matcher_reasons)), review.matcher_evidence.model_dump_json() if review.matcher_evidence else None, review.status.value, review.created_at.isoformat(), review.resolved_at.isoformat() if review.resolved_at else None, review.reviewed_by, review.review_note, review.final_relationship_state.value if review.final_relationship_state else None, review.decision_source.value if review.decision_source else None, review.graph_version_at_creation, review.version),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _replace_incidents_in_connection(self, connection: sqlite3.Connection, incident_list: list[Incident]) -> None:
        existing_ids = {row["id"] for row in connection.execute("SELECT id FROM complaints").fetchall()}
        member_ids = [str(complaint_id) for incident in incident_list for complaint_id in incident.complaint_ids]
        if any(complaint_id not in existing_ids for complaint_id in member_ids):
            raise ValueError("unknown complaint referenced by incident")
        if len(member_ids) != len(set(member_ids)) or set(member_ids) != existing_ids:
            raise ValueError("incident replacement must cover each stored complaint exactly once")
        connection.execute("DELETE FROM incident_members")
        connection.execute("DELETE FROM match_edges")
        connection.execute("DELETE FROM incidents")
        for incident in incident_list:
            connection.execute(
                "INSERT INTO incidents(incident_id,report_count,centroid_latitude,centroid_longitude,radius_metres,earliest_reported_at,latest_reported_at,category_summary,status,conflict_reasons,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(incident.incident_id), incident.report_count, incident.centroid_latitude,
                    incident.centroid_longitude, incident.radius_metres,
                    incident.earliest_reported_at.isoformat(), incident.latest_reported_at.isoformat(),
                    json.dumps([category.value for category in incident.category_summary]), incident.status.value,
                    json.dumps(list(incident.conflict_reasons)), incident.model_dump_json(),
                ),
            )
            for complaint_id in incident.complaint_ids:
                connection.execute("INSERT INTO incident_members(incident_id,complaint_id) VALUES(?,?)", (str(incident.incident_id), str(complaint_id)))
            for edge in (*incident.confirmed_edges, *incident.review_candidates):
                edge_kind = "confirmed" if edge.decision is MatchState.AUTO_MATCH else "review"
                connection.execute(
                    "INSERT OR IGNORE INTO match_edges(left_id,right_id,edge_kind,matcher_recommendation,decision_source,reasons) VALUES(?,?,?,?,?,?)",
                    (str(edge.left_id), str(edge.right_id), edge_kind, edge.matcher_recommendation.value if edge.matcher_recommendation else None, edge.decision_source.value, json.dumps(list(edge.reasons))),
                )

    def list_incidents(self) -> list[Incident]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload FROM incidents ORDER BY incident_id").fetchall()
        return [Incident.model_validate_json(row["payload"]) for row in rows]

    def get_incident(self, incident_id: UUID) -> Incident | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM incidents WHERE incident_id=?", (str(incident_id),)
            ).fetchone()
        return None if row is None else Incident.model_validate_json(row["payload"])
