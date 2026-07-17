import sys

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Flask test client backed by an isolated, throwaway SQLite file.

    database/db.py's DB_PATH is a module-level constant and app.py calls
    init_db()/seed_db() at import time, so the app module must be patched
    and re-imported per test to avoid touching the real spendly.db.
    """
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test.db"))
    sys.modules.pop("app", None)
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as test_client:
        yield test_client
    sys.modules.pop("app", None)


@pytest.fixture
def db(monkeypatch, tmp_path):
    """Isolated database.db module for pure DB-helper tests (no Flask app)."""
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test_db_helpers.db"))
    from database import db as db_module
    db_module.init_db()
    return db_module
