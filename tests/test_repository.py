from src.repository import Repository


def test_repository_round_trip(tmp_path):
    repository = Repository(tmp_path / "app.db")
    item = {"inspection_id": "I-1", "product_id": "P-1", "product_name": "Demo", "findings": []}
    repository.save_inspection(item)
    assert repository.get_inspection("I-1")["product_name"] == "Demo"

