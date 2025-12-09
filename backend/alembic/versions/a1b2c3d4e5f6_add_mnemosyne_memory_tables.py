"""
Add Mnemosyne memory tables for long-term agent memory.

Creates:
- memories: Core episodic memory storage with vector embeddings
- memory_anchors: Symbolic links to code artifacts (files, symbols)

Revision ID: a1b2c3d4e5f6
Revises: 74567b34c2a1
Create Date: 2025-12-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "74567b34c2a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Mnemosyne memory tables with pgvector support."""

    # Enable pgvector extension (safe to run multiple times)
    # Wrapped in try/except for environments where extension is pre-installed
    # or user lacks CREATE EXTENSION permissions
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as e:
        import logging
        logging.warning(f"Could not create vector extension (may already exist): {e}")

    # Core memory storage table
    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "embedding",
            # Using raw SQL for vector type since alembic doesn't have native support
            # 1536 dimensions for text-embedding-3-small
            sa.Column("embedding", sa.LargeBinary(), nullable=True),
        ),
        sa.Column("memory_type", sa.String(50), nullable=False, default="task_outcome"),
        sa.Column("confidence", sa.Float(), nullable=False, default=1.0),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Replace the embedding column with proper vector type
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE memories ADD COLUMN embedding vector(1536)")

    # Symbolic anchors for graph-based retrieval
    op.create_table(
        "memory_anchors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "memory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("symbol_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index("ix_memories_task_id", "memories", ["task_id"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_created_at", "memories", ["created_at"])
    op.create_index("ix_memory_anchors_memory_id", "memory_anchors", ["memory_id"])
    op.create_index("ix_memory_anchors_file_path", "memory_anchors", ["file_path"])

    # HNSW index for fast approximate nearest neighbor search on embeddings
    # Using cosine distance (vector_cosine_ops) which is standard for text embeddings
    op.execute("""
        CREATE INDEX ix_memories_embedding_hnsw
        ON memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """Remove Mnemosyne memory tables."""
    op.drop_index("ix_memories_embedding_hnsw", table_name="memories")
    op.drop_index("ix_memory_anchors_file_path", table_name="memory_anchors")
    op.drop_index("ix_memory_anchors_memory_id", table_name="memory_anchors")
    op.drop_index("ix_memories_created_at", table_name="memories")
    op.drop_index("ix_memories_memory_type", table_name="memories")
    op.drop_index("ix_memories_task_id", table_name="memories")
    op.drop_table("memory_anchors")
    op.drop_table("memories")
