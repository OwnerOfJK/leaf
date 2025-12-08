"""Tests for enhanced LLM context building."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch
import json
from app.models.database import Book
from app.services.recommendation_engine import _generate_with_llm


def test_includes_user_favorites_in_context():
    """LLM context includes user's high-rated books."""
    user_books = [
        {"book_id": 1, "title": "The Hobbit", "author": "Tolkien", "user_rating": 5},
        {"book_id": 2, "title": "1984", "author": "Orwell", "user_rating": 4},
        {"book_id": 3, "title": "Bad Book", "author": "Bad Author", "user_rating": 2},
    ]

    candidate = Book(id=100, isbn="1000000000", title="Test", author="Author")

    with patch('app.services.recommendation_engine.openai_client.chat.completions.create') as mock_llm:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"book_id": 100, "confidence_score": 95, "explanation": "Great match!"}
        ])
        mock_llm.return_value = mock_response

        # Execute
        result = _generate_with_llm(
            query="fantasy adventure",
            candidate_books=[candidate],
            user_books=user_books,
        )

        # Verify LLM was called
        assert mock_llm.called

        # Extract the user_prompt from the call
        call_args = mock_llm.call_args
        messages = call_args.kwargs['messages']
        user_prompt = messages[1]['content']

        # Verify favorites are in context
        assert "The Hobbit" in user_prompt
        assert "Tolkien" in user_prompt
        assert "5★" in user_prompt or "5 stars" in user_prompt

        assert "1984" in user_prompt
        assert "Orwell" in user_prompt
        assert "4★" in user_prompt or "4 stars" in user_prompt

        # Verify result structure
        assert len(result) == 1
        assert result[0]['book_id'] == 100
        assert result[0]['confidence_score'] == 95
        assert result[0]['explanation'] == "Great match!"
        assert result[0]['rank'] == 1

        print("✓ User favorites included in LLM context")
        print(f"✓ Result: Book {result[0]['book_id']}, Score: {result[0]['confidence_score']}, Rank: {result[0]['rank']}")


def test_includes_user_dislikes_in_context():
    """LLM context includes user's low-rated books."""
    user_books = [
        {"book_id": 1, "title": "Good Book", "author": "Good Author", "user_rating": 5},
        {"book_id": 2, "title": "Bad Book 1", "author": "Bad Author 1", "user_rating": 1},
        {"book_id": 3, "title": "Bad Book 2", "author": "Bad Author 2", "user_rating": 2},
    ]

    candidate = Book(id=100, isbn="1000000000", title="Test", author="Author")

    with patch('app.services.recommendation_engine.openai_client.chat.completions.create') as mock_llm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"book_id": 100, "confidence_score": 95, "explanation": "Great match!"}
        ])
        mock_llm.return_value = mock_response

        result = _generate_with_llm(
            query="any query",
            candidate_books=[candidate],
            user_books=user_books,
        )

        # Extract user_prompt
        call_args = mock_llm.call_args
        messages = call_args.kwargs['messages']
        user_prompt = messages[1]['content']

        # Verify dislikes are in context
        assert "Bad Book 1" in user_prompt or "disliked" in user_prompt.lower()
        assert "Bad Book 2" in user_prompt or "disliked" in user_prompt.lower()

        # Verify result structure
        assert len(result) == 1
        assert result[0]['book_id'] == 100
        assert result[0]['rank'] == 1

        print("✓ User dislikes included in LLM context")
        print(f"✓ Result: Book {result[0]['book_id']}, Explanation: '{result[0]['explanation']}'")


