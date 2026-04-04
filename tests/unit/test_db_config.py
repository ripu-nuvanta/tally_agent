"""Tests for database-related config settings."""
from backend.config import Settings


def _settings_no_env(**overrides):
    """Create Settings without reading .env file."""
    defaults = {"ANTHROPIC_API_KEY": "test", "_env_file": None}
    defaults.update(overrides)
    return Settings(**defaults)


def test_database_url_defaults_to_none():
    s = _settings_no_env()
    assert s.DATABASE_URL is None


def test_jwt_secret_defaults_to_none():
    s = _settings_no_env()
    assert s.JWT_SECRET is None


def test_jwt_expiry_defaults():
    s = _settings_no_env()
    assert s.JWT_ACCESS_TOKEN_EXPIRY_MINUTES == 30
    assert s.JWT_REFRESH_TOKEN_EXPIRY_DAYS == 7


def test_db_mode_enabled_when_database_url_set():
    s = _settings_no_env(DATABASE_URL="postgresql+asyncpg://user:pass@localhost/testdb")
    assert s.db_mode is True


def test_db_mode_disabled_when_database_url_not_set():
    s = _settings_no_env()
    assert s.db_mode is False
