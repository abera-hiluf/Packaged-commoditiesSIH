"""SQLite persistence behind small functions for later database replacement."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Repository:
    def __init__(self, path: str | Path = "data/app.db"):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self):
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS inspections (inspection_id TEXT PRIMARY KEY, product_id TEXT, product_name TEXT, manufacturer TEXT, category TEXT, inspection_date TEXT, overall_status TEXT, rule_version TEXT, payload TEXT NOT NULL)")

    def save_inspection(self, inspection: dict[str, Any]) -> str:
        inspection = dict(inspection)
        inspection.setdefault("inspection_date", datetime.now(timezone.utc).isoformat())
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (inspection["inspection_id"], inspection.get("product_id"), inspection.get("product_name"), inspection.get("manufacturer"), inspection.get("category"), inspection["inspection_date"], inspection.get("overall_status"), inspection.get("rule_version"), json.dumps(inspection)))
        return inspection["inspection_id"]

    def list_inspections(self, search: str = "") -> list[dict[str, Any]]:
        query = "SELECT payload FROM inspections"
        params: tuple[str, ...] = ()
        if search:
            query += " WHERE product_name LIKE ? OR manufacturer LIKE ? OR product_id LIKE ? OR overall_status LIKE ?"
            like = f"%{search}%"
            params = (like, like, like, like)
        query += " ORDER BY inspection_date DESC"
        with self._connect() as db:
            return [json.loads(row["payload"]) for row in db.execute(query, params)]

    def get_inspection(self, inspection_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM inspections WHERE inspection_id = ?", (inspection_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

