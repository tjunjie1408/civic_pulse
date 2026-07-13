import sqlite3

import pytest

from civicpulse.repository import SQLiteRepository


def test_schema_initializes_idempotently_with_foreign_keys(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    repository.initialize()

    with repository.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"complaints", "embeddings", "incidents", "incident_members", "match_edges", "photo_assessments", "submission_keys"} <= tables


def test_sqlite_constraints_reject_invalid_rows_and_orphans(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()

    with repository.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO complaints(id,text,normalized_text,latitude,longitude,reported_at,category) VALUES(?,?,?,?,?,?,?)",
                ("bad", "x", "x", 3.0, 101.0, "2026-07-12T08:00:00+00:00", "pothole"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO incident_members(incident_id,complaint_id) VALUES(?,?)",
                ("missing", "missing"),
            )
