"""Book service for CRUD operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import Book


def get_book_by_isbn(db: Session, isbn: str) -> Book | None:
    """Retrieve a book by its ISBN.

    Args:
        db: Database session
        isbn: Book ISBN (10 or 13 digits)

    Returns:
        Book instance if found, None otherwise
    """
    stmt = select(Book).where(Book.isbn == isbn)
    return db.scalars(stmt).first()


def get_book_by_id(db: Session, book_id: int) -> Book | None:
    """Retrieve a book by its database ID.

    Args:
        db: Database session
        book_id: Book primary key

    Returns:
        Book instance if found, None otherwise
    """
    stmt = select(Book).where(Book.id == book_id)
    return db.scalars(stmt).first()


def get_books_by_ids(db: Session, book_ids: list[int]) -> list[Book]:
    """Retrieve multiple books by their database IDs.

    Args:
        db: Database session
        book_ids: List of book primary keys

    Returns:
        List of Book instances (may be fewer than requested if some not found)
    """
    stmt = select(Book).where(Book.id.in_(book_ids))
    return list(db.scalars(stmt).all())


def create_book(
    db: Session,
    isbn: str,
    title: str,
    author: str,
    embedding: list[float],
    description: str | None = None,
    categories: list[str] | None = None,
    cover_url: str | None = None,
    isbn13: str | None = None,
    page_count: int | None = None,
    publisher: str | None = None,
    publication_year: int | None = None,
    language: str | None = None,
    average_rating: float | None = None,
    ratings_count: int | None = None,
    data_source: str | None = None,
) -> Book:
    """Create a new book record with embedding and rich metadata.

    Args:
        db: Database session
        isbn: Book ISBN-10 (must be unique)
        title: Book title
        author: Book author
        embedding: 1536-dimensional embedding vector
        description: Book description (optional)
        categories: List of genre/category tags (optional)
        cover_url: URL to book cover image (optional)
        isbn13: Book ISBN-13 (optional)
        page_count: Number of pages (optional)
        publisher: Publisher name (optional)
        publication_year: Year of publication (optional)
        language: Language code (e.g., 'en') (optional)
        average_rating: Global average rating 0-5 (optional)
        ratings_count: Number of ratings (optional)
        data_source: Data source identifier (optional)

    Returns:
        Created Book instance

    Raises:
        IntegrityError: If ISBN already exists
    """
    book = Book(
        isbn=isbn,
        isbn13=isbn13,
        title=title,
        author=author,
        description=description,
        categories=categories,
        page_count=page_count,
        publisher=publisher,
        publication_year=publication_year,
        language=language,
        average_rating=average_rating,
        ratings_count=ratings_count,
        cover_url=cover_url,
        embedding=embedding,
        data_source=data_source,
    )
    db.add(book)
    db.flush()  # Get ID without committing transaction
    return book
