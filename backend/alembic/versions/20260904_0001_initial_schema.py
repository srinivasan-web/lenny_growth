"""Create the initial conversation and transcript-vector schema.

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "20260904_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "episodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=128)),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("guest_name", sa.String(length=255)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("source_url"),
    )
    op.create_index("ix_episodes_guest_name", "episodes", ["guest_name"])
    op.create_index("ix_episodes_published_at", "episodes", ["published_at"])
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32)),
        sa.Column("model", sa.String(length=128)),
        sa.Column("source_metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_session_created_at", "messages", ["session_id", "created_at"])
    op.create_table(
        "transcripts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("episode_id", sa.UUID(), nullable=False),
        sa.Column("source_url", sa.String(length=2048)),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("ingest_metadata", postgresql.JSONB()),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id"),
        sa.UniqueConstraint("source_url"),
    )
    op.create_index("ix_transcripts_content_hash", "transcripts", ["content_hash"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("artifact_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("artifact_type IN ('markdown', 'html')", name="ck_artifacts_type"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_message_id", "artifacts", ["message_id"])
    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transcript_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Float()),
        sa.Column("end_seconds", sa.Float()),
        sa.Column("topic", sa.String(length=500)),
        sa.Column("chunk_metadata", postgresql.JSONB()),
        sa.Column("embedding", Vector(dim=384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("token_count > 0", name="ck_transcript_chunks_token_count"),
        sa.CheckConstraint("end_seconds IS NULL OR start_seconds IS NULL OR end_seconds >= start_seconds", name="ck_transcript_chunks_time_range"),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transcript_id", "chunk_index", name="uq_transcript_chunks_transcript_index"),
    )
    op.create_index("ix_transcript_chunks_transcript_id", "transcript_chunks", ["transcript_id"])
    op.execute("CREATE INDEX ix_transcript_chunks_embedding_hnsw ON transcript_chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcript_chunks_embedding_hnsw")
    op.drop_table("transcript_chunks")
    op.drop_table("artifacts")
    op.drop_index("ix_transcripts_content_hash", table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_table("messages")
    op.drop_table("episodes")
    op.drop_table("sessions")
