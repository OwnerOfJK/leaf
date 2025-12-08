"""Vector similarity search using pgvector."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import Book


def search_similar_books(
    db: Session,
    embedding: list[float],
    limit: int = 10,
    exclude_ids: list[int] | None = None,
) -> list[Book]:
    """Find books similar to a query embedding using cosine similarity.

    Args:
        db: Database session
        embedding: 1536-dimensional query embedding vector
        limit: Maximum number of results to return
        exclude_ids: Optional list of book IDs to exclude from results

    Returns:
        List of Book instances ordered by similarity (most similar first)
        Each book has a 'similarity' attribute (0.0-1.0, higher is more similar)
    """
    # Select book and similarity score (1 - cosine_distance)
    stmt = (
        select(
            Book,
            (1 - Book.embedding.cosine_distance(embedding)).label('similarity')
        )
        .order_by(Book.embedding.cosine_distance(embedding))
        .limit(limit)
    )

    if exclude_ids:
        stmt = stmt.where(Book.id.notin_(exclude_ids))

    results = db.execute(stmt).all()

    # Attach similarity as attribute to each book
    books = []
    for book, similarity in results:
        book.similarity = float(similarity)
        books.append(book)

    return books


def search_similar_to_books(
    db: Session,
    book_ids: list[int],
    limit: int = 10,
    exclude_ids: list[int] | None = None,
) -> list[Book]:
    """Find books similar to a set of existing books.

    Calculates average embedding of input books and searches for similar books.
    Useful for "users who liked these books also liked..." recommendations.

    Args:
        db: Database session
        book_ids: List of book IDs to base similarity search on
        limit: Maximum number of results to return
        exclude_ids: Optional list of book IDs to exclude (typically the input books themselves)

    Returns:
        List of Book instances ordered by similarity to the input books
    """
    # Fetch the input books
    books_stmt = select(Book).where(Book.id.in_(book_ids))
    books = list(db.scalars(books_stmt).all())

    if not books:
        return []

    # Calculate average embedding
    avg_embedding = [
        sum(book.embedding[i] for book in books if book.embedding is not None) / len(books)
        for i in range(1536)
    ]

    # Search using the average embedding
    return search_similar_books(
        db=db,
        embedding=avg_embedding,
        limit=limit,
        exclude_ids=exclude_ids or book_ids,
    )
