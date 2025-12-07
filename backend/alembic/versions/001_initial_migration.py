"""Initial migration: books and recommendations tables

Revision ID: 001_initial
Revises:
Create Date: 2025-12-07
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Create books and recommendations tables with pgvector support."""

    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create books table
    op.create_table(
        'books',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('isbn', sa.String(length=20), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('author', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('categories', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('cover_url', sa.Text(), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for books table
    op.create_index('idx_books_isbn', 'books', ['isbn'], unique=True)
    op.execute(
        'CREATE INDEX idx_books_embedding ON books USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
    )

    # Create recommendations table
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.DECIMAL(precision=5, scale=2), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('trace_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for recommendations table
    op.create_index('idx_recommendations_session_id', 'recommendations', ['session_id'])
    op.create_index('idx_recommendations_book_id', 'recommendations', ['book_id'])
    op.create_index('idx_recommendations_created_at', 'recommendations', ['created_at'])


def downgrade() -> None:
    """Drop books and recommendations tables."""
    op.drop_index('idx_recommendations_created_at', table_name='recommendations')
    op.drop_index('idx_recommendations_book_id', table_name='recommendations')
    op.drop_index('idx_recommendations_session_id', table_name='recommendations')
    op.drop_table('recommendations')

    op.execute('DROP INDEX IF EXISTS idx_books_embedding')
    op.drop_index('idx_books_isbn', table_name='books')
    op.drop_table('books')
