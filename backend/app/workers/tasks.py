"""Celery tasks for async processing."""

import logging
from pathlib import Path

from sqlalchemy import or_

from app.constants import CSV_PROGRESS_UPDATE_INTERVAL, MAX_DESCRIPTION_LENGTH
from app.core.database import SessionLocal
from app.core.embeddings import create_embedding, format_book_text
from app.core.redis_client import session_manager
from app.models.database import Book
from app.services.google_books_api import fetch_from_google_books
from app.utils.csv_processor import parse_goodreads_csv, validate_csv_file
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks.process_csv_upload", bind=True)
def process_csv_upload(self, session_id: str, file_path: str) -> dict:
    """Process uploaded Goodreads CSV file asynchronously.

    This task:
    1. Parses the CSV file
    2. For each book:
       - Checks if it exists in PostgreSQL
       - If not, fetches metadata from Google Books API
       - Generates embedding
       - Inserts into database
    3. Updates Redis session with user's book IDs and ratings
    4. Updates CSV processing status

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

    try:
        # Update status to processing
        session_manager.set_csv_status(session_id, "processing")
        logger.info(f"Starting CSV processing for session {session_id}")

        # Validate CSV file
        validate_csv_file(csv_path)

        # Parse CSV
        books_from_csv = parse_goodreads_csv(csv_path)
        total_books = len(books_from_csv)
        logger.info(f"Parsed {total_books} books from CSV")

        books_added = 0
        books_existing = 0
        books_failed = 0
        user_books = []  # List of {book_id, title, author, user_rating}

        # Process each book
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

                # Check if book exists in database (by ISBN or ISBN13)
                existing_book = db.query(Book).filter(
                    or_(
                        Book.isbn == book_data["isbn"] if book_data["isbn"] else False,
                        Book.isbn13 == book_data["isbn13"] if book_data["isbn13"] else False,
                        Book.isbn == book_data["isbn13"] if book_data["isbn13"] else False,
                        Book.isbn13 == book_data["isbn"] if book_data["isbn"] else False,
                    )
                ).first()

                if existing_book:
                    # Book already exists
                    books_existing += 1
                    user_books.append({
                        "book_id": existing_book.id,
                        "title": existing_book.title,
                        "author": existing_book.author,
                        "user_rating": book_data["user_rating"]
                    })
                    logger.debug(f"Book exists: {existing_book.title} (ID: {existing_book.id})")
                    continue

                # Book doesn't exist - fetch from Google Books API
                # Try ISBN first, then ISBN13
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

                # Generate embedding for the book
                embedding_text = format_book_text(
                    title=google_data["title"],
                    author=google_data["author"],
                    description=description
                )
                embedding = create_embedding(embedding_text)

                # Create new book record
                new_book = Book(
                    isbn=google_data["isbn"],
                    isbn13=google_data["isbn13"],
                    title=google_data["title"],
                    author=google_data["author"],
                    description=description,
                    categories=google_data.get("categories"),
                    page_count=google_data.get("page_count"),
                    publisher=google_data.get("publisher"),
                    publication_year=google_data.get("publication_year"),
                    language=google_data.get("language"),
                    average_rating=google_data.get("average_rating"),
                    ratings_count=google_data.get("ratings_count"),
                    cover_url=google_data.get("cover_url"),
                    embedding=embedding,
                    data_source="google_books"
                )

                db.add(new_book)
                db.flush()  # Get the book ID without committing
                books_added += 1

                user_books.append({
                    "book_id": new_book.id,
                    "title": new_book.title,
                    "author": new_book.author,
                    "user_rating": book_data["user_rating"]
                })

                logger.info(
                    f"Added new book: {new_book.title} (ID: {new_book.id}) "
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
