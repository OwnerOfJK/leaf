"""Tests for dislike penalty system."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
from app.constants import DISLIKE_PENALTY, DISLIKE_SIMILARITY_THRESHOLD
from app.models.database import Book
from app.services.recommendation_engine import _apply_dislike_penalties


def test_penalizes_candidates_similar_to_dislikes():
    """Candidates similar to disliked books get penalized."""
    db = MagicMock()

    # Disliked book
    disliked_book = Book(
        id=999,
        isbn="9999999999",
        title="Disliked Book",
        author="Bad Author",
    )
    disliked_book.embedding = [0.8] * 768 + [0.1] * 768

    # Candidate very similar to disliked book
    similar_candidate = Book(
        id=1,
        isbn="1111111111",
        title="Similar Book",
        author="Author 1",
    )
    similar_candidate.embedding = [0.8] * 768 + [0.1] * 768  # Same embedding
    similar_candidate.similarity = 0.9

    # Candidate not similar to disliked book
    dissimilar_candidate = Book(
        id=2,
        isbn="2222222222",
        title="Different Book",
        author="Author 2",
    )
    dissimilar_candidate.embedding = [0.1] * 768 + [0.8] * 768  # Opposite
    dissimilar_candidate.similarity = 0.8

    db.query.return_value.filter.return_value.all.return_value = [disliked_book]

    user_books = [
        {"book_id": 999, "title": "Disliked Book", "author": "Bad Author", "user_rating": 1},
    ]

    candidates = [similar_candidate, dissimilar_candidate]

    # Apply penalties
    result = _apply_dislike_penalties(
        db=db,
        candidates=candidates,
        user_books=user_books,
    )

    # Find candidates in result
    similar_result = next(c for c in result if c.id == 1)
    dissimilar_result = next(c for c in result if c.id == 2)

    # Verify similar candidate was penalized
    assert hasattr(similar_result, 'penalized_due_to_dislike')
    assert similar_result.penalized_due_to_dislike is True
    assert similar_result.similarity == 0.9 * DISLIKE_PENALTY
    assert similar_result.original_similarity_before_penalty == 0.9

    # Verify dissimilar candidate was NOT penalized
    assert not hasattr(dissimilar_result, 'penalized_due_to_dislike')
    assert dissimilar_result.similarity == 0.8  # Unchanged

    print(f"✓ Similar candidate penalized: {0.9} → {0.9 * DISLIKE_PENALTY}")
    print(f"✓ Dissimilar candidate unaffected: {0.8}")


def test_no_penalties_when_no_dislikes():
    """No penalties applied when user has no disliked books."""
    db = MagicMock()

    candidate = Book(id=1, isbn="1111111111", title="Book 1", author="Author 1")
    candidate.embedding = [0.8] * 768 + [0.1] * 768
    candidate.similarity = 0.9

    # User books: all rated 3 or higher
    user_books = [
        {"book_id": 100, "title": "Good Book", "author": "Author", "user_rating": 4},
    ]

    candidates = [candidate]

    result = _apply_dislike_penalties(
        db=db,
        candidates=candidates,
        user_books=user_books,
    )

    # Verify no penalties applied
    assert len(result) == 1
    result_candidate = result[0]
    assert not hasattr(result_candidate, 'penalized_due_to_dislike')
    assert result_candidate.similarity == 0.9  # Unchanged

    print("✓ No penalties when user has no dislikes (all rated ≥3)")


def test_no_penalties_when_no_user_books():
    """No penalties applied when no user books provided."""
    db = MagicMock()

    candidate = Book(id=1, isbn="1111111111", title="Book 1", author="Author 1")
    candidate.embedding = [0.8] * 768 + [0.1] * 768
    candidate.similarity = 0.9

    candidates = [candidate]

    result = _apply_dislike_penalties(
        db=db,
        candidates=candidates,
        user_books=None,
    )

    # Verify no penalties applied
    assert len(result) == 1
    result_candidate = result[0]
    assert not hasattr(result_candidate, 'penalized_due_to_dislike')
    assert result_candidate.similarity == 0.9  # Unchanged

    print("✓ No penalties when no user books provided")


def test_reranks_after_penalties():
    """Candidates are re-sorted after penalties applied."""
    db = MagicMock()

    disliked_book = Book(id=999, isbn="9999999999", title="Disliked", author="Bad")
    disliked_book.embedding = [0.8] * 768 + [0.1] * 768

    # High similarity candidate (similar to dislike)
    high_sim_candidate = Book(id=1, isbn="1111111111", title="High Sim", author="Author 1")
    high_sim_candidate.embedding = [0.8] * 768 + [0.1] * 768
    high_sim_candidate.similarity = 0.95  # Will be penalized to 0.475

    # Medium similarity candidate (not similar to dislike)
    med_sim_candidate = Book(id=2, isbn="2222222222", title="Med Sim", author="Author 2")
    med_sim_candidate.embedding = [0.1] * 768 + [0.8] * 768
    med_sim_candidate.similarity = 0.70  # Stays 0.70

    db.query.return_value.filter.return_value.all.return_value = [disliked_book]

    user_books = [
        {"book_id": 999, "title": "Disliked", "author": "Bad", "user_rating": 1},
    ]

    candidates = [high_sim_candidate, med_sim_candidate]

    result = _apply_dislike_penalties(
        db=db,
        candidates=candidates,
        user_books=user_books,
    )

    # After penalties: high_sim=0.475, med_sim=0.70
    # Result should be re-sorted with med_sim first
    assert result[0].id == 2, "Medium sim candidate should rank first after penalty"
    assert result[1].id == 1, "High sim candidate should rank second after penalty"

    print(f"✓ Re-ranked after penalties:")
    print(f"  - Before: [high_sim=0.95, med_sim=0.70]")
    print(f"  - After:  [med_sim=0.70, high_sim=0.475]")


def test_handles_books_without_embeddings():
    """Books without embeddings are skipped gracefully."""
    db = MagicMock()

    # Disliked book without embedding
    disliked_book = Book(id=999, isbn="9999999999", title="Disliked", author="Bad")
    disliked_book.embedding = None

    # Candidate with embedding
    candidate = Book(id=1, isbn="1111111111", title="Candidate", author="Author 1")
    candidate.embedding = [0.8] * 768 + [0.1] * 768
    candidate.similarity = 0.9

    db.query.return_value.filter.return_value.all.return_value = [disliked_book]

    user_books = [
        {"book_id": 999, "title": "Disliked", "author": "Bad", "user_rating": 1},
    ]

    candidates = [candidate]

    result = _apply_dislike_penalties(
        db=db,
        candidates=candidates,
        user_books=user_books,
    )

    # Verify no penalties applied (disliked book has no embedding)
    assert len(result) == 1
    result_candidate = result[0]
    assert not hasattr(result_candidate, 'penalized_due_to_dislike')
    assert result_candidate.similarity == 0.9  # Unchanged

    print("✓ Disliked books without embeddings are skipped")


def test_penalizes_only_once_per_candidate():
    """Candidate is only penalized once even if similar to multiple dislikes."""
    db = MagicMock()

    # Two disliked books with same embedding
    disliked_book_1 = Book(id=998, isbn="9999999998", title="Disliked 1", author="Bad 1")
    disliked_book_1.embedding = [0.8] * 768 + [0.1] * 768

    disliked_book_2 = Book(id=999, isbn="9999999999", title="Disliked 2", author="Bad 2")
    disliked_book_2.embedding = [0.8] * 768 + [0.1] * 768

    # Candidate similar to both
    candidate = Book(id=1, isbn="1111111111", title="Candidate", author="Author 1")
    candidate.embedding = [0.8] * 768 + [0.1] * 768
    candidate.similarity = 0.9

    db.query.return_value.filter.return_value.all.return_value = [disliked_book_1, disliked_book_2]

    user_books = [
        {"book_id": 998, "title": "Disliked 1", "author": "Bad 1", "user_rating": 1},
        {"book_id": 999, "title": "Disliked 2", "author": "Bad 2", "user_rating": 2},
    ]

    candidates = [candidate]

    result = _apply_dislike_penalties(
        db=db,
        candidates=candidates,
        user_books=user_books,
    )

    # Verify penalty applied only once
    assert len(result) == 1
    result_candidate = result[0]
    expected_score = 0.9 * DISLIKE_PENALTY
    assert result_candidate.similarity == expected_score, f"Expected {expected_score}, got {result_candidate.similarity}"
    assert result_candidate.original_similarity_before_penalty == 0.9

    print(f"✓ Candidate penalized only once despite 2 similar dislikes")
    print(f"  - Original: 0.9")
    print(f"  - After penalty: {expected_score}")


def main():
    """Run all dislike penalty tests."""
    print("\n" + "=" * 70)
    print("DISLIKE PENALTY SYSTEM TESTS")
    print("=" * 70 + "\n")

    try:
        test_penalizes_candidates_similar_to_dislikes()
        test_no_penalties_when_no_dislikes()
        test_no_penalties_when_no_user_books()
        test_reranks_after_penalties()
        test_handles_books_without_embeddings()
        test_penalizes_only_once_per_candidate()

        print("\n" + "=" * 70)
        print("✅ ALL DISLIKE PENALTY TESTS PASSED")
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
