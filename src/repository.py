"""Repository API that isolates application code from SQLite queries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import Database, init_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _loads(value: str | None) -> Any:
    return None if value is None else json.loads(value)


class Repository:
    """Persistence facade; callers provide dictionaries, never SQL."""

    def __init__(self, path: str | Path = "data/compliance.db", database: Database | None = None):
        self.database = database or init_db(path)

    @staticmethod
    def _row(row):
        return dict(row) if row else None

    def create_product(self, product: dict[str, Any]) -> str:
        with self.database.transaction() as db:
            db.execute("INSERT INTO products (product_id, product_name, category, manufacturer, created_at) VALUES (?, ?, ?, ?, ?)", (product["product_id"], product.get("product_name"), product.get("category"), product.get("manufacturer"), product.get("created_at", _now())))
        return product["product_id"]

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        with self.database.connect() as db:
            return self._row(db.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone())

    def list_products(self) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM products ORDER BY created_at DESC")]

    get_products = list_products

    def create_inspection(self, inspection: dict[str, Any]) -> str:
        with self.database.transaction() as db:
            db.execute("INSERT INTO inspections (inspection_id, product_id, inspection_date, overall_status, created_at) VALUES (?, ?, ?, ?, ?)", (inspection["inspection_id"], inspection["product_id"], inspection.get("inspection_date", _now()), inspection.get("overall_status"), inspection.get("created_at", _now())))
        return inspection["inspection_id"]

    def get_inspection(self, inspection_id: str) -> dict[str, Any] | None:
        with self.database.connect() as db:
            row = self._row(db.execute("SELECT * FROM inspections WHERE inspection_id = ?", (inspection_id,)).fetchone())
        if row:
            row["product"] = self.get_product(row["product_id"])
        return row

    def list_inspections(self, search: str = "") -> list[dict[str, Any]]:
        query = "SELECT i.*, p.product_name, p.manufacturer, p.category FROM inspections i JOIN products p ON p.product_id = i.product_id"
        params: tuple[str, ...] = ()
        if search:
            query += " WHERE i.inspection_id LIKE ? OR i.product_id LIKE ? OR p.product_name LIKE ? OR p.manufacturer LIKE ? OR i.overall_status LIKE ?"
            like = f"%{search}%"
            params = (like, like, like, like, like)
        query += " ORDER BY i.inspection_date DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(query, params)]

    def save_inspection(self, inspection: dict[str, Any]) -> str:
        """Compatibility entry point that persists the inspection header."""
        if not self.get_product(inspection["product_id"]):
            self.create_product({"product_id": inspection["product_id"], "product_name": inspection.get("product_name"), "category": inspection.get("category"), "manufacturer": inspection.get("manufacturer")})
        if not self.get_inspection(inspection["inspection_id"]):
            self.create_inspection(inspection)
        return inspection["inspection_id"]

    def save_image(self, image: dict[str, Any]) -> str:
        with self.database.transaction() as db:
            db.execute("INSERT INTO images (image_id, inspection_id, image_path, image_type, created_at) VALUES (?, ?, ?, ?, ?)", (image["image_id"], image["inspection_id"], image.get("image_path"), image.get("image_type"), image.get("created_at", _now())))
        return image["image_id"]

    def save_ocr_result(self, result: dict[str, Any]) -> int:
        with self.database.transaction() as db:
            cursor = db.execute("INSERT INTO ocr_results (image_id, text, confidence, engine, words_json, lines_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (result["image_id"], result.get("text", ""), result.get("confidence"), result.get("engine"), _json(result.get("words")), _json(result.get("lines")), result.get("created_at", _now())))
            return cursor.lastrowid

    def save_extracted_field(self, inspection_id: str, field: dict[str, Any]) -> int:
        with self.database.transaction() as db:
            cursor = db.execute("INSERT INTO extracted_fields (inspection_id, field_name, original_value, status, extraction_confidence, image_id, source_text, bbox_json, extraction_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (inspection_id, field.get("field"), field.get("original_value", field.get("value")), field.get("status"), field.get("extraction_confidence"), field.get("image_id"), field.get("source_text"), _json(field.get("bbox")), field.get("method"), _now()))
            return cursor.lastrowid

    def save_normalized_field(self, inspection_id: str, field: dict[str, Any]) -> int:
        with self.database.transaction() as db:
            cursor = db.execute("INSERT INTO normalized_fields (inspection_id, field_name, normalized_value_json, normalization_status, normalization_method, created_at) VALUES (?, ?, ?, ?, ?, ?)", (inspection_id, field.get("field"), _json(field.get("normalized_value")), field.get("normalization_status"), field.get("normalization_method"), _now()))
            return cursor.lastrowid

    def save_applicability_result(self, inspection_id: str, result: dict[str, Any]) -> int:
        with self.database.transaction() as db:
            cursor = db.execute("INSERT INTO applicability_results (inspection_id, rule_id, status, reason, created_at) VALUES (?, ?, ?, ?, ?)", (inspection_id, result.get("rule_id"), result.get("status"), result.get("reason"), _now()))
            return cursor.lastrowid

    def save_compliance_finding(self, inspection_id: str, finding: dict[str, Any]) -> str:
        with self.database.transaction() as db:
            db.execute("INSERT INTO compliance_findings (finding_id, inspection_id, rule_id, declaration, status, severity, message, reason, field_value_json, evidence_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (finding["finding_id"], inspection_id, finding.get("rule_id"), finding.get("declaration"), finding.get("status"), finding.get("severity"), finding.get("message"), finding.get("reason"), _json(finding.get("field_value")), _json(finding.get("evidence_ids", [])), finding.get("created_at", _now())))
        return finding["finding_id"]

    def save_evidence(self, evidence: dict[str, Any], finding_id: str | None = None) -> str:
        with self.database.transaction() as db:
            db.execute("INSERT INTO evidence (evidence_id, finding_id, image_id, image_path, source_text, bbox_json, ocr_confidence, extraction_confidence, field_name, original_value, normalized_value_json, extraction_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (evidence["evidence_id"], finding_id or evidence.get("finding_id"), evidence.get("image_id"), evidence.get("image_path"), evidence.get("source_text"), _json(evidence.get("bbox")), evidence.get("ocr_confidence"), evidence.get("extraction_confidence"), evidence.get("field"), evidence.get("original_value"), _json(evidence.get("normalized_value")), evidence.get("extraction_method"), evidence.get("created_at", _now())))
        return evidence["evidence_id"]

    def add_review(self, finding_id: str, review: dict[str, Any]) -> int:
        with self.database.transaction() as db:
            cursor = db.execute("INSERT INTO reviews (finding_id, review_status, reviewer_name, reviewer_value, reviewer_comment, reviewed_at) VALUES (?, ?, ?, ?, ?, ?)", (finding_id, review["review_status"], review.get("reviewer_name"), review.get("reviewer_value"), review.get("reviewer_comment"), review.get("reviewed_at", _now())))
            return cursor.lastrowid

    def update_review_status(self, finding_id: str, review_status: str, reviewer_name: str, reviewer_value: Any = None, reviewer_comment: str | None = None) -> int:
        return self.add_review(finding_id, {"review_status": review_status, "reviewer_name": reviewer_name, "reviewer_value": reviewer_value, "reviewer_comment": reviewer_comment})

    def get_findings_for_inspection(self, inspection_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM compliance_findings WHERE inspection_id = ? ORDER BY id", (inspection_id,))]
        for row in rows:
            row["field_value"] = _loads(row.pop("field_value_json"))
            row["evidence_ids"] = _loads(row.pop("evidence_ids_json")) or []
        return rows

    def get_evidence_for_finding(self, finding_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM evidence WHERE finding_id = ? ORDER BY id", (finding_id,))]
        for row in rows:
            row["bbox"] = _loads(row.pop("bbox_json"))
            row["normalized_value"] = _loads(row.pop("normalized_value_json"))
        return rows

    def get_inspection_summary(self, inspection_id: str) -> dict[str, Any]:
        findings = self.get_findings_for_inspection(inspection_id)
        return {"inspection_id": inspection_id, "total_findings": len(findings), "by_status": {status: sum(f["status"] == status for f in findings) for status in {f["status"] for f in findings}}, "findings": findings}

    def list_recent_inspections(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM inspections ORDER BY inspection_date DESC LIMIT ?", (max(0, int(limit)),))]

    def get_findings_by_status(self, status: str) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM compliance_findings WHERE status = ? ORDER BY created_at DESC", (status,))]

    def metrics(self) -> dict[str, Any]:
        with self.database.connect() as db:
            return {"total_products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0], "total_inspections": db.execute("SELECT COUNT(*) FROM inspections").fetchone()[0], "total_findings": db.execute("SELECT COUNT(*) FROM compliance_findings").fetchone()[0], "findings_by_status": {row["status"]: row["count"] for row in db.execute("SELECT status, COUNT(*) AS count FROM compliance_findings GROUP BY status")}}
