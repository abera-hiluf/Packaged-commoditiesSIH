"""Explicitly seed synthetic products and inspection headers into SQLite."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.repository import Repository


def main() -> None:
    products = json.loads((ROOT / "data" / "sample_products.json").read_text(encoding="utf-8"))["products"]
    inspections = json.loads((ROOT / "data" / "inspections.json").read_text(encoding="utf-8"))["inspections"]
    repository = Repository(ROOT / "data" / "compliance.db")
    for product in products:
        if not repository.get_product(product["product_id"]):
            repository.create_product(product)
    for inspection in inspections:
        if not repository.get_inspection(inspection["inspection_id"]):
            repository.create_inspection({**inspection, "overall_status": inspection.get("status")})
    print(f"Seeded {len(products)} synthetic products and {len(inspections)} synthetic inspections.")


if __name__ == "__main__":
    main()
