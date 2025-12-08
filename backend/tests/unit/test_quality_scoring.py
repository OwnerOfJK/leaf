"""Tests for quality scoring system."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import Book
from app.services.recommendation_engine import _calculate_quality_score, _apply_quality_scoring


def test_quality_score_full_metadata():
    """Book with complete metadata gets high score (0.9-1.0)."""
    book = Book(
        id=1,
        isbn="1234567890",
        title="Test Book",
        author="Test Author",
        description="A" * 150,  # Long description (>100 chars)
        categories=["Fiction", "Fantasy", "Adventure"],  # 3 categories (>2)
        page_count=350,
        publisher="Test Publisher",
        ratings_count=500,  # >100 ratings
        average_rating=4.5,
    )

    score = _calculate_quality_score(book)
    print(f"Full metadata score: {score}")

    # Expected: 0.5 (desc) + 0.2 (cats) + 0.2 (ratings) + 0.05 (pages) + 0.05 (pub) = 1.0
    assert score == 1.0, f"Expected 1.0, got {score}"
    print("✓ Full metadata book scores 1.0")


def test_quality_score_sparse_metadata():
    """Book with minimal metadata gets low score (0.2-0.4)."""
    book = Book(
        id=2,
        isbn="0987654321",
        title="Sparse Book",
        author="Unknown Author",
        description="Short",  # Short description (<100 chars)
        categories=["Fiction"],  # 1 category
        page_count=None,
        publisher=None,
        ratings_count=5,  # <10 ratings
        average_rating=3.0,
    )

    score = _calculate_quality_score(book)
    print(f"Sparse metadata score: {score}")

    # Expected: 0.2 (desc) + 0.1 (cat) = 0.3
    assert abs(score - 0.3) < 0.001, f"Expected ~0.3, got {score}"
    print("✓ Sparse metadata book scores 0.3")


def test_quality_score_no_metadata():
    """Book with no optional metadata gets minimum score."""
    book = Book(
        id=3,
        isbn="1111111111",
        title="No Metadata Book",
        author="Anonymous",
        description=None,
        categories=None,
        page_count=None,
        publisher=None,
        ratings_count=None,
        average_rating=None,
    )

    score = _calculate_quality_score(book)
    print(f"No metadata score: {score}")

    # Expected: 0.0 (nothing)
    assert score == 0.0, f"Expected 0.0, got {score}"
    print("✓ No metadata book scores 0.0")


def test_quality_scoring_reranks_candidates():
    """Quality scoring promotes high-quality books over sparse ones."""
    # Create two books with different quality levels
    high_quality = Book(
        id=1,
        isbn="1111111111",
        title="High Quality Book",
        author="Good Author",
        description="A" * 200,
        categories=["Fiction", "Fantasy"],
        page_count=400,
        publisher="Big Publisher",
        ratings_count=1000,
        average_rating=4.8,
    )
    high_quality.similarity = 0.70  # Lower similarity

    low_quality = Book(
        id=2,
        isbn="2222222222",
        title="Low Quality Book",
        author="Unknown",
        description=None,
        categories=None,
        page_count=None,
        publisher=None,
        ratings_count=None,
        average_rating=None,
    )
    low_quality.similarity = 0.85  # Higher similarity

    candidates = [low_quality, high_quality]

    # Apply quality scoring
    scored = _apply_quality_scoring(candidates)

    print(f"\nBefore quality scoring:")
    print(f"  Low quality: similarity={0.85}")
    print(f"  High quality: similarity={0.70}")

    print(f"\nAfter quality scoring:")
    print(f"  Low quality: similarity={scored[1].similarity:.3f}, quality={scored[1].quality_score:.2f}")
    print(f"  High quality: similarity={scored[0].similarity:.3f}, quality={scored[0].quality_score:.2f}")

    # High quality should now rank first despite lower initial similarity
    # High: 0.70 * 1.0 = 0.70
    # Low:  0.85 * 0.0 = 0.0
    assert scored[0].id == 1, "High quality book should rank first"
    assert scored[1].id == 2, "Low quality book should rank second"

    print("✓ Quality scoring successfully re-ranks candidates")


def test_quality_score_edge_cases():
    """Test edge cases in quality scoring."""

    # Description exactly 100 chars (should count as short)
    book_100 = Book(
        id=1,
        isbn="1111111111",
        title="Test",
        author="Test",
        description="A" * 100,
    )
    score_100 = _calculate_quality_score(book_100)
    # Should get short desc score (0.2)
    assert abs(score_100 - 0.2) < 0.001, f"100-char description should score ~0.2, got {score_100}"

    # Description 101 chars (should count as long)
    book_101 = Book(
        id=2,
        isbn="2222222222",
        title="Test",
        author="Test",
        description="A" * 101,
    )
    score_101 = _calculate_quality_score(book_101)
    # Should get long desc score (0.5)
    assert abs(score_101 - 0.5) < 0.001, f"101-char description should score ~0.5, got {score_101}"

    # Ratings count exactly 10 (should count as medium)
    book_10_ratings = Book(
        id=3,
        isbn="3333333333",
        title="Test",
        author="Test",
        ratings_count=10,
    )
    score_10 = _calculate_quality_score(book_10_ratings)
    # Should not get rating points (need >10)
    assert score_10 == 0.0, f"10 ratings should score 0.0, got {score_10}"

    # Ratings count 11 (should count as medium)
    book_11_ratings = Book(
        id=4,
        isbn="4444444444",
        title="Test",
        author="Test",
        ratings_count=11,
    )
    score_11 = _calculate_quality_score(book_11_ratings)
    # Should get medium rating points (0.1)
    assert abs(score_11 - 0.1) < 0.001, f"11 ratings should score ~0.1, got {score_11}"

    print("✓ Edge cases handled correctly")


def main():
    """Run all quality scoring tests."""
    print("\n" + "=" * 70)
    print("QUALITY SCORING TESTS")
    print("=" * 70 + "\n")

    try:
        test_quality_score_full_metadata()
        test_quality_score_sparse_metadata()
        test_quality_score_no_metadata()
        test_quality_scoring_reranks_candidates()
        test_quality_score_edge_cases()

        print("\n" + "=" * 70)
        print("✅ ALL QUALITY SCORING TESTS PASSED")
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
