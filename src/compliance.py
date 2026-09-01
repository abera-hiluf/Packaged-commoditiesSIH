"""Compliance status aggregation and review-score prioritization."""

STATUSES = ("COMPLIANT", "WARNING", "NON-COMPLIANT", "NEEDS REVIEW")


def overall_status(findings: list[dict]) -> str:
    statuses = {f.get("status") for f in findings}
    if "NON-COMPLIANT" in statuses:
        return "NON-COMPLIANT"
    if "NEEDS REVIEW" in statuses:
        return "NEEDS REVIEW"
    if "WARNING" in statuses:
        return "WARNING"
    return "COMPLIANT"


def review_score(findings: list[dict]) -> int:
    """Application prioritization indicator, not a legal compliance percentage."""
    deductions = {"NON-COMPLIANT": 30, "NEEDS REVIEW": 15, "WARNING": 8}
    return max(0, min(100, 100 - sum(deductions.get(f.get("status"), 0) for f in findings)))

