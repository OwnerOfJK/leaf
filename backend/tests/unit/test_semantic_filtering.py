"""Tests for semantic filtering of user favorites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
from app.models.database import Book
from app.services.recommendation_engine import _filter_relevant_books


def test_filter_relevant_fantasy_books():
    """User asks for fantasy, has fantasy 5★ books → should pass filter."""
    # Mock database session
    db = MagicMock()

    # Create fantasy books with embeddings (similar direction to query)
    fantasy_book_1 = Book(
        id=1,
        isbn="1111111111",
        title="The Name of the Wind",
        author="Patrick Rothfuss",
        categories=["Fantasy"],
    )
    # Fantasy embedding: high values in first half, low in second half
    fantasy_book_1.embedding = [0.8] * 768 + [0.1] * 768

    fantasy_book_2 = Book(
        id=2,
        isbn="2222222222",
        title="Mistborn",
        author="Brandon Sanderson",
        categories=["Fantasy"],
    )
    fantasy_book_2.embedding = [0.75] * 768 + [0.15] * 768

    # Mock query.filter().all() to return fantasy books
    db.query.return_value.filter.return_value.all.return_value = [fantasy_book_1, fantasy_book_2]

    # User books list
    user_books = [
        {"book_id": 1, "title": "The Name of the Wind", "author": "Patrick Rothfuss", "user_rating": 5},
        {"book_id": 2, "title": "Mistborn", "author": "Brandon Sanderson", "user_rating": 5},
    ]

    # Query embedding for "fantasy with magic" (similar pattern to fantasy books)
    query_embedding = [0.8] * 768 + [0.1] * 768

    # Filter relevant books
    relevant = _filter_relevant_books(
        db=db,
        query_embedding=query_embedding,
        user_books=user_books,
        similarity_threshold=0.4,
    )

    print(f"✓ Fantasy query matched {len(relevant)}/2 fantasy books")
    assert len(relevant) == 2, f"Expected 2 relevant books, got {len(relevant)}"
    assert relevant[0]['book_id'] == 1
    assert relevant[1]['book_id'] == 2


def test_filter_excludes_unrelated_books():
    """User asks for fantasy, has coding 5★ books → should fail filter."""
    # Mock database session
    db = MagicMock()

    # Create coding books with embeddings (opposite direction to fantasy query)
    coding_book_1 = Book(
        id=101,
        isbn="1010101010",
        title="Clean Code",
        author="Robert Martin",
        categories=["Programming"],
    )
    # Coding embedding: low values in first half, high in second half (opposite of fantasy)
    coding_book_1.embedding = [0.1] * 768 + [0.8] * 768

    coding_book_2 = Book(
        id=102,
        isbn="2020202020",
        title="Design Patterns",
        author="Gang of Four",
        categories=["Programming"],
    )
    coding_book_2.embedding = [0.15] * 768 + [0.75] * 768

    db.query.return_value.filter.return_value.all.return_value = [coding_book_1, coding_book_2]

    user_books = [
        {"book_id": 101, "title": "Clean Code", "author": "Robert Martin", "user_rating": 5},
        {"book_id": 102, "title": "Design Patterns", "author": "Gang of Four", "user_rating": 5},
    ]

    # Query embedding for "fantasy with magic" (high first half, low second half)
    query_embedding = [0.8] * 768 + [0.1] * 768

    # Filter relevant books
    relevant = _filter_relevant_books(
        db=db,
        query_embedding=query_embedding,
        user_books=user_books,
        similarity_threshold=0.4,
    )

    print(f"✓ Fantasy query matched {len(relevant)}/2 coding books (correctly excluded)")
    assert len(relevant) == 0, f"Expected 0 relevant books, got {len(relevant)}"


def test_filter_returns_empty_when_no_matches():
    """No books above threshold → returns empty list."""
    db = MagicMock()

    # Create book with low similarity (opposite direction to query)
    unrelated_book = Book(
        id=1,
        isbn="1111111111",
        title="Unrelated Book",
        author="Someone",
    )
    unrelated_book.embedding = [0.1] * 768 + [0.9] * 768  # Opposite direction

    db.query.return_value.filter.return_value.all.return_value = [unrelated_book]

    user_books = [
        {"book_id": 1, "title": "Unrelated Book", "author": "Someone", "user_rating": 5},
    ]

    query_embedding = [0.9] * 768 + [0.1] * 768  # High first half, low second half

    relevant = _filter_relevant_books(
        db=db,
        query_embedding=query_embedding,
        user_books=user_books,
        similarity_threshold=0.4,
    )

    print(f"✓ No books above threshold → empty list returned")
    assert len(relevant) == 0


def test_filter_preserves_user_rating():
    """Filtered books preserve user_rating field."""
    db = MagicMock()

    book = Book(
        id=1,
        isbn="1111111111",
        title="Test Book",
        author="Test Author",
    )
    book.embedding = [0.8] * 768 + [0.1] * 768

    db.query.return_value.filter.return_value.all.return_value = [book]

    user_books = [
        {"book_id": 1, "title": "Test Book", "author": "Test Author", "user_rating": 4},
    ]

    query_embedding = [0.8] * 768 + [0.1] * 768

    relevant = _filter_relevant_books(
        db=db,
        query_embedding=query_embedding,
        user_books=user_books,
        similarity_threshold=0.4,
    )

    print(f"✓ User rating preserved: {relevant[0]['user_rating']}")
    assert len(relevant) == 1
    assert relevant[0]['user_rating'] == 4


def test_filter_handles_books_without_embeddings():
    """Books without embeddings are skipped gracefully."""
    db = MagicMock()

    book_with_embedding = Book(
        id=1,
        isbn="1111111111",
        title="Book With Embedding",
        author="Author 1",
    )
    book_with_embedding.embedding = [0.8] * 768 + [0.1] * 768

    book_without_embedding = Book(
        id=2,
        isbn="2222222222",
        title="Book Without Embedding",
        author="Author 2",
    )
    book_without_embedding.embedding = None  # No embedding

    db.query.return_value.filter.return_value.all.return_value = [
        book_with_embedding,
        book_without_embedding
    ]

    user_books = [
        {"book_id": 1, "title": "Book With Embedding", "author": "Author 1", "user_rating": 5},
        {"book_id": 2, "title": "Book Without Embedding", "author": "Author 2", "user_rating": 5},
    ]

    query_embedding = [0.8] * 768 + [0.1] * 768

    relevant = _filter_relevant_books(
        db=db,
        query_embedding=query_embedding,
        user_books=user_books,
        similarity_threshold=0.4,
    )

    print(f"✓ Books without embeddings skipped: {len(relevant)}/2 returned")
    assert len(relevant) == 1  # Only book with embedding
    assert relevant[0]['book_id'] == 1


def main():
    """Run all semantic filtering tests."""
    print("\n" + "=" * 70)
    print("SEMANTIC FILTERING TESTS")
    print("=" * 70 + "\n")

    try:
        test_filter_relevant_fantasy_books()
        test_filter_excludes_unrelated_books()
        test_filter_returns_empty_when_no_matches()
        test_filter_preserves_user_rating()
        test_filter_handles_books_without_embeddings()

        print("\n" + "=" * 70)
        print("✅ ALL SEMANTIC FILTERING TESTS PASSED")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
