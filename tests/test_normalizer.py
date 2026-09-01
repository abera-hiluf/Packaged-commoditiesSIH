from src.normalizer import normalize_currency, normalize_quantity


def test_normalizes_common_variants():
    assert normalize_currency("MRP Rs.120") == "Rs 120"
    assert normalize_quantity("1 kilograms") == "1 kg"

