"""Make isbn13 the primary identifier (NOT NULL), isbn becomes nullable

Revision ID: 21a49b0bc640
Revises: 4b25be72aa78
Create Date: 2026-01-11

ISBN-13 has been the standard since 2007. All books have ISBN-13, but not all
have ISBN-10. This migration makes isbn13 the required field and isbn optional.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21a49b0bc640'
down_revision: Union[str, None] = '4b25be72aa78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Backfill isbn13 from isbn where isbn13 is NULL
    # This ensures all existing records have an isbn13 value before we make it NOT NULL
    op.execute("""
        UPDATE books
        SET isbn13 = isbn
        WHERE isbn13 IS NULL AND isbn IS NOT NULL
    """)

    # Step 2: Drop the unique index on isbn (created in previous migration as ix_books_isbn)
    op.drop_index('ix_books_isbn', table_name='books')

    # Step 3: Drop the existing non-unique index on isbn13
    op.drop_index('ix_books_isbn13', table_name='books')

    # Step 4: Make isbn13 NOT NULL
    op.alter_column('books', 'isbn13',
                    existing_type=sa.String(length=20),
                    nullable=False)

    # Step 5: Make isbn nullable
    op.alter_column('books', 'isbn',
                    existing_type=sa.String(length=20),
                    nullable=True)

    # Step 6: Create unique index on isbn13 and regular index on isbn
    op.create_index('ix_books_isbn13', 'books', ['isbn13'], unique=True)
    op.create_index('ix_books_isbn', 'books', ['isbn'], unique=False)


def downgrade() -> None:
    # Reverse the process

    # Step 1: Drop indexes
    op.drop_index('ix_books_isbn', table_name='books')
    op.drop_index('ix_books_isbn13', table_name='books')

    # Step 2: Make isbn NOT NULL (will fail if any NULL values exist)
    op.alter_column('books', 'isbn',
                    existing_type=sa.String(length=20),
                    nullable=False)

    # Step 3: Make isbn13 nullable again
    op.alter_column('books', 'isbn13',
                    existing_type=sa.String(length=20),
                    nullable=True)

    # Step 4: Recreate original unique index on isbn
    op.create_index('ix_books_isbn', 'books', ['isbn'], unique=True)

    # Step 5: Recreate non-unique index on isbn13
    op.create_index('ix_books_isbn13', 'books', ['isbn13'], unique=False)
