"""Add normalized title and author columns for deduplication

Revision ID: 8c3f2a1d5e9b
Revises: 21a49b0bc640
Create Date: 2026-01-12

Adds title_normalized and author_normalized columns for flexible CSV upload
deduplication. These columns store lowercase, punctuation-free versions of
title and author to match books across different editions and formats.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c3f2a1d5e9b'
down_revision: Union[str, None] = '21a49b0bc640'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add normalized columns (nullable initially for backfill)
    op.add_column('books', sa.Column('title_normalized', sa.String(500), nullable=True))
    op.add_column('books', sa.Column('author_normalized', sa.String(500), nullable=True))

    # Create indexes for fast lookups
    op.create_index('ix_books_title_normalized', 'books', ['title_normalized'])
    op.create_index('ix_books_author_normalized', 'books', ['author_normalized'])

    # Create composite index for combined title+author lookups
    op.create_index(
        'ix_books_title_author_normalized',
        'books',
        ['title_normalized', 'author_normalized']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_books_title_author_normalized', table_name='books')
    op.drop_index('ix_books_author_normalized', table_name='books')
    op.drop_index('ix_books_title_normalized', table_name='books')

    # Drop columns
    op.drop_column('books', 'author_normalized')
    op.drop_column('books', 'title_normalized')
