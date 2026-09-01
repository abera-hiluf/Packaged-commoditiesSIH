"""Run the backend pipeline against the first synthetic demo product."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.repository import Repository
from src.rule_engine import load_rules
from src.service import process_inspection


def main() -> None:
    products = json.loads((ROOT / "data" / "sample_products.json").read_text(encoding="utf-8"))["products"]
    product = products[0]
    rules = load_rules(ROOT / "data" / "rules" / "legal_rules.json")["rules"]
    result = process_inspection(product, [ROOT / path for path in product["image_paths"]], rules, repository=Repository(ROOT / "data" / "compliance.db"))
    print("Inspection:", result["inspection_id"])
    print("Processing status:", result["status"])
    print("Overall status:", result["overall_status"])
    print("Summary:", result["summary"])
    print("Findings:", [(f.get("declaration"), f.get("status"), f.get("evidence_ids", [])) for f in result["findings"]])
    print("Evidence:", [(e.get("evidence_id"), e.get("image_id"), e.get("source_text")) for e in result["evidence"]])
    if result["errors"]:
        print("Errors:", result["errors"])


if __name__ == "__main__":
    main()

