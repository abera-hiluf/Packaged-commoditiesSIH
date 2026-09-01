from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_app_is_presentation_boundary():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "process_inspection" in source
    assert "SELECT " not in source
    assert "INSERT " not in source
    assert "image_to_data" not in source
    assert "re.search" not in source


def test_app_and_result_component_exist():
    assert (ROOT / "app.py").exists()
    assert (ROOT / "components" / "results.py").exists()
