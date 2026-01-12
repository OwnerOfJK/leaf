#!/usr/bin/env python3
"""Backfill normalized title and author columns for existing books.

This script populates the title_normalized and author_normalized columns
for all existing books in the database. Run this after applying the
migration that adds these columns.

Usage:
    cd backend
    python scripts/backfill_normalized_columns.py

The script processes books in batches to avoid memory issues and
provides progress updates.
"""

import logging
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.database import Book
from app.utils.csv_processor import normalize_author, normalize_title

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Batch size for processing
BATCH_SIZE = 1000


def backfill_normalized_columns():
    """Backfill normalized title and author columns for all books."""
    db = SessionLocal()

    try:
        # Get total count of books needing backfill
        total_books = db.query(func.count(Book.id)).filter(
            Book.title_normalized.is_(None)
        ).scalar()

        if total_books == 0:
            logger.info("No books need backfilling. All books already have normalized columns.")
            return

        logger.info(f"Found {total_books} books to backfill")

        processed = 0
        updated = 0

        while True:
            # Fetch a batch of books without normalized columns
            books = db.query(Book).filter(
                Book.title_normalized.is_(None)
            ).limit(BATCH_SIZE).all()

            if not books:
                break

            for book in books:
                book.title_normalized = normalize_title(book.title)
                book.author_normalized = normalize_author(book.author)
                updated += 1

            # Commit the batch
            db.commit()
            processed += len(books)

            logger.info(f"Progress: {processed}/{total_books} books processed ({processed * 100 // total_books}%)")

        logger.info(f"Backfill complete! Updated {updated} books.")

    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        db.rollback()
        raise

    finally:
        db.close()


def verify_backfill():
    """Verify that all books have normalized columns populated."""
    db = SessionLocal()

    try:
        # Count books with NULL normalized columns
        null_count = db.query(func.count(Book.id)).filter(
            Book.title_normalized.is_(None)
        ).scalar()

        total_count = db.query(func.count(Book.id)).scalar()

        if null_count == 0:
            logger.info(f"✓ Verification passed: All {total_count} books have normalized columns")
            return True
        else:
            logger.warning(f"✗ Verification failed: {null_count}/{total_count} books still have NULL normalized columns")
            return False

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill normalized columns for books")
    parser.add_argument("--verify-only", action="store_true", help="Only verify, don't backfill")
    args = parser.parse_args()

    if args.verify_only:
        verify_backfill()
    else:
        backfill_normalized_columns()
        verify_backfill()
