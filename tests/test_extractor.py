from src.extractor import extract_fields


def test_extracts_quantity_and_mrp():
    fields = extract_fields("Net Quantity: 500 g\nMRP ₹120")
    assert fields["net_quantity"]["normalized_value"] == "500 g"
    assert fields["mrp"]["normalized_value"] == "Rs 120"

