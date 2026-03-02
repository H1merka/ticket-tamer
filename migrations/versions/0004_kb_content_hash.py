"""add content_hash column to knowledge_base

Revision ID: 0004_kb_content_hash
Revises: 0003_users
Create Date: 2025-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_kb_content_hash"
down_revision = "0003_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_base",
        sa.Column(
            "content_hash",
            sa.String(64),
            nullable=True,
            comment="SHA-256 hash of source content for incremental re-indexing",
        ),
    )
    op.create_index(
        "ix_knowledge_base_content_hash",
        "knowledge_base",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_base_content_hash", table_name="knowledge_base")
    op.drop_column("knowledge_base", "content_hash")