def test_includes_rating_distribution():
    """LLM context includes rating distribution."""
    user_books = [
        {"book_id": 1, "title": "Book 1", "author": "Author 1", "user_rating": 5},
        {"book_id": 2, "title": "Book 2", "author": "Author 2", "user_rating": 5},
        {"book_id": 3, "title": "Book 3", "author": "Author 3", "user_rating": 4},
        {"book_id": 4, "title": "Book 4", "author": "Author 4", "user_rating": 3},
        {"book_id": 5, "title": "Book 5", "author": "Author 5", "user_rating": 1},
    ]

    candidate = Book(id=100, isbn="1000000000", title="Test", author="Author")

    with patch('app.services.recommendation_engine.openai_client.chat.completions.create') as mock_llm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"book_id": 100, "confidence_score": 95, "explanation": "Great match!"}
        ])
        mock_llm.return_value = mock_response

        result = _generate_with_llm(
            query="any query",
            candidate_books=[candidate],
            user_books=user_books,
        )

        # Extract user_prompt
        call_args = mock_llm.call_args
        messages = call_args.kwargs['messages']
        user_prompt = messages[1]['content']

        # Verify rating distribution is in context
        assert "5★: 2" in user_prompt or "5 stars: 2" in user_prompt
        assert "4★: 1" in user_prompt or "4 stars: 1" in user_prompt
        assert "3★: 1" in user_prompt or "3 stars: 1" in user_prompt
        assert "1★: 1" in user_prompt or "1 stars: 1" in user_prompt

        # Verify result structure
        assert len(result) == 1
        assert result[0]['confidence_score'] == 95

        print("✓ Rating distribution included in LLM context")
        print(f"✓ Result: Confidence: {result[0]['confidence_score']}, Book: {result[0]['book_id']}")


def test_enhanced_system_prompt():
    """System prompt instructs LLM to use user preferences."""
    user_books = [
        {"book_id": 1, "title": "Book", "author": "Author", "user_rating": 5},
    ]

    candidate = Book(id=100, isbn="1000000000", title="Test", author="Author")

    with patch('app.services.recommendation_engine.openai_client.chat.completions.create') as mock_llm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"book_id": 100, "confidence_score": 95, "explanation": "Great match!"}
        ])
        mock_llm.return_value = mock_response

        result = _generate_with_llm(
            query="any query",
            candidate_books=[candidate],
            user_books=user_books,
        )

        # Extract system_prompt
        call_args = mock_llm.call_args
        messages = call_args.kwargs['messages']
        system_prompt = messages[0]['content']

        # Verify enhanced instructions
        assert "reading history" in system_prompt.lower()
        assert "loved" in system_prompt.lower() or "high ratings" in system_prompt.lower()
        assert "disliked" in system_prompt.lower() or "low ratings" in system_prompt.lower()
        assert "preferences" in system_prompt.lower()

        # Verify result
        assert len(result) == 1
        assert 'book_id' in result[0]
        assert 'explanation' in result[0]

        print("✓ System prompt enhanced with preference instructions")
        print(f"✓ Result contains required fields: book_id={result[0]['book_id']}, has explanation={len(result[0]['explanation']) > 0}")


def test_works_without_user_books():
    """Function still works when no user books provided."""
    candidate = Book(id=100, isbn="1000000000", title="Test", author="Author")

    with patch('app.services.recommendation_engine.openai_client.chat.completions.create') as mock_llm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"book_id": 100, "confidence_score": 95, "explanation": "Great match!"}
        ])
        mock_llm.return_value = mock_response

        result = _generate_with_llm(
            query="any query",
            candidate_books=[candidate],
            user_books=None,
        )

        # Should complete without error
        assert len(result) == 1
        assert result[0]['book_id'] == 100

        print("✓ Works correctly without user books")


def main():
    """Run all LLM context tests."""
    print("\n" + "=" * 70)
    print("ENHANCED LLM CONTEXT TESTS")
    print("=" * 70 + "\n")

    try:
        test_includes_user_favorites_in_context()
        test_includes_user_dislikes_in_context()
        test_includes_rating_distribution()
        test_enhanced_system_prompt()
        test_works_without_user_books()

        print("\n" + "=" * 70)
        print("✅ ALL LLM CONTEXT TESTS PASSED")
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
