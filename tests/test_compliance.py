from src.compliance import overall_status, review_score


def test_status_priority():
    assert overall_status([{ "status": "COMPLIANT" }, { "status": "WARNING" }]) == "WARNING"
    assert overall_status([{ "status": "NEEDS REVIEW" }, { "status": "COMPLIANT" }]) == "NEEDS REVIEW"
    assert overall_status([{ "status": "NON-COMPLIANT" }]) == "NON-COMPLIANT"
    assert review_score([{ "status": "NON-COMPLIANT" }]) == 70

