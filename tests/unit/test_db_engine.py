"""Tests for database engine initialization."""
import pytest


def test_init_engine_raises_without_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("backend.config.settings.DATABASE_URL", None)
    from backend.db.engine import init_engine
    with pytest.raises(ValueError, match="DATABASE_URL must be set"):
        init_engine(database_url=None)

def test_engine_module_has_expected_functions():
    from backend.db import engine as eng_module
    assert callable(eng_module.init_engine)
    assert callable(eng_module.close_engine)
    assert callable(eng_module.get_db)
