"""Evidence and provenance records for auditable compliance findings.

Evidence records what earlier pipeline stages observed. This module does not
invent evidence and does not generate legal explanations.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from itertools import count
from typing import Any, Iterable


_evidence_sequence = count(1)
_finding_sequence = count(1)


def _next_evidence_id() -> str:
    return f"EV-{next(_evidence_sequence):03d}"


def _next_finding_id() -> str:
    return f"FIND-{next(_finding_sequence):03d}"


def _bbox(value: Any) -> dict[str, int] | list[Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return {key: int(value[key]) for key in ("x", "y", "width", "height") if key in value}
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [int(item) for item in value]
    return None


def create_field_evidence(extracted_field: dict[str, Any] | None, normalized_field: dict[str, Any] | None, image_path: str | None = None) -> dict[str, Any]:
    """Combine extractor and normalizer provenance without fabricating values."""
    extracted_field = extracted_field or {}
    normalized_field = normalized_field or {}
    return {
        "evidence_id": _next_evidence_id(),
        "image_id": extracted_field.get("image_id", normalized_field.get("image_id")),
        "image_path": image_path,
        "source_text": extracted_field.get("source_text", normalized_field.get("source_text")),
        "bbox": _bbox(extracted_field.get("bbox", normalized_field.get("bbox"))),
        "ocr_confidence": extracted_field.get("ocr_confidence", normalized_field.get("ocr_confidence")),
        "extraction_confidence": extracted_field.get("extraction_confidence", normalized_field.get("extraction_confidence")),
        "field": extracted_field.get("field", normalized_field.get("field")),
        "original_value": extracted_field.get("original_value", normalized_field.get("original_value", extracted_field.get("value"))),
        "normalized_value": normalized_field.get("normalized_value"),
        "extraction_method": extracted_field.get("method"),
        "pipeline_stage": "field_normalization",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "PENDING",
    }


def attach_evidence_to_finding(finding: dict[str, Any], evidence: dict[str, Any] | Iterable[dict[str, Any]] | None) -> dict[str, Any]:
    """Return a finding linked to evidence IDs; missing evidence remains explicit."""
    result = deepcopy(finding)
    result.setdefault("finding_id", _next_finding_id())
    records = [] if evidence is None else [evidence] if isinstance(evidence, dict) else list(evidence)
    result["evidence_ids"] = [record.get("evidence_id") for record in records if record.get("evidence_id")]
    if not result["evidence_ids"]:
        result["evidence_status"] = "NO_SUPPORTING_TEXT_DETECTED"
    else:
        result["evidence_status"] = "SUPPORTING_EVIDENCE_ATTACHED"
    return result


def apply_reviewer_correction(evidence: dict[str, Any], reviewer_value: Any, reviewer: str, reason: str) -> dict[str, Any]:
    """Add correction metadata without changing the original observed value."""
    corrected = deepcopy(evidence)
    corrected["reviewer_value"] = reviewer_value
    corrected["reviewer"] = reviewer
    corrected["review_reason"] = reason
    corrected["review_status"] = "CORRECTED"
    corrected["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    return corrected


class EvidenceStore:
    """Small in-memory evidence collection for use before persistence is added."""

    def __init__(self):
        self._evidence: dict[str, dict[str, Any]] = {}
        self._findings: dict[str, dict[str, Any]] = {}

    def add_evidence(self, evidence: dict[str, Any]) -> str:
        record = deepcopy(evidence)
        evidence_id = record.get("evidence_id") or _next_evidence_id()
        if evidence_id in self._evidence:
            raise ValueError(f"Duplicate evidence ID: {evidence_id}")
        record["evidence_id"] = evidence_id
        self._evidence[evidence_id] = record
        return evidence_id

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        return deepcopy(self._evidence.get(evidence_id))

    def list_evidence(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._evidence.values()]

    def attach_finding(self, finding: dict[str, Any], evidence_ids: Iterable[str] | None = None) -> dict[str, Any]:
        result = deepcopy(finding)
        result.setdefault("finding_id", _next_finding_id())
        ids = list(evidence_ids or result.get("evidence_ids", []))
        missing = [evidence_id for evidence_id in ids if evidence_id not in self._evidence]
        if missing:
            raise ValueError(f"Unknown evidence ID(s): {', '.join(missing)}")
        result["evidence_ids"] = ids
        result["evidence_status"] = "SUPPORTING_EVIDENCE_ATTACHED" if ids else "NO_SUPPORTING_TEXT_DETECTED"
        self._findings[result["finding_id"]] = result
        return deepcopy(result)

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        return deepcopy(self._findings.get(finding_id))

    def get_evidence_for_finding(self, finding_id: str) -> list[dict[str, Any]]:
        finding = self._findings.get(finding_id, {})
        return [deepcopy(self._evidence[evidence_id]) for evidence_id in finding.get("evidence_ids", []) if evidence_id in self._evidence]

    def validate_references(self) -> list[str]:
        errors = []
        for finding in self._findings.values():
            for evidence_id in finding.get("evidence_ids", []):
                if evidence_id not in self._evidence:
                    errors.append(f"Finding {finding.get('finding_id')} references missing evidence {evidence_id}")
        errors.extend(validate_evidence(self.list_evidence()))
        return errors


def validate_evidence(records: Iterable[dict[str, Any]]) -> list[str]:
    """Return validation errors while allowing legitimate missing-field evidence."""
    errors: list[str] = []
    seen: set[str] = set()
    for record in records:
        evidence_id = record.get("evidence_id")
        if not evidence_id:
            errors.append("Evidence record is missing evidence_id")
        elif evidence_id in seen:
            errors.append(f"Duplicate evidence ID: {evidence_id}")
        else:
            seen.add(evidence_id)
        bbox = record.get("bbox")
        if bbox is not None:
            values = list(bbox.values()) if isinstance(bbox, dict) else list(bbox) if isinstance(bbox, (list, tuple)) else []
            if len(values) != 4 or not all(isinstance(value, (int, float)) for value in values):
                errors.append(f"Malformed bounding box for {evidence_id or '<unknown>'}")
        if record.get("field") and record.get("original_value") is not None and not record.get("source_text"):
            errors.append(f"Missing source_text for evidence {evidence_id or '<unknown>'}")
        if record.get("image_path") is not None and not isinstance(record.get("image_path"), str):
            errors.append(f"Invalid image reference for {evidence_id or '<unknown>'}")
    return errors

