#!/usr/bin/env python3
"""Collect NYT Bestseller books from 2008-2025.

This script fetches weekly bestseller lists from the NYT Books API,
enriches them with Google Books API metadata, generates embeddings in batches,
and stores them in the database.

Rate limits:
- 5 requests per minute (12 second sleep between requests)
- 500 requests per day (checkpoint and resume support)

Usage:
    python scripts/data_collection/collect_nyt_bestsellers.py
    python scripts/data_collection/collect_nyt_bestsellers.py --resume
    python scripts/data_collection/collect_nyt_bestsellers.py --limit 10  # Test mode
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
NYT_API_BASE_URL = "https://api.nytimes.com/svc/books/v3"
NYT_RATE_LIMIT_SLEEP = 12  # seconds (5 requests/min = 1 request/12s)
NYT_DAILY_LIMIT = 500
BATCH_SIZE = 500  # Books per embedding batch
CHECKPOINT_FILE = backend_dir / "scripts" / "data_collection" / "nyt_checkpoint.json"
START_DATE = datetime(2008, 6, 22)  # First date available in NYT Books API
END_DATE = datetime.now()

# Get API key from environment
from app.config import get_settings
settings = get_settings()


class NYTCollector:
    """Collector for NYT Bestseller books."""

    def __init__(self, api_key: str, resume: bool = False, limit: int | None = None):
        """Initialize collector.

        Args:
            api_key: NYT Books API key
            resume: Whether to resume from checkpoint
            limit: Optional limit on total requests (for testing)
        """
        self.api_key = api_key
        self.limit = limit
        self.request_count = 0
        self.daily_request_count = 0
        self.checkpoint_data = self._load_checkpoint() if resume else {}
        self.session = requests.Session()

        # Statistics
        self.books_added = 0
        self.books_existing = 0
        self.books_failed = 0
        self.isbns_seen = set()  # For deduplication across weeks

        # Batch buffer
        self.batch_buffer = []

        # Track last successful date for interruption handling
        self.last_successful_date = None

    def _load_checkpoint(self) -> dict:
        """Load checkpoint data from file."""
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded checkpoint: processed {data.get('request_count', 0)} requests")
                return data
        return {}

    def _save_checkpoint(self, list_name: str, date: str):
        """Save checkpoint data to file."""
        checkpoint = {
            "list_name": list_name,
            "last_date": date,
            "request_count": self.request_count,
            "books_added": self.books_added,
            "books_existing": self.books_existing,
            "books_failed": self.books_failed,
            "timestamp": datetime.now().isoformat()
        }
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        logger.debug(f"Saved checkpoint: {list_name} @ {date}")

    def _make_request(self, endpoint: str, params: dict) -> dict | None:
        """Make API request with rate limiting and error handling.

        Args:
            endpoint: API endpoint (e.g., "/lists.json")
            params: Query parameters

        Returns:
            JSON response or None if error
        """
        # Check daily limit
        if self.daily_request_count >= NYT_DAILY_LIMIT:
            logger.warning(
                f"Hit daily limit of {NYT_DAILY_LIMIT} requests. "
                f"Checkpoint saved. Resume tomorrow with --resume flag."
            )
            return None

        # Check test limit
        if self.limit and self.request_count >= self.limit:
            logger.info(f"Reached test limit of {self.limit} requests")
            return None

        url = f"{NYT_API_BASE_URL}{endpoint}"
        params["api-key"] = self.api_key

        try:
            # Rate limiting: sleep before request
            if self.request_count > 0:
                logger.debug(f"Sleeping {NYT_RATE_LIMIT_SLEEP}s for rate limiting...")
                time.sleep(NYT_RATE_LIMIT_SLEEP)

            response = self.session.get(url, params=params, timeout=30)

            self.request_count += 1
            self.daily_request_count += 1

            if response.status_code == 429:
                logger.warning("Rate limit exceeded (429). Sleeping for 60s...")
                time.sleep(60)
                return None

            if response.status_code != 200:
                logger.error(f"NYT API returned status {response.status_code}: {response.text}")
                return None

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    def fetch_overview_for_date(self, date: str) -> list[dict] | None:
        """Fetch all bestseller lists for a specific date using overview endpoint.

        This is more efficient than fetching each list individually - we get
        all lists in a single API call.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            List of book dictionaries with ISBN, title, author, list_name
            None if request failed or hit rate limit
        """
        data = self._make_request(
            "/lists/overview.json",
            {"published_date": date}
        )

        if not data:
            return None

        if "results" not in data:
            logger.warning(f"No 'results' in response for {date}: {data}")
            return []

        results = data["results"]
        if not results:
            logger.warning(f"Empty 'results' for {date}")
            return []

        lists = results.get("lists")
        if lists is None:
            logger.warning(f"'lists' key is None for {date}")
            return []

        books = []
        for list_info in lists:
            list_name = list_info.get("list_name_encoded", "unknown")

            for book_item in list_info.get("books", []):
                # Extract ISBNs (try primary_isbn13 first, then primary_isbn10)
                isbn13 = book_item.get("primary_isbn13") or None
                isbn10 = book_item.get("primary_isbn10") or None

                # Skip if no ISBN
                if not isbn13 and not isbn10:
                    continue

                books.append({
                    "isbn": isbn10,
                    "isbn13": isbn13,
                    "title": book_item.get("title", "Unknown"),
                    "author": book_item.get("author", "Unknown"),
                    "rank": book_item.get("rank"),
                    "list_name": list_name
                })

        return books

    def process_books(self, db: Session):
        """Main processing loop: fetch weekly overview and add books to database."""
        start_time = time.time()

        # Resume from checkpoint if available
        start_date = START_DATE
        if self.checkpoint_data:
            checkpoint_date = self.checkpoint_data.get("last_date")
            if checkpoint_date:
                start_date = datetime.strptime(checkpoint_date, "%Y-%m-%d")
                start_date += timedelta(weeks=1)  # Start from next week
                logger.info(f"Resuming from {start_date.date()}")

        # Process each week from start to end date
        current_date = start_date
        weeks_processed = 0

        while current_date <= END_DATE:
            date_str = current_date.strftime("%Y-%m-%d")

            logger.info("=" * 80)
            logger.info(f"Fetching all lists for week of {date_str}")
            logger.info("=" * 80)

            books = self.fetch_overview_for_date(date_str)

            if books is None:  # Hit rate limit or test limit
                # Save the last SUCCESSFULLY processed date, not the current one we couldn't fetch
                checkpoint_date = self.last_successful_date or date_str
                self._save_checkpoint("overview", checkpoint_date)
                logger.info(f"Stopping. Last successful date: {checkpoint_date}")
                break

            if len(books) == 0:
                logger.info(f"No books found for {date_str} (may be before API data starts)")
                # Move to next week and continue
                weeks_processed += 1
                current_date += timedelta(weeks=1)
                continue

            logger.info(f"Found {len(books)} books across all lists for {date_str}")

            # Process each book
            books_processed_this_week = 0
            quota_exceeded = False
            for book_data in books:
                list_name = book_data.get("list_name", "unknown")
                before_count = len(self.batch_buffer)
                result = self._process_single_book(db, book_data, list_name)

                # Check if Google Books quota was exceeded
                if result == "QUOTA_EXCEEDED":
                    quota_exceeded = True
                    break

                if len(self.batch_buffer) > before_count:
                    books_processed_this_week += 1

            # If quota exceeded, stop processing and save checkpoint at PREVIOUS week
            if quota_exceeded:
                logger.error("=" * 80)
                logger.error("GOOGLE BOOKS QUOTA EXCEEDED")
                logger.error("=" * 80)
                logger.error("Stopping to prevent data loss.")
                logger.error("The quota typically resets after 24 hours.")

                # Process remaining batch
                if self.batch_buffer:
                    logger.info(f"Processing batch of {len(self.batch_buffer)} books before stopping...")
                    added = self._process_batch(db)
                    self.books_added += added
                    self.batch_buffer = []

                # Save checkpoint at PREVIOUS successfully completed week
                if self.last_successful_date:
                    self._save_checkpoint("quota_exceeded", self.last_successful_date)
                    logger.info(f"Checkpoint saved at last successful week: {self.last_successful_date}")
                    logger.info("Resume with --resume flag after quota resets (usually 24 hours)")
                break

            logger.info(
                f"Week summary: {books_processed_this_week} new books, "
                f"{len(books) - books_processed_this_week} duplicates/existing"
            )

            # Save checkpoint after each week
            weeks_processed += 1
            self.last_successful_date = date_str
            self._save_checkpoint("overview", date_str)

            logger.info(f"Completed week {weeks_processed}, moving to next week...")

            # Move to next week
            current_date += timedelta(weeks=1)

        # Process remaining books in batch buffer
        if self.batch_buffer:
            logger.info(f"Processing final batch of {len(self.batch_buffer)} books...")
            added = self._process_batch(db)
            self.books_added += added
            if added == 0 and len(self.batch_buffer) > 0:
                logger.error(f"Final batch processing failed - 0 books added!")
                self.books_failed += len(self.batch_buffer)

        # Final statistics
        elapsed_time = time.time() - start_time
        elapsed_minutes = elapsed_time / 60

        logger.info("=" * 80)
        logger.info("PROCESSING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total API requests: {self.request_count}")
        logger.info(f"Unique ISBNs seen: {len(self.isbns_seen)}")
        logger.info(f"Books added: {self.books_added}")
        logger.info(f"Books existing: {self.books_existing}")
        logger.info(f"Books failed: {self.books_failed}")
        logger.info(f"Processing time: {elapsed_minutes:.2f} minutes")
        logger.info("=" * 80)

        # Checkpoint remains saved for reference/resume
        if CHECKPOINT_FILE.exists():
            logger.info(f"Checkpoint saved at: {CHECKPOINT_FILE}")

    def _process_single_book(self, db: Session, book_data: dict, list_name: str):
        """Process a single book: check existence, fetch metadata, add to batch.

        Args:
            db: Database session
            book_data: Book data from NYT API
            list_name: Name of the bestseller list
        """
        # Deduplicate: skip if we've already seen this ISBN
        isbn = book_data["isbn"]
        isbn13 = book_data["isbn13"]

        dedup_key = isbn or isbn13
        if dedup_key in self.isbns_seen:
            # Already processed this ISBN in a previous week
            return

        self.isbns_seen.add(dedup_key)

        # Check if book exists in database (isbn13 is primary identifier)
        existing_book = None
        if isbn13:
            existing_book = db.query(Book).filter(
                or_(Book.isbn13 == isbn13, Book.isbn == isbn13)
            ).first()
        if not existing_book and isbn:
            existing_book = db.query(Book).filter(
                or_(Book.isbn13 == isbn, Book.isbn == isbn)
            ).first()

        if existing_book:
            self.books_existing += 1
            logger.info(f"✓ Book already in database: {existing_book.title} (ISBN: {dedup_key})")
            return

        # Fetch from Google Books API
        google_data = None
        if isbn:
            google_data = fetch_from_google_books(isbn)
        if not google_data and isbn13:
            google_data = fetch_from_google_books(isbn13)

        # Check if quota was exceeded
        if google_data == "QUOTA_EXCEEDED":
            logger.error(
                f"⚠️  GOOGLE BOOKS QUOTA EXCEEDED - Stopping to preserve data. "
                f"Book: {book_data['title']} (ISBN: {isbn or isbn13})"
            )
            # Return special signal to stop processing
            return "QUOTA_EXCEEDED"

        if not google_data:
            self.books_failed += 1
            logger.warning(
                f"✗ FAILED - Not in Google Books: {book_data['title']} "
                f"(ISBN: {isbn}, ISBN13: {isbn13})"
            )
            return

        # Validate and normalize ISBN identifiers
        # isbn13 is required for database, isbn (ISBN-10) is optional
        google_isbn = google_data.get("isbn")
        google_isbn13 = google_data.get("isbn13")

        if not google_isbn and not google_isbn13:
            # No ISBN identifiers from Google Books - skip this book
            self.books_failed += 1
            logger.warning(
                f"✗ FAILED - No ISBN in Google Books response: {google_data.get('title')} "
                f"by {google_data.get('author')}"
            )
            return

        # Ensure isbn13 is always set (required field in database)
        if not google_isbn13 and google_isbn:
            google_data["isbn13"] = google_isbn
            logger.debug(f"Using ISBN-10 as ISBN-13 for: {google_data.get('title')}")

        # Truncate description
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
        self.batch_buffer.append({
            "google_data": google_data,
            "embedding_text": embedding_text
        })

        logger.info(f"→ Added to batch ({len(self.batch_buffer)}/{BATCH_SIZE}): {google_data['title']}")

        # Process batch if full
        if len(self.batch_buffer) >= BATCH_SIZE:
            logger.info(f"Batch full ({BATCH_SIZE} books), processing...")
            added = self._process_batch(db)
            self.books_added += added
            if added == 0:
                logger.error(f"Batch processing failed - 0 books added!")
                self.books_failed += len(self.batch_buffer)
            self.batch_buffer = []

    def _process_batch(self, db: Session) -> int:
        """Generate embeddings for batch and insert into database."""
        if not self.batch_buffer:
            return 0

        logger.info(f"Generating embeddings for batch of {len(self.batch_buffer)} books...")

        try:
            # Extract embedding texts
            embedding_texts = [book["embedding_text"] for book in self.batch_buffer]

            # Generate embeddings in batch
            embeddings = create_embeddings_batch(embedding_texts)

            # Insert books with embeddings
            books_added = 0
            for book_info, embedding in zip(self.batch_buffer, embeddings):
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
                    data_source="nyt_bestseller"
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
        description="Collect NYT Bestseller books from 2008-2025"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of API requests (for testing)"
    )

    args = parser.parse_args()

    # Check for API key
    if not hasattr(settings, 'nyt_books_api_key') or not settings.nyt_books_api_key:
        logger.error("NYT Books API key not found in settings. Please set NYT_BOOKS_API_KEY in .env")
        sys.exit(1)

    logger.info("Starting NYT Bestseller data collection")
    if args.resume:
        logger.info("Resume mode: continuing from checkpoint")
    if args.limit:
        logger.info(f"Test mode: limiting to {args.limit} requests")

    # Initialize collector
    collector = NYTCollector(
        api_key=settings.nyt_books_api_key,
        resume=args.resume,
        limit=args.limit
    )

    # Process books
    db = SessionLocal()
    try:
        collector.process_books(db)
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n" + "=" * 80)
        logger.warning("Processing interrupted by user (Ctrl-C)")
        logger.warning("=" * 80)

        # Process remaining batch before exiting
        if collector.batch_buffer:
            logger.info(f"Processing remaining batch of {len(collector.batch_buffer)} books before exit...")
            try:
                added = collector._process_batch(db)
                collector.books_added += added
                if added > 0:
                    logger.info(f"✓ Successfully saved {added} books from batch")
                else:
                    logger.error("✗ Batch processing failed")
                    collector.books_failed += len(collector.batch_buffer)
            except Exception as e:
                logger.error(f"Error processing final batch: {e}", exc_info=True)
                collector.books_failed += len(collector.batch_buffer)

        # Save final checkpoint at last successful week (not today's date!)
        checkpoint_date = collector.last_successful_date or START_DATE.strftime("%Y-%m-%d")
        collector._save_checkpoint("interrupted", checkpoint_date)

        logger.info("=" * 80)
        logger.info(f"Books added: {collector.books_added}")
        logger.info(f"Books existing: {collector.books_existing}")
        logger.info(f"Books failed: {collector.books_failed}")
        logger.info(f"Checkpoint saved. Resume with --resume flag to continue.")
        logger.info("=" * 80)
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
