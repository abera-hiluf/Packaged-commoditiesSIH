"""CSV and PDF report generation."""

import csv
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors


def write_csv(inspection: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "status", "value", "severity", "reason", "rule_id"])
        writer.writeheader()
        writer.writerows({key: finding.get(key) for key in writer.fieldnames} for finding in inspection.get("findings", []))
    return target


def write_pdf(inspection: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(target), pagesize=A4)
    story = [Paragraph("AI-Assisted Compliance Review", styles["Title"]), Paragraph("Prototype decision-support report — not legal advice or certification.", styles["Normal"]), Spacer(1, 12)]
    story.append(Paragraph(f"Product: {inspection.get('product_name', 'Unnamed')} | Inspection: {inspection.get('inspection_id', '')}", styles["Normal"]))
    story.append(Paragraph(f"Overall review status: {inspection.get('overall_status', 'NEEDS REVIEW')} | Review score: {inspection.get('review_score', '—')}/100", styles["Normal"]))
    story.append(Spacer(1, 12))
    rows = [["Field", "Status", "Value", "Severity", "Rule"]] + [[f.get("field"), f.get("status"), f.get("value") or "Not detected", f.get("severity"), f.get("rule_id")] for f in inspection.get("findings", [])]
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19324d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Final determination requires qualified human review. Prototype configuration must be verified against current official Legal Metrology notifications.", styles["Normal"]))
    doc.build(story)
    return target

