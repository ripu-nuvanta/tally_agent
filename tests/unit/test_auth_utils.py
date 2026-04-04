"""Tests for auth utility functions — password hashing, validation, JWT."""
import pytest

def test_password_hash_roundtrip():
    from backend.utils.auth import hash_password, verify_password
    hashed = hash_password("Str0ng!Pass#99")
    assert verify_password("Str0ng!Pass#99", hashed) is True
    assert verify_password("wrong", hashed) is False

def test_password_hash_is_bcrypt():
    from backend.utils.auth import hash_password
    hashed = hash_password("Str0ng!Pass#99")
    assert hashed.startswith("$2b$")

class TestPasswordValidation:
    def test_valid_password(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ng!Pass#99")
        assert errors == []

    def test_too_short(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ng!1")
        assert any("12 characters" in e for e in errors)

    def test_no_uppercase(self):
        from backend.utils.auth import validate_password
        errors = validate_password("str0ng!pass#99")
        assert any("uppercase" in e for e in errors)

    def test_no_lowercase(self):
        from backend.utils.auth import validate_password
        errors = validate_password("STR0NG!PASS#99")
        assert any("lowercase" in e for e in errors)

    def test_no_digit(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Strong!Pass#abc")
        assert any("digit" in e for e in errors)

    def test_no_special(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ngPass9999")
        assert any("special" in e for e in errors)

    def test_multiple_failures(self):
        from backend.utils.auth import validate_password
        errors = validate_password("short")
        assert len(errors) >= 3

class TestJWT:
    def test_create_and_decode_access_token(self):
        from backend.utils.auth import create_access_token, decode_token
        token = create_access_token(user_id="abc-123", secret="x" * 32)
        payload = decode_token(token, secret="x" * 32)
        assert payload["sub"] == "abc-123"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        from backend.utils.auth import create_refresh_token, decode_token
        token = create_refresh_token(user_id="abc-123", secret="x" * 32)
        payload = decode_token(token, secret="x" * 32)
        assert payload["sub"] == "abc-123"
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self):
        from backend.utils.auth import create_access_token, decode_token
        token = create_access_token(user_id="abc-123", secret="x" * 32, expiry_minutes=-1)
        with pytest.raises(Exception):
            decode_token(token, secret="x" * 32)

    def test_invalid_token_raises(self):
        from backend.utils.auth import decode_token
        with pytest.raises(Exception):
            decode_token("garbage.token.here", secret="x" * 32)

    def test_wrong_secret_raises(self):
        from backend.utils.auth import create_access_token, decode_token
        token = create_access_token(user_id="abc-123", secret="x" * 32)
        with pytest.raises(Exception):
            decode_token(token, secret="y" * 32)
