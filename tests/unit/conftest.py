# Re-export the Postgres db_session fixture (defined for integration tests) so
# DB-backed unit tests (e.g. test_dedup.py B1/B2) can use a real session.
# Gated on TEST_DATABASE_URL — skips when unset.
from tests.integration.conftest import db_available, db_session  # noqa: F401
