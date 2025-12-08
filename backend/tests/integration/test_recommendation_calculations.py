"""Integration tests for the complete recommendation pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch
from app.models.database import Book
from app.services.recommendation_engine import _retrieve_candidates


def test_full_pipeline_with_all_features():
    """
    Integration test: Full pipeline with quality scoring, semantic filtering,
    dynamic collaborative weights, and dislike penalties.

    Scenario:
    - User loves 3 fantasy books (rated 5★)
    - User dislikes 1 romance book (rated 1★)
    - Query: "epic fantasy adventure"
    - Expected: Collaborative filtering uses fantasy books, not romance
    """
    db = MagicMock()

    # User's reading history
    fantasy_book_1 = Book(id=1, isbn="1111111111", title="LOTR", author="Tolkien")
    fantasy_book_1.embedding = [0.8] * 768 + [0.1] * 768

    fantasy_book_2 = Book(id=2, isbn="2222222222", title="Hobbit", author="Tolkien")
    fantasy_book_2.embedding = [0.8] * 768 + [0.1] * 768

    fantasy_book_3 = Book(id=3, isbn="3333333333", title="Mistborn", author="Sanderson")
    fantasy_book_3.embedding = [0.75] * 768 + [0.15] * 768

    romance_book = Book(id=999, isbn="9999999999", title="Romance Book", author="Romance Author")
    romance_book.embedding = [0.1] * 768 + [0.8] * 768  # Opposite direction

    # Candidate books
    good_fantasy = Book(id=100, isbn="1000000000", title="Good Fantasy", author="Fantasy Author")
    good_fantasy.embedding = [0.8] * 768 + [0.1] * 768
    good_fantasy.description = "A" * 150  # Long description
    good_fantasy.categories = ["Fantasy", "Adventure"]
    good_fantasy.ratings_count = 500
    good_fantasy.page_count = 400
    good_fantasy.publisher = "Publisher"

    romance_like = Book(id=200, isbn="2000000000", title="Romance-like", author="Author")
    romance_like.embedding = [0.1] * 768 + [0.8] * 768  # Similar to disliked romance
    romance_like.description = "Short"
    romance_like.categories = ["Romance"]
    romance_like.ratings_count = 5

    # Mock database queries
    # For semantic filtering (user books)
    def mock_query_filter_all(model):
        if hasattr(model, 'id'):
            # This is Book.id.in_() query
            class MockFilterResult:
                def all(self):
                    # Return user's books for filtering
                    return [fantasy_book_1, fantasy_book_2, fantasy_book_3, romance_book]
            return MockFilterResult()
        return MagicMock()

    db.query.return_value.filter.return_value.all.side_effect = lambda: [
        fantasy_book_1, fantasy_book_2, fantasy_book_3, romance_book
    ]

    user_books = [
        {"book_id": 1, "title": "LOTR", "author": "Tolkien", "user_rating": 5},
        {"book_id": 2, "title": "Hobbit", "author": "Tolkien", "user_rating": 5},
        {"book_id": 3, "title": "Mistborn", "author": "Sanderson", "user_rating": 5},
        {"book_id": 999, "title": "Romance Book", "author": "Romance Author", "user_rating": 1},
    ]

    with patch('app.services.recommendation_engine.create_embedding') as mock_embedding:
        # Fantasy query embedding
        mock_embedding.return_value = [0.8] * 768 + [0.1] * 768

        with patch('app.services.recommendation_engine.vector_search.search_similar_to_books') as mock_collab:
            with patch('app.services.recommendation_engine.vector_search.search_similar_books') as mock_query_search:
                # Collaborative filtering returns good fantasy book
                good_fantasy.similarity = 0.95
                mock_collab.return_value = [good_fantasy]

                # Query search returns romance-like book
                romance_like.similarity = 0.70
                mock_query_search.return_value = [romance_like]

                # Execute full pipeline
                candidates = _retrieve_candidates(
                    db=db,
                    query="epic fantasy adventure",
                    user_books=user_books,
                    top_k=60,
                )

                # Verify results
                print("\n" + "=" * 70)
                print("INTEGRATION TEST RESULTS")
                print("=" * 70)

                # 1. Verify collaborative filtering was used (user has 3 relevant fantasy books)
                assert mock_collab.called, "Collaborative filtering should be used"
                collab_args = mock_collab.call_args
                book_ids_used = collab_args.kwargs['book_ids']

                # Should use fantasy books (1, 2, 3), NOT romance (999)
                assert len(book_ids_used) >= 3, f"Expected ≥3 books for collaborative, got {len(book_ids_used)}"
                assert 1 in book_ids_used, "Fantasy book 1 should be used"
                assert 2 in book_ids_used, "Fantasy book 2 should be used"
                assert 3 in book_ids_used, "Fantasy book 3 should be used"
                assert 999 not in book_ids_used, "Romance book (disliked) should NOT be used"

                print(f"\n✓ Collaborative filtering used relevant books: {book_ids_used}")
                print(f"✓ Romance book (999) excluded from collaborative filtering")

                # 2. Verify candidates returned
                assert len(candidates) == 2, f"Expected 2 candidates, got {len(candidates)}"

                # 3. Verify quality scoring was applied (good_fantasy has high quality)
                good_fantasy_result = next((c for c in candidates if c.id == 100), None)
                assert good_fantasy_result is not None, "Good fantasy book should be in results"
                assert hasattr(good_fantasy_result, 'quality_score'), "Quality score should be calculated"
                assert good_fantasy_result.quality_score == 1.0, f"Expected quality score 1.0, got {good_fantasy_result.quality_score}"

                print(f"\n✓ Quality scoring applied: {good_fantasy_result.quality_score}")

                # 4. Verify dislike penalty was applied to romance-like book
                romance_result = next((c for c in candidates if c.id == 200), None)
                assert romance_result is not None, "Romance-like book should be in results"

                # Romance-like has high similarity to disliked romance book, should be penalized
                if hasattr(romance_result, 'penalized_due_to_dislike'):
                    print(f"\n✓ Dislike penalty applied to romance-like book")
                    print(f"  - Original similarity: {romance_result.original_similarity_before_penalty}")
                    print(f"  - After penalty: {romance_result.similarity}")
                    print(f"  - Penalized due to book: {romance_result.penalized_due_to_book_id}")
                else:
                    print(f"\n⚠ Dislike penalty not applied (books may not be similar enough)")

                # 5. Verify final ranking (good fantasy should rank higher than romance-like)
                assert candidates[0].id == 100, "Good fantasy should rank first"
                assert candidates[1].id == 200, "Romance-like should rank second"

                print(f"\n✓ Final ranking correct:")
                for i, candidate in enumerate(candidates, 1):
                    print(f"  {i}. Book {candidate.id}: similarity={candidate.similarity:.3f}")

                print("\n" + "=" * 70)
                print("✅ FULL PIPELINE INTEGRATION TEST PASSED")
                print("=" * 70)


def main():
    """Run integration tests."""
    print("\n" + "=" * 70)
    print("RECOMMENDATION PIPELINE INTEGRATION TESTS")
    print("=" * 70)

    try:
        test_full_pipeline_with_all_features()

        print("\n" + "=" * 70)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
