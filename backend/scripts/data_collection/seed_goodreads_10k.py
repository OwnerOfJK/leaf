#!/usr/bin/env python3
"""Seed database with goodbooks-10k dataset.

This script loads ~10,000 books from the goodbooks-10k dataset CSV file,
enriches them with Google Books API metadata, generates embeddings in batches,
and stores them in the database.

Usage:
    python scripts/data_collection/seed_goodreads_10k.py
    python scripts/data_collection/seed_goodreads_10k.py --limit 100  # Test with 100 books
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add backend directory to path to allow imports
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.constants import MAX_DESCRIPTION_LENGTH
from app.core.database import SessionLocal
from app.core.embeddings import create_embeddings_batch, format_book_text
from app.models.database import Book
from app.services.google_books_api import fetch_from_google_books
from app.utils.csv_processor import parse_goodbooks_10k_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CSV_PATH = backend_dir / "data" / "books.csv"
BATCH_SIZE = 500  # Number of books to process before generating embeddings
PROGRESS_LOG_INTERVAL = 50  # Log progress every N books


def process_books(csv_path: Path, limit: int | None = None) -> dict:
    """Process books from CSV and add to database.

    Args:
        csv_path: Path to the goodbooks-10k CSV file
        limit: Optional limit on number of books to process (for testing)

    Returns:
        Dictionary with processing statistics
    """
    db = SessionLocal()
    start_time = time.time()

    try:
        # Parse CSV
        logger.info(f"Parsing CSV file: {csv_path}")
        books_from_csv = parse_goodbooks_10k_csv(csv_path)

        if limit:
            books_from_csv = books_from_csv[:limit]
            logger.info(f"Limited to first {limit} books for testing")

        total_books = len(books_from_csv)
        logger.info(f"Parsed {total_books} books from CSV")

        # Statistics
        books_added = 0
        books_existing = 0
        books_failed = 0

        # Batch buffer for books needing embeddings
        batch_buffer = []

        # Pass 1: Check existing books and fetch metadata from Google Books
        logger.info("Pass 1: Checking existing books and fetching metadata...")

        for idx, book_data in enumerate(books_from_csv, 1):
            try:
                # Log progress
                if idx % PROGRESS_LOG_INTERVAL == 0:
                    logger.info(
                        f"Progress: [{idx}/{total_books}] "
                        f"Added: {books_added}, Existing: {books_existing}, Failed: {books_failed}"
                    )

                # Check if book exists in database (by ISBN or ISBN13)
                # According to deduplication strategy: use ISBN as primary key
                existing_book = None
                if book_data["isbn"]:
                    existing_book = db.query(Book).filter(Book.isbn == book_data["isbn"]).first()

                # If not found by ISBN, try ISBN13
                if not existing_book and book_data["isbn13"]:
                    existing_book = db.query(Book).filter(
                        or_(
                            Book.isbn == book_data["isbn13"],
                            Book.isbn13 == book_data["isbn13"]
                        )
                    ).first()

                if existing_book:
                    # Book already exists - skip
                    books_existing += 1
                    logger.debug(f"Book exists: {existing_book.title} (ID: {existing_book.id})")
                    continue

                # Book doesn't exist - fetch from Google Books API
                google_data = None
                if book_data["isbn"]:
                    google_data = fetch_from_google_books(book_data["isbn"])
                if not google_data and book_data["isbn13"]:
                    google_data = fetch_from_google_books(book_data["isbn13"])

                if not google_data:
                    # Could not fetch from Google Books - skip this book
                    books_failed += 1
                    logger.warning(
                        f"Skipping book (not found in Google Books): {book_data['title']} "
                        f"(ISBN: {book_data['isbn']}, ISBN13: {book_data['isbn13']})"
                    )
                    continue

                # Truncate description to MAX_DESCRIPTION_LENGTH
                description = google_data.get("description")
                if description and len(description) > MAX_DESCRIPTION_LENGTH:
                    description = description[:MAX_DESCRIPTION_LENGTH]
                    google_data["description"] = description

                # Prepare embedding text
                embedding_text = format_book_text(
                    title=google_data["title"],
                    author=google_data["author"],
                    description=description
                )

                # Add to batch buffer
                batch_buffer.append({
                    "google_data": google_data,
                    "embedding_text": embedding_text
                })

                logger.debug(
                    f"Collected book for batch: {google_data['title']} [{idx}/{total_books}]"
                )

                # Process batch if buffer is full
                if len(batch_buffer) >= BATCH_SIZE:
                    added = process_batch(db, batch_buffer)
                    books_added += added
                    batch_buffer = []

            except Exception as e:
                books_failed += 1
                logger.error(
                    f"Error processing book {idx}/{total_books}: {book_data.get('title', 'Unknown')}: {e}",
                    exc_info=True
                )
                continue

        # Pass 2: Process remaining books in buffer
        if batch_buffer:
            logger.info(f"Processing final batch of {len(batch_buffer)} books...")
            added = process_batch(db, batch_buffer)
            books_added += added

        # Final statistics
        elapsed_time = time.time() - start_time
        elapsed_minutes = elapsed_time / 60

        logger.info("=" * 80)
        logger.info("PROCESSING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total books processed: {total_books}")
        logger.info(f"Successfully added: {books_added}")
        logger.info(f"Already existed: {books_existing}")
        logger.info(f"Failed: {books_failed}")
        logger.info(f"Processing time: {elapsed_minutes:.2f} minutes")
        logger.info("=" * 80)

        return {
            "total_books": total_books,
            "books_added": books_added,
            "books_existing": books_existing,
            "books_failed": books_failed,
            "elapsed_time": elapsed_time
        }

    finally:
        db.close()


def process_batch(db: Session, batch_buffer: list[dict]) -> int:
    """Process a batch of books: generate embeddings and insert into database.

    Args:
        db: Database session
        batch_buffer: List of book dictionaries with google_data and embedding_text

    Returns:
        Number of books successfully added
    """
    if not batch_buffer:
        return 0

    logger.info(f"Generating embeddings for batch of {len(batch_buffer)} books...")

    try:
        # Extract all embedding texts
        embedding_texts = [book["embedding_text"] for book in batch_buffer]

        # Generate embeddings in batch (OpenAI supports up to 2048 inputs)
        embeddings = create_embeddings_batch(embedding_texts)

        # Insert all books with embeddings into database
        books_added = 0
        for book_info, embedding in zip(batch_buffer, embeddings):
            google_data = book_info["google_data"]

            new_book = Book(
                isbn=google_data["isbn"],
                isbn13=google_data["isbn13"],
                title=google_data["title"],
                author=google_data["author"],
                description=google_data.get("description"),
                categories=google_data.get("categories"),
                page_count=google_data.get("page_count"),
                publisher=google_data.get("publisher"),
                publication_year=google_data.get("publication_year"),
                language=google_data.get("language"),
                average_rating=google_data.get("average_rating"),
                ratings_count=google_data.get("ratings_count"),
                cover_url=google_data.get("cover_url"),
                embedding=embedding,
                data_source="goodreads_10k"
            )

            db.add(new_book)
            books_added += 1

        # Commit batch
        db.commit()
        logger.info(f"Successfully added {books_added} books to database")
        return books_added

    except Exception as e:
        logger.error(f"Error processing batch: {e}", exc_info=True)
        db.rollback()
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed database with goodbooks-10k dataset"
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to books.csv file (default: {DEFAULT_CSV_PATH})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of books to process (for testing)"
    )

    args = parser.parse_args()

    # Validate CSV file exists
    if not args.csv_path.exists():
        logger.error(f"CSV file not found: {args.csv_path}")
        sys.exit(1)

    logger.info("Starting goodbooks-10k data collection")
    logger.info(f"CSV file: {args.csv_path}")
    if args.limit:
        logger.info(f"Limit: {args.limit} books (TEST MODE)")

    # Process books
    try:
        result = process_books(args.csv_path, args.limit)

        # Exit with appropriate code
        if result["books_failed"] == result["total_books"]:
            logger.error("All books failed to process")
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
