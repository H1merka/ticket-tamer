"""create initial tables — tickets, knowledge_base, email_log

Revision ID: 0001_initial_tables
Revises:
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- knowledge_base (must exist before tickets FK) ---
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column(
            "source_type",
            sa.String(20),
            nullable=False,
            server_default="official_docs",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- tickets ---
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email_from", sa.String(255), nullable=False),
        sa.Column("email_to", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # ERIS NER fields
        sa.Column("fio", sa.String(255), nullable=True),
        sa.Column("organization", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("serial_numbers", JSONB, nullable=True),
        sa.Column("device_type", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        # AI results
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("entities", JSONB, server_default="{}"),
        # Response
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column(
            "kb_article_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_base.id"),
            nullable=True,
        ),
        # Status
        sa.Column("status", sa.String(30), server_default="new"),
        sa.Column("is_auto", sa.Boolean(), server_default=sa.text("true")),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- email_log ---
    op.create_table(
        "email_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id"),
            nullable=True,
        ),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("raw_headers", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(500), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("email_log")
    op.drop_table("tickets")
    op.drop_table("knowledge_base")
