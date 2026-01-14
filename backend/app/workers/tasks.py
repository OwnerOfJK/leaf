"""Celery tasks for async processing."""

import logging
from pathlib import Path

from sqlalchemy import and_, or_
from sqlalchemy.dialects.postgresql import insert

from app.constants import CSV_PROGRESS_UPDATE_INTERVAL, MAX_DESCRIPTION_LENGTH
from app.core.database import SessionLocal
from app.core.embeddings import create_embeddings_batch, format_book_text
from app.core.redis_client import session_manager
from app.models.database import Book
from app.services.google_books_api import (
    fetch_from_google_books,
    reset_quota_circuit,
    search_by_title_author,
)
from app.utils.csv_processor import (
    get_csv_preview,
    normalize_author,
    normalize_title,
    parse_flexible_csv,
    validate_csv_file,
)
from app.utils.isbn_utils import normalize_isbn
from app.utils.schema_detector import detect_csv_schema
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks.process_csv_upload", bind=True)
def process_csv_upload(self, session_id: str, file_path: str) -> dict:
    """Process uploaded CSV file asynchronously with flexible format support.

    This task:
    1. Detects CSV schema using LLM
    2. Parses the CSV file using detected schema
    3. For each book:
       - Checks if it exists in PostgreSQL (by ISBN or title+author)
       - If not, fetches metadata from Google Books API
       - Generates embedding
       - Inserts into database
    4. Updates Redis session with user's book IDs, ratings, and read status
    5. Updates CSV processing status

    Args:
        session_id: Session ID for tracking
        file_path: Absolute path to uploaded CSV file

    Returns:
        Dictionary with processing results:
        {
            'status': 'completed' | 'failed',
            'books_processed': int,
            'books_added': int,
            'books_existing': int,
            'books_failed': int,
            'error': str | None
        }
    """
    db = SessionLocal()
    csv_path = Path(file_path)

    # Reset Google Books API circuit breaker for this task
    reset_quota_circuit()

    try:
        # Update status to processing
        session_manager.set_csv_status(session_id, "processing")
        logger.info(f"Starting CSV processing for session {session_id}")

        # Validate CSV file
        validate_csv_file(csv_path)

        # Step 1: Detect CSV schema using LLM
        logger.info("Detecting CSV schema...")
        headers, sample_rows = get_csv_preview(csv_path)
        schema_mapping = detect_csv_schema(headers, sample_rows)
        logger.info(f"Detected schema: {schema_mapping}")

        # Step 2: Parse CSV using detected schema
        books_from_csv = parse_flexible_csv(csv_path, schema_mapping)
        total_books = len(books_from_csv)
        logger.info(f"Parsed {total_books} books from CSV")

        books_added = 0
        books_existing = 0
        books_failed = 0
        user_books = []  # List of {book_id, title, author, user_rating, exclusive_shelf}

        # Track seen ISBNs (normalized to ISBN-13) for deduplication within batch
        isbns_seen = set()

        # Pass 1: Collect existing books and new books needing embeddings
        new_books_to_add = []  # List of {google_data, embedding_text, user_rating, exclusive_shelf}

        for idx, book_data in enumerate(books_from_csv, 1):
            try:
                # Extend session TTL periodically to keep it alive during processing
                if idx % CSV_PROGRESS_UPDATE_INTERVAL == 0:
                    session_manager.extend_session_ttl(session_id)
                    logger.debug(f"Extended session TTL at book {idx}/{total_books}")

                # Update progress metadata
                session_manager.set_metadata(session_id, {
                    "total_books": total_books,
                    "processed": idx,
                    "added": books_added,
                    "existing": books_existing,
                    "failed": books_failed
                })

                # Extract book data
                isbn = book_data.get("isbn")
                isbn13 = book_data.get("isbn13")
                title = book_data.get("title", "Unknown Title")
                author = book_data.get("author", "Unknown Author")
                title_normalized = book_data.get("title_normalized") or normalize_title(title)
                author_normalized = book_data.get("author_normalized") or normalize_author(author)

                # Normalize ISBNs for consistent deduplication
                normalized_key = normalize_isbn(isbn13) or normalize_isbn(isbn)

                # Create a dedup key for this batch (use ISBN if available, else title+author)
                if normalized_key:
                    batch_dedup_key = f"isbn:{normalized_key}"
                else:
                    batch_dedup_key = f"ta:{title_normalized}:{author_normalized}"

                # Skip if already seen in this batch
                if batch_dedup_key in isbns_seen:
                    logger.info(f"Skipping duplicate in batch: '{title}' by '{author}' (key: {batch_dedup_key})")
                    continue
                isbns_seen.add(batch_dedup_key)

                # Check if book exists in database
                existing_book = None

                # First: Check by ISBN (if available)
                if normalized_key:
                    existing_book = db.query(Book).filter(
                        or_(Book.isbn13 == normalized_key, Book.isbn == normalized_key)
                    ).first()

                    # Also check with original ISBNs as fallback
                    if not existing_book and isbn13:
                        existing_book = db.query(Book).filter(
                            or_(Book.isbn13 == isbn13, Book.isbn == isbn13)
                        ).first()
                    if not existing_book and isbn:
                        existing_book = db.query(Book).filter(
                            or_(Book.isbn13 == isbn, Book.isbn == isbn)
                        ).first()

                # Second: Check by normalized title+author (catches different editions)
                if not existing_book and title_normalized and author_normalized:
                    existing_book = db.query(Book).filter(
                        and_(
                            Book.title_normalized == title_normalized,
                            Book.author_normalized == author_normalized
                        )
                    ).first()

                if existing_book:
                    # Book already exists
                    books_existing += 1
                    user_books.append({
                        "book_id": existing_book.id,
                        "title": existing_book.title,
                        "author": existing_book.author,
                        "user_rating": book_data.get("user_rating", 0),
                        "exclusive_shelf": book_data.get("exclusive_shelf", "read")
                    })
                    logger.info(
                        f"Skipping existing book: '{existing_book.title}' by '{existing_book.author}' "
                        f"(DB ID: {existing_book.id}, ISBN13: {existing_book.isbn13})"
                    )
                    continue

                # Book doesn't exist - fetch from Google Books API
                google_data = None

                # Strategy 1: Try ISBN lookup (most accurate)
                if isbn:
                    google_data = fetch_from_google_books(isbn)
                if (not google_data or google_data == "QUOTA_EXCEEDED") and isbn13:
                    google_data = fetch_from_google_books(isbn13)

                # Strategy 2: If no ISBN or ISBN lookup failed, try title+author search
                if (not google_data or google_data == "QUOTA_EXCEEDED") and title != "Unknown Title":
                    logger.info(f"No ISBN available, searching by title+author: '{title}' by '{author}'")
                    google_data = search_by_title_author(title, author)

                if not google_data or google_data == "QUOTA_EXCEEDED":
                    # Could not fetch from Google Books - skip this book
                    books_failed += 1
                    reason = "quota exceeded" if google_data == "QUOTA_EXCEEDED" else "not found in Google Books"
                    logger.warning(
                        f"Skipping book ({reason}): {title} by {author} "
                        f"(ISBN: {isbn}, ISBN13: {isbn13})"
                    )
                    continue

                # Validate and normalize ISBN identifiers from Google Books
                # isbn13 is required for database, isbn (ISBN-10) is optional
                google_isbn = google_data.get("isbn")
                google_isbn13 = google_data.get("isbn13")

                if not google_isbn and not google_isbn13:
                    # No ISBN identifiers at all - skip this book
                    books_failed += 1
                    logger.warning(
                        f"Skipping book (no ISBN in Google Books response): {google_data.get('title')} "
                        f"by {google_data.get('author')}"
                    )
                    continue

                # Normalize Google's ISBN-13 for deduplication
                google_normalized = normalize_isbn(google_isbn13) or normalize_isbn(google_isbn)

                # Check if Google returned a different ISBN than source (different edition)
                # Add Google's normalized ISBN to seen set to prevent duplicates
                if google_normalized and google_normalized != normalized_key:
                    if google_normalized in isbns_seen:
                        # Already processed this book via different source ISBN
                        logger.info(
                            f"Skipping duplicate edition: '{google_data.get('title')}' by '{google_data.get('author')}' "
                            f"(Google ISBN13: {google_normalized}, source ISBN: {normalized_key})"
                        )
                        continue
                    isbns_seen.add(google_normalized)

                # Ensure isbn13 is always set (required field)
                if not google_isbn13 and google_isbn:
                    google_data["isbn13"] = google_isbn
                    logger.debug(f"Using ISBN-10 as ISBN-13 for: {google_data.get('title')}")

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

                # Collect for batch processing
                new_books_to_add.append({
                    "google_data": google_data,
                    "embedding_text": embedding_text,
                    "user_rating": book_data.get("user_rating", 0),
                    "exclusive_shelf": book_data.get("exclusive_shelf", "read")
                })

                logger.debug(
                    f"Collected book for batch embedding: {google_data['title']} "
                    f"[{idx}/{total_books}]"
                )

            except Exception as e:
                books_failed += 1
                logger.error(
                    f"Error processing book {idx}/{total_books}: {book_data.get('title', 'Unknown')}: {e}",
                    exc_info=True
                )
                # Continue processing remaining books
                continue

        # Pass 2: Batch generate embeddings for all new books
        if new_books_to_add:
            logger.info(f"Generating embeddings for {len(new_books_to_add)} new books in batch")

            try:
                # Extract all embedding texts
                embedding_texts = [book["embedding_text"] for book in new_books_to_add]

                # Generate all embeddings in a single batch call (or multiple if > 2048)
                all_embeddings = []
                batch_size = 2048
                for i in range(0, len(embedding_texts), batch_size):
                    batch = embedding_texts[i:i + batch_size]
                    batch_embeddings = create_embeddings_batch(batch)
                    all_embeddings.extend(batch_embeddings)
                    logger.debug(f"Generated {len(batch_embeddings)} embeddings (batch {i//batch_size + 1})")

                # Pass 3: Build book records for bulk insert
                book_records = []
                isbn13_to_user_data = {}  # Map isbn13 -> user data for later lookup

                for book_info, embedding in zip(new_books_to_add, all_embeddings):
                    google_data = book_info["google_data"]
                    isbn13 = google_data["isbn13"]
                    book_title = google_data["title"]
                    book_author = google_data["author"]

                    book_records.append({
                        "isbn": google_data["isbn"],
                        "isbn13": isbn13,
                        "title": book_title,
                        "author": book_author,
                        "title_normalized": normalize_title(book_title),
                        "author_normalized": normalize_author(book_author),
                        "description": google_data.get("description"),
                        "categories": google_data.get("categories"),
                        "page_count": google_data.get("page_count"),
                        "publisher": google_data.get("publisher"),
                        "publication_year": google_data.get("publication_year"),
                        "language": google_data.get("language"),
                        "average_rating": google_data.get("average_rating"),
                        "ratings_count": google_data.get("ratings_count"),
                        "cover_url": google_data.get("cover_url"),
                        "embedding": embedding,
                        "data_source": "google_books"
                    })

                    # Store user-specific data for later lookup
                    isbn13_to_user_data[isbn13] = {
                        "user_rating": book_info["user_rating"],
                        "exclusive_shelf": book_info["exclusive_shelf"]
                    }

                # Use INSERT ... ON CONFLICT DO NOTHING to skip duplicates
                stmt = insert(Book).values(book_records).on_conflict_do_nothing(
                    index_elements=["isbn13"]
                )
                result = db.execute(stmt)
                db.flush()

                # Get actual inserted count
                inserted_count = result.rowcount if result.rowcount >= 0 else len(book_records)
                skipped_count = len(book_records) - inserted_count
                books_added += inserted_count

                if skipped_count > 0:
                    logger.info(f"Inserted {inserted_count} books, skipped {skipped_count} duplicates")

                # Query for all books by isbn13 to get their IDs (includes both inserted and existing)
                isbn13_list = list(isbn13_to_user_data.keys())
                inserted_books = db.query(Book).filter(Book.isbn13.in_(isbn13_list)).all()

                for book in inserted_books:
                    user_data = isbn13_to_user_data.get(book.isbn13)
                    if user_data:
                        user_books.append({
                            "book_id": book.id,
                            "title": book.title,
                            "author": book.author,
                            "user_rating": user_data["user_rating"],
                            "exclusive_shelf": user_data["exclusive_shelf"]
                        })
                        logger.info(f"Added book to user library: {book.title} (ID: {book.id})")

            except Exception as e:
                logger.error(f"Error during batch embedding generation: {e}", exc_info=True)
                db.rollback()  # Rollback failed transaction before continuing
                books_failed += len(new_books_to_add)
                # Continue with existing books only

        # Commit all changes
        db.commit()

        # Update session with user's books
        session_data = session_manager.get_session(session_id)
        if session_data:
            session_data["books_from_csv"] = user_books
            session_data["csv_uploaded"] = True

            session_manager.update_session(session_id, session_data)

        # Update status to completed
        session_manager.set_csv_status(session_id, "completed")

        # Update final metadata
        final_metadata = {
            "total_books": total_books,
            "processed": total_books,
            "added": books_added,
            "existing": books_existing,
            "failed": books_failed
        }
        session_manager.set_metadata(session_id, final_metadata)

        logger.info(
            f"CSV processing completed for session {session_id}: "
            f"{total_books} total, {books_added} added, {books_existing} existing, {books_failed} failed"
        )

        return {
            "status": "completed",
            "books_processed": total_books,
            "books_added": books_added,
            "books_existing": books_existing,
            "books_failed": books_failed,
            "error": None
        }

    except Exception as e:
        logger.error(f"Critical error processing CSV for session {session_id}: {e}", exc_info=True)
        session_manager.set_csv_status(session_id, "failed")
        session_manager.set_metadata(session_id, {
            "error": str(e)
        })

        return {
            "status": "failed",
            "books_processed": 0,
            "books_added": 0,
            "books_existing": 0,
            "books_failed": 0,
            "error": str(e)
        }

    finally:
        db.close()
        # Clean up uploaded file
        if csv_path.exists():
            try:
                csv_path.unlink()
                logger.info(f"Deleted temporary CSV file: {csv_path}")
            except Exception as e:
                logger.warning(f"Failed to delete CSV file {csv_path}: {e}")
