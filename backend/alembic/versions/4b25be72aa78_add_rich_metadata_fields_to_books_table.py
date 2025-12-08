"""Add rich metadata fields to books table

Revision ID: 4b25be72aa78
Revises: 001_initial
Create Date: 2025-12-08 15:57:46.935224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b25be72aa78'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to books table
    op.add_column('books', sa.Column('isbn13', sa.String(length=20), nullable=True))
    op.add_column('books', sa.Column('page_count', sa.Integer(), nullable=True))
    op.add_column('books', sa.Column('publisher', sa.Text(), nullable=True))
    op.add_column('books', sa.Column('publication_year', sa.Integer(), nullable=True))
    op.add_column('books', sa.Column('language', sa.String(length=10), nullable=True))
    op.add_column('books', sa.Column('average_rating', sa.DECIMAL(precision=3, scale=2), nullable=True))
    op.add_column('books', sa.Column('ratings_count', sa.Integer(), nullable=True))
    op.add_column('books', sa.Column('data_source', sa.String(length=50), nullable=True))
    op.add_column('books', sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False))

    # Recreate indexes with SQLAlchemy naming convention
    op.drop_index('idx_books_embedding', table_name='books', postgresql_with={'lists': '100'}, postgresql_using='ivfflat')
    op.drop_index('idx_books_isbn', table_name='books')
    op.create_index(op.f('ix_books_isbn'), 'books', ['isbn'], unique=True)
    op.create_index(op.f('ix_books_isbn13'), 'books', ['isbn13'], unique=False)
    op.create_index(op.f('ix_books_publication_year'), 'books', ['publication_year'], unique=False)

    # Recreate vector index (CRITICAL for performance)
    op.create_index(
        'idx_books_embedding',
        'books',
        ['embedding'],
        unique=False,
        postgresql_using='ivfflat',
        postgresql_with={'lists': '100'},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )

    # Create GIN index for array search on categories
    op.execute('CREATE INDEX idx_books_categories ON books USING GIN(categories)')

    # Recreate recommendation indexes with SQLAlchemy naming convention
    op.drop_index('idx_recommendations_book_id', table_name='recommendations')
    op.drop_index('idx_recommendations_created_at', table_name='recommendations')
    op.drop_index('idx_recommendations_session_id', table_name='recommendations')
    op.create_index(op.f('ix_recommendations_book_id'), 'recommendations', ['book_id'], unique=False)
    op.create_index(op.f('ix_recommendations_created_at'), 'recommendations', ['created_at'], unique=False)
    op.create_index(op.f('ix_recommendations_session_id'), 'recommendations', ['session_id'], unique=False)


def downgrade() -> None:
    # Revert recommendation indexes
    op.drop_index(op.f('ix_recommendations_session_id'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_created_at'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_book_id'), table_name='recommendations')
    op.create_index('idx_recommendations_session_id', 'recommendations', ['session_id'], unique=False)
    op.create_index('idx_recommendations_created_at', 'recommendations', ['created_at'], unique=False)
    op.create_index('idx_recommendations_book_id', 'recommendations', ['book_id'], unique=False)

    # Drop GIN index on categories
    op.execute('DROP INDEX IF EXISTS idx_books_categories')

    # Revert book indexes
    op.drop_index('idx_books_embedding', table_name='books', postgresql_with={'lists': '100'}, postgresql_using='ivfflat')
    op.drop_index(op.f('ix_books_publication_year'), table_name='books')
    op.drop_index(op.f('ix_books_isbn13'), table_name='books')
    op.drop_index(op.f('ix_books_isbn'), table_name='books')
    op.create_index('idx_books_isbn', 'books', ['isbn'], unique=True)
    op.create_index('idx_books_embedding', 'books', ['embedding'], unique=False, postgresql_with={'lists': '100'}, postgresql_using='ivfflat')

    # Remove new columns
    op.drop_column('books', 'updated_at')
    op.drop_column('books', 'data_source')
    op.drop_column('books', 'ratings_count')
    op.drop_column('books', 'average_rating')
    op.drop_column('books', 'language')
    op.drop_column('books', 'publication_year')
    op.drop_column('books', 'publisher')
    op.drop_column('books', 'page_count')
    op.drop_column('books', 'isbn13')
