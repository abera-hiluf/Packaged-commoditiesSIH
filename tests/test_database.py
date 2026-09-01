import sqlite3

from src.database import Database, init_db


def test_database_initialization_is_idempotent(tmp_path):
    path = tmp_path / "compliance.db"
    database = init_db(path)
    database.init_db()
    with database.connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"products", "inspections", "images", "ocr_results", "extracted_fields", "normalized_fields", "applicability_results", "compliance_findings", "evidence", "reviews"} <= tables


def test_foreign_keys_are_enabled(tmp_path):
    database = Database(tmp_path / "compliance.db")
    database.init_db()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_transaction_rolls_back(tmp_path):
    database = init_db(tmp_path / "compliance.db")
    try:
        with database.transaction() as connection:
            connection.execute("INSERT INTO products (product_id, created_at) VALUES (?, ?)", ("P-1", "now"))
            raise RuntimeError("rollback")
    except RuntimeError:
        pass
    assert database.connect().execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0

