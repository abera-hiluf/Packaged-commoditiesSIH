"""SQLite connection and schema management for the repository layer."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL UNIQUE,
    product_name TEXT, category TEXT, manufacturer TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inspection_id TEXT NOT NULL UNIQUE,
    product_id TEXT NOT NULL REFERENCES products(product_id), inspection_date TEXT,
    overall_status TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT NOT NULL UNIQUE,
    inspection_id TEXT NOT NULL REFERENCES inspections(inspection_id), image_path TEXT,
    image_type TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ocr_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT NOT NULL REFERENCES images(image_id),
    text TEXT, confidence REAL, engine TEXT, words_json TEXT, lines_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS extracted_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inspection_id TEXT NOT NULL REFERENCES inspections(inspection_id),
    field_name TEXT NOT NULL, original_value TEXT, status TEXT, extraction_confidence REAL,
    image_id TEXT, source_text TEXT, bbox_json TEXT, extraction_method TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS normalized_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inspection_id TEXT NOT NULL REFERENCES inspections(inspection_id),
    field_name TEXT NOT NULL, normalized_value_json TEXT, normalization_status TEXT,
    normalization_method TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS applicability_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inspection_id TEXT NOT NULL REFERENCES inspections(inspection_id),
    rule_id TEXT NOT NULL, status TEXT, reason TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS compliance_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id TEXT NOT NULL UNIQUE,
    inspection_id TEXT NOT NULL REFERENCES inspections(inspection_id), rule_id TEXT,
    declaration TEXT, status TEXT, severity TEXT, message TEXT, reason TEXT,
    field_value_json TEXT, evidence_ids_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_id TEXT NOT NULL UNIQUE,
    finding_id TEXT REFERENCES compliance_findings(finding_id), image_id TEXT,
    image_path TEXT, source_text TEXT, bbox_json TEXT, ocr_confidence REAL,
    extraction_confidence REAL, field_name TEXT, original_value TEXT,
    normalized_value_json TEXT, extraction_method TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id TEXT NOT NULL REFERENCES compliance_findings(finding_id),
    review_status TEXT NOT NULL, reviewer_name TEXT, reviewer_value TEXT,
    reviewer_comment TEXT, reviewed_at TEXT
);
"""


class Database:
    """Small connection factory with foreign keys and transaction support."""

    def __init__(self, path: str | Path = "data/compliance.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def init_db(path: str | Path = "data/compliance.db") -> Database:
    """Initialize a database idempotently and return its wrapper."""
    database = Database(path)
    database.init_db()
    return database

