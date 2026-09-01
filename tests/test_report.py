from src.report import write_csv, write_pdf


def test_reports_are_generated(tmp_path):
    inspection = {"inspection_id": "I-1", "product_name": "Demo", "overall_status": "NEEDS REVIEW", "findings": []}
    assert write_csv(inspection, tmp_path / "out.csv").exists()
    assert write_pdf(inspection, tmp_path / "out.pdf").exists()

