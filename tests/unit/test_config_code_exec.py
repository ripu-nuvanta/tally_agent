"""Tests for CODE_EXECUTION_ENABLED config setting."""

import os
from unittest.mock import patch


class TestCodeExecutionConfig:
    def test_default_is_true(self):
        """CODE_EXECUTION_ENABLED defaults to True."""
        from backend.config import Settings
        s = Settings(ANTHROPIC_API_KEY="test")
        assert s.CODE_EXECUTION_ENABLED is True

    def test_can_disable_via_env(self):
        """CODE_EXECUTION_ENABLED can be set to False via env var."""
        with patch.dict(os.environ, {"CODE_EXECUTION_ENABLED": "false"}):
            from backend.config import Settings
            s = Settings(ANTHROPIC_API_KEY="test")
            assert s.CODE_EXECUTION_ENABLED is False
