"""Unit tests for configuration defaults."""

import os
from unittest.mock import patch


class TestConfigDefaults:
    def test_default_tally_host_is_localhost(self):
        """TALLY_HOST default must be 'localhost', not a hardcoded IP."""
        # Clear any env overrides and disable .env file loading
        env_overrides = {
            k: v for k, v in os.environ.items()
            if not k.startswith("TALLY_")
        }
        with patch.dict(os.environ, env_overrides, clear=True):
            from backend.config import Settings

            class TestSettings(Settings):
                model_config = {"env_file": None, "extra": "ignore"}

            s = TestSettings()
            assert s.TALLY_HOST == "localhost"

    def test_default_tally_port(self):
        with patch.dict(os.environ, {}, clear=True):
            from backend.config import Settings

            class TestSettings(Settings):
                model_config = {"env_file": None, "extra": "ignore"}

            s = TestSettings()
            assert s.TALLY_PORT == 9000

    def test_tally_url_property(self):
        from backend.config import Settings
        s = Settings(TALLY_HOST="192.168.1.100", TALLY_PORT=9001)
        assert s.TALLY_URL == "http://192.168.1.100:9001"

    def test_fx_default_rates_default_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            from backend.config import Settings

            class TestSettings(Settings):
                model_config = {"env_file": None, "extra": "ignore"}

            s = TestSettings()
            assert s.FX_DEFAULT_RATES == ""
            assert s.FX_DEFAULT_RATE == 0.0

    def test_default_stock_group_default_primary(self):
        """DEFAULT_STOCK_GROUP defaults to 'Primary' (inventory Phase 2)."""
        with patch.dict(os.environ, {}, clear=True):
            from backend.config import Settings

            class TestSettings(Settings):
                model_config = {"env_file": None, "extra": "ignore"}

            s = TestSettings()
            assert s.DEFAULT_STOCK_GROUP == "Primary"
