"""uploaded_files: add content_hash (sha256) for duplicate detection

Revision ID: 003
Revises: 002
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uploaded_files",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_uploaded_files_content_hash", "uploaded_files", ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_uploaded_files_content_hash", table_name="uploaded_files")
    op.drop_column("uploaded_files", "content_hash")
