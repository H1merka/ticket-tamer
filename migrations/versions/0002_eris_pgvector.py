"""add pgvector extension and kb_chunks table

Revision ID: 0002_eris_pgvector
Revises: 0001_initial_tables
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_eris_pgvector"
down_revision = "0001_initial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Create kb_chunks table ---
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_base.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="official_docs"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Add vector column via raw SQL (pgvector type)
    op.execute("ALTER TABLE kb_chunks ADD COLUMN embedding vector(1024)")

    # --- Indexes ---
    # HNSW index for general cosine search
    op.execute(
        "CREATE INDEX idx_kb_chunks_embedding_hnsw "
        "ON kb_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # Partial HNSW index for official_docs priority search
    op.execute(
        "CREATE INDEX idx_kb_chunks_official_embedding_hnsw "
        "ON kb_chunks USING hnsw (embedding vector_cosine_ops) "
        "WHERE source_type = 'official_docs'"
    )

    # B-tree indexes for filtering and cleanup
    op.create_index(
        "idx_kb_chunks_source_priority", "kb_chunks", ["source_type", "priority"]
    )
    op.create_index(
        "idx_kb_chunks_expires_at",
        "kb_chunks",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    op.create_index("idx_kb_chunks_article_id", "kb_chunks", ["article_id"])


def downgrade() -> None:
    op.drop_table("kb_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
