"""Conservative normalization; original evidence remains untouched."""

import re
from datetime import datetime


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).replace("|", "I")).strip(" .:;-_")


def normalize_currency(value: str) -> str:
    text = clean_text(value).replace("₹", "Rs ")
    text = re.sub(r"(?i)\bMRP\s*", "", text)
    text = re.sub(r"(?i)\bRs\.?\s*", "Rs ", text)
    match = re.search(r"\d+(?:\.\d{1,2})?", text.replace(",", ""))
    return f"Rs {match.group(0)}" if match else text


def normalize_quantity(value: str) -> str:
    text = clean_text(value).replace(",", "")
    text = re.sub(r"(?i)\b(kgs?|kilograms?)\b", "kg", text)
    text = re.sub(r"(?i)\b(gms?|grams?)\b", "g", text)
    text = re.sub(r"(?i)\b(ltrs?|litres?|liters?)\b", "L", text)
    text = re.sub(r"(?i)\b(mls?|millilitres?|milliliters?)\b", "ml", text)
    return text


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) >= 10 else clean_text(value)


def normalize_date(value: str) -> str:
    text = clean_text(value)
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%Y", "%b %Y", "%B %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return text


def normalize_field(field: str, value: str) -> str:
    if field == "mrp":
        return normalize_currency(value)
    if field == "net_quantity":
        return normalize_quantity(value)
    if field == "consumer_care":
        return normalize_phone(value) if re.search(r"\d", value) else clean_text(value)
    if field.endswith("date") or field in {"best_before", "use_by"}:
        return normalize_date(value)
    return clean_text(value)

