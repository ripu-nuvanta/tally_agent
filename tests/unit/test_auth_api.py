"""Tests for auth API — password validation and rate limiting logic."""
import time
import pytest
from backend.utils.auth import validate_password


class TestPasswordValidation:
    def test_register_rejects_weak_password(self):
        errors = validate_password("weak")
        assert len(errors) >= 3

    def test_register_accepts_strong_password(self):
        errors = validate_password("Str0ng!Pass#99")
        assert errors == []


class TestRateLimit:
    def test_rate_limit_blocks_after_max_attempts(self):
        from backend.api.auth import _check_rate_limit, _login_attempts, _RATE_LIMIT_MAX
        email = "ratelimit-test@example.com"
        _login_attempts[email] = [time.time() for _ in range(_RATE_LIMIT_MAX)]
        with pytest.raises(Exception) as exc_info:
            _check_rate_limit(email)
        assert "429" in str(exc_info.value.status_code)
        del _login_attempts[email]

    def test_rate_limit_allows_under_threshold(self):
        from backend.api.auth import _check_rate_limit, _login_attempts
        email = "ratelimit-ok@example.com"
        _login_attempts[email] = [time.time(), time.time()]
        _check_rate_limit(email)  # Should not raise
        del _login_attempts[email]
