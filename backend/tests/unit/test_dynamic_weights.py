"""Tests for dynamic collaborative filtering weights."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch
from app.constants import MIN_RELEVANT_BOOKS
from app.models.database import Book
from app.services.recommendation_engine import _retrieve_candidates


def test_uses_collaborative_when_enough_relevant_books():
    """User has ≥2 relevant high-rated books → collaborative filtering is used."""
    db = MagicMock()

    # Create fantasy books (relevant to query)
    fantasy_book_1 = Book(id=1, isbn="1111111111", title="Fantasy 1", author="Author 1")
    fantasy_book_1.embedding = [0.8] * 768 + [0.1] * 768

    fantasy_book_2 = Book(id=2, isbn="2222222222", title="Fantasy 2", author="Author 2")
    fantasy_book_2.embedding = [0.75] * 768 + [0.15] * 768

    # Mock database query for books
    db.query.return_value.filter.return_value.all.return_value = [fantasy_book_1, fantasy_book_2]

    # User books: 2 high-rated fantasy books
    user_books = [
        {"book_id": 1, "title": "Fantasy 1", "author": "Author 1", "user_rating": 5},
        {"book_id": 2, "title": "Fantasy 2", "author": "Author 2", "user_rating": 5},
    ]

    # Mock embedding creation
    with patch('app.services.recommendation_engine.create_embedding') as mock_embedding:
        mock_embedding.return_value = [0.8] * 768 + [0.1] * 768

        # Mock vector search functions
        with patch('app.services.recommendation_engine.vector_search.search_similar_to_books') as mock_collab:
            with patch('app.services.recommendation_engine.vector_search.search_similar_books') as mock_query:
                # Setup mock returns
                mock_collab_book = Book(id=100, isbn="1000000000", title="Collab Book", author="Collab Author")
                mock_collab_book.similarity = 0.9
                mock_collab.return_value = [mock_collab_book]

                mock_query_book = Book(id=200, isbn="2000000000", title="Query Book", author="Query Author")
                mock_query_book.similarity = 0.8
                mock_query.return_value = [mock_query_book]

                # Execute
                candidates = _retrieve_candidates(
                    db=db,
                    query="fantasy with magic",
                    user_books=user_books,
                    top_k=60,
                )

                # Verify collaborative filtering was called
                assert mock_collab.called, "Collaborative filtering should be called when ≥2 relevant books"
                assert mock_collab.call_count == 1

                # Verify it was called with the relevant book IDs
                call_args = mock_collab.call_args
                book_ids_used = call_args.kwargs['book_ids']
                assert len(book_ids_used) >= MIN_RELEVANT_BOOKS

                # Verify candidates include both collaborative and query results
                assert len(candidates) == 2, f"Expected 2 candidates, got {len(candidates)}"
                candidate_ids = [c.id for c in candidates]
                assert 100 in candidate_ids, "Collaborative book should be in candidates"
                assert 200 in candidate_ids, "Query book should be in candidates"

                print(f"✓ Collaborative filtering used with {len(book_ids_used)} relevant books")
                print(f"✓ Candidates include both collaborative (ID=100) and query (ID=200) results")


def test_skips_collaborative_when_insufficient_relevant_books():
    """User has <2 relevant high-rated books → collaborative filtering is skipped."""
    db = MagicMock()

    # Create one fantasy book and one coding book
    fantasy_book = Book(id=1, isbn="1111111111", title="Fantasy Book", author="Author 1")
    fantasy_book.embedding = [0.8] * 768 + [0.1] * 768

    coding_book = Book(id=2, isbn="2222222222", title="Coding Book", author="Author 2")
    coding_book.embedding = [0.1] * 768 + [0.8] * 768  # Opposite direction

    db.query.return_value.filter.return_value.all.return_value = [fantasy_book, coding_book]

    # User books: 1 fantasy book, 1 coding book (both high-rated)
    user_books = [
        {"book_id": 1, "title": "Fantasy Book", "author": "Author 1", "user_rating": 5},
        {"book_id": 2, "title": "Coding Book", "author": "Author 2", "user_rating": 5},
    ]

    with patch('app.services.recommendation_engine.create_embedding') as mock_embedding:
        # Fantasy query embedding
        mock_embedding.return_value = [0.8] * 768 + [0.1] * 768

        with patch('app.services.recommendation_engine.vector_search.search_similar_to_books') as mock_collab:
            with patch('app.services.recommendation_engine.vector_search.search_similar_books') as mock_query:
                mock_query_book = Book(id=200, isbn="2000000000", title="Query Book", author="Query Author")
                mock_query_book.similarity = 0.8
                mock_query.return_value = [mock_query_book]

                # Execute
                candidates = _retrieve_candidates(
                    db=db,
                    query="fantasy with magic",
                    user_books=user_books,
                    top_k=60,
                )

                # Verify collaborative filtering was NOT called
                assert not mock_collab.called, "Collaborative filtering should be skipped when <2 relevant books"

                # Verify candidates only include query results (no collaborative)
                assert len(candidates) == 1, f"Expected 1 candidate, got {len(candidates)}"
                assert candidates[0].id == 200, "Only query book should be in candidates"

                print("✓ Collaborative filtering skipped (only 1 relevant book out of 2)")
                print("✓ Candidates only include query search results (ID=200)")


def test_skips_collaborative_when_no_high_rated_books():
    """User has no high-rated books → collaborative filtering is skipped."""
    db = MagicMock()

    # User books: all rated 3 stars or lower
    user_books = [
        {"book_id": 1, "title": "Book 1", "author": "Author 1", "user_rating": 3},
        {"book_id": 2, "title": "Book 2", "author": "Author 2", "user_rating": 2},
    ]

    with patch('app.services.recommendation_engine.create_embedding') as mock_embedding:
        mock_embedding.return_value = [0.8] * 768 + [0.1] * 768

        with patch('app.services.recommendation_engine.vector_search.search_similar_to_books') as mock_collab:
            with patch('app.services.recommendation_engine.vector_search.search_similar_books') as mock_query:
                mock_query_book = Book(id=200, isbn="2000000000", title="Query Book", author="Query Author")
                mock_query_book.similarity = 0.8
                mock_query.return_value = [mock_query_book]

                # Execute
                candidates = _retrieve_candidates(
                    db=db,
                    query="any query",
                    user_books=user_books,
                    top_k=60,
                )

                # Verify collaborative filtering was NOT called
                assert not mock_collab.called, "Collaborative filtering should be skipped when no high-rated books"

                # Verify candidates only include query results
                assert len(candidates) == 1, f"Expected 1 candidate, got {len(candidates)}"
                assert candidates[0].id == 200, "Only query book should be in candidates"

                print("✓ Collaborative filtering skipped (no books rated ≥4 stars)")
                print("✓ Candidates only include query search results (ID=200)")


def test_all_relevant_books_used_in_collaborative():
    """All relevant high-rated books are used for collaborative filtering."""
    db = MagicMock()

    # Create 3 fantasy books
    fantasy_books = []
    for i in range(1, 4):
        book = Book(id=i, isbn=f"{i}" * 10, title=f"Fantasy {i}", author=f"Author {i}")
        book.embedding = [0.8] * 768 + [0.1] * 768
        fantasy_books.append(book)

    db.query.return_value.filter.return_value.all.return_value = fantasy_books

    user_books = [
        {"book_id": i, "title": f"Fantasy {i}", "author": f"Author {i}", "user_rating": 5}
        for i in range(1, 4)
    ]

    with patch('app.services.recommendation_engine.create_embedding') as mock_embedding:
        mock_embedding.return_value = [0.8] * 768 + [0.1] * 768

        with patch('app.services.recommendation_engine.vector_search.search_similar_to_books') as mock_collab:
            with patch('app.services.recommendation_engine.vector_search.search_similar_books') as mock_query:
                mock_collab_book = Book(id=100, isbn="1000000000", title="Collab Book", author="Collab Author")
                mock_collab_book.similarity = 0.9
                mock_collab.return_value = [mock_collab_book]

                mock_query_book = Book(id=200, isbn="2000000000", title="Query Book", author="Query Author")
                mock_query_book.similarity = 0.8
                mock_query.return_value = [mock_query_book]

                # Execute
                candidates = _retrieve_candidates(
                    db=db,
                    query="fantasy with magic",
                    user_books=user_books,
                    top_k=60,
                )

                # Verify all 3 books were used
                call_args = mock_collab.call_args
                book_ids_used = call_args.kwargs['book_ids']
                assert len(book_ids_used) == 3, f"Expected 3 books used, got {len(book_ids_used)}"
                assert set(book_ids_used) == {1, 2, 3}

                # Verify candidates include both collaborative and query results
                assert len(candidates) == 2, f"Expected 2 candidates, got {len(candidates)}"
                candidate_ids = [c.id for c in candidates]
                assert 100 in candidate_ids, "Collaborative book should be in candidates"
                assert 200 in candidate_ids, "Query book should be in candidates"

                print(f"✓ All 3 relevant books used for collaborative filtering")
                print(f"✓ Candidates include both collaborative (ID=100) and query (ID=200) results")


def main():
    """Run all dynamic collaborative weight tests."""
    print("\n" + "=" * 70)
    print("DYNAMIC COLLABORATIVE FILTERING TESTS")
    print("=" * 70 + "\n")

    try:
        test_uses_collaborative_when_enough_relevant_books()
        test_skips_collaborative_when_insufficient_relevant_books()
        test_skips_collaborative_when_no_high_rated_books()
        test_all_relevant_books_used_in_collaborative()

        print("\n" + "=" * 70)
        print("✅ ALL DYNAMIC COLLABORATIVE FILTERING TESTS PASSED")
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
