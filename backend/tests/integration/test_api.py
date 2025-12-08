"""Comprehensive Test Suite for Leaf Backend

This test suite validates:
1. Infrastructure (Database, Redis, Langfuse)
2. Direct LLM integration with Langfuse tracking
3. End-to-end API flow with CSV upload (Session + CSV → CSV Processing → Follow-up Answers → Recommendations → Feedback)

"""

import sys
import time
from pathlib import Path

# Add backend directory to Python path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from langfuse.decorators import langfuse_context, observe
from langfuse.openai import OpenAI

from app.config import get_settings
from app.core.langfuse_client import langfuse

settings = get_settings()
BASE_URL = "http://localhost:8000"


# =============================================================================
# Test 1: Infrastructure Validation
# =============================================================================


def test_infrastructure():
    """Validate database, Redis, and basic connectivity."""
    print("\n" + "=" * 70)
    print("TEST 1: Infrastructure Validation")
    print("=" * 70)

    # Test root endpoint
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200, "Root endpoint failed"
    print("✓ Root endpoint responding")

    # Test database
    response = requests.get(f"{BASE_URL}/test/db")
    assert response.status_code == 200, "Database connection failed"
    data = response.json()
    assert data.get("pgvector_installed"), "pgvector not installed"
    assert "books" in data.get("tables", []), "Books table not found"
    print(f"✓ Database connected (pgvector {data.get('pgvector_version')})")
    print(f"  Tables: {', '.join(data.get('tables', []))}")

    # Test Redis
    response = requests.get(f"{BASE_URL}/test/redis")
    assert response.status_code == 200, "Redis connection failed"
    data = response.json()
    assert data.get("status") == "connected", "Redis not connected"
    print(f"✓ Redis connected (version {data.get('redis_version')})")

    print("\n✅ Infrastructure: ALL PASSED")


# =============================================================================
# Test 2: Direct Langfuse Integration
# =============================================================================


@observe()
def test_embedding():
    """Test embedding call with Langfuse tracking."""
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input="Hello, this is a test embedding for Langfuse tracking",
    )

    embedding = response.data[0].embedding
    print(f"  ✓ Embedding created (dimension: {len(embedding)})")
    assert len(embedding) == 1536, "Embedding dimension should be 1536"


@observe()
def test_chat_completion():
    """Test chat completion with Langfuse tracking."""
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Say 'Langfuse tracking works!' in one sentence.",
            },
        ],
        temperature=0.7,
    )

    message = response.choices[0].message.content
    print(f"  ✓ Chat completion: {message}")
    assert message is not None and len(message) > 0, "Chat completion should return a message"


@observe(name="langfuse_integration_test")
def test_langfuse_integration():
    """Test direct Langfuse integration with OpenAI calls."""
    print("\n" + "=" * 70)
    print("TEST 2: Langfuse Integration")
    print("=" * 70)

    print("\nTesting embedding call...")
    test_embedding()

    print("\nTesting chat completion...")
    test_chat_completion()

    trace_id = langfuse_context.get_current_trace_id()
    trace_url = f"{settings.langfuse_base_url}/trace/{trace_id}"

    print("\n✅ Langfuse Integration: PASSED")
    print(f"  Trace ID: {trace_id}")
    print(f"  Trace URL: {trace_url}")

    assert trace_id is not None, "Trace ID should be generated"


# =============================================================================
# Test 3: End-to-End API Flow
# =============================================================================


def test_api_flow():
    """Test complete recommendation flow via API with CSV upload."""
    print("\n" + "=" * 70)
    print("TEST 3: End-to-End API Flow (with CSV)")
    print("=" * 70)

    initial_query = "I love dark fantasy"
    question_1 = "Books with complex world-building and political intrigue"
    question_2 = "Character-driven narratives with moral ambiguity"
    question_3 = "Prefer darker, mature themes over YA dystopian"

    # Step 1: Create session with CSV upload
    print("\n1️⃣  Creating session with CSV upload...")

    csv_file_path = Path(__file__).parent.parent.parent / "data" / "goodreads_library_test.csv"
    assert csv_file_path.exists(), f"CSV file not found: {csv_file_path}"

    with open(csv_file_path, 'rb') as csv_file:
        session_response = requests.post(
            f"{BASE_URL}/api/sessions/create",
            data={
                "initial_query": initial_query
            },
            files={
                "csv_file": ("goodreads_library_test.csv", csv_file, "text/csv")
            }
        )

    assert session_response.status_code == 200, f"Failed to create session: {session_response.text}"

    session_data = session_response.json()
    session_id = session_data.get("session_id")
    assert session_id is not None, f"No session_id in response: {session_data}"

    print(f"  ✓ Session created: {session_id}")
    print(f"  ✓ Status: {session_data.get('status', 'unknown')}")
    print(f"  ✓ Follow-up questions: {len(session_data.get('follow_up_questions', []))} questions")
    print(f"  ✓ CSV uploaded: goodreads_library_test.csv")

    # Verify status is "processing_csv" (CSV uploaded)
    current_status = session_data.get('status')
    assert current_status == 'processing_csv', f"Expected status 'processing_csv', got '{current_status}'"

    # Step 1.5: Wait for CSV processing to complete
    print("\n1️⃣.5️⃣  Waiting for CSV processing...")
    max_attempts = 60  # 60 attempts * 2 seconds = 2 minutes max
    attempt = 0

    while attempt < max_attempts:
        status_response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/status")
        assert status_response.status_code == 200, f"Failed to get status: {status_response.text}"

        status_data = status_response.json()
        current_status = status_data.get('csv_status')  # Changed from 'status' to 'csv_status'

        if current_status is None:
            print(f"  ⚠ Warning: No csv_status in response: {status_data}")
            attempt += 1
            time.sleep(2)
            continue

        if current_status in ['completed', 'ready']:
            books_processed = status_data.get('books_processed', 0)
            books_total = status_data.get('books_total', 0)
            new_books_added = status_data.get('new_books_added', 0)
            print(f"  ✓ CSV processing completed! (status: {current_status})")
            print(f"  ✓ Processed {books_processed}/{books_total} books ({new_books_added} new)")
            break
        elif current_status == 'failed':
            error_msg = status_data.get('error', 'Unknown error')
            assert False, f"CSV processing failed: {error_msg}"

        attempt += 1
        time.sleep(2)  # Wait 2 seconds between polls

        if attempt % 5 == 0:  # Progress indicator every 10 seconds
            print(f"  ⏳ Still processing (csv_status: {current_status})... ({attempt * 2}s elapsed)")

    assert current_status in ['completed', 'ready'], f"CSV processing did not complete within timeout. csv_status: {current_status}"

    # Step 2: Submit follow-up answers
    print("\n2️⃣  Submitting follow-up answers...")
    answers_response = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/answers",
        json={
            "answers": {
                "question_1": question_1,
                "question_2": question_2,
                "question_3": question_3
            }
        },
    )

    assert answers_response.status_code == 200, f"Failed to submit answers: {answers_response.text}"

    answers_data = answers_response.json()
    print(f"  ✓ Answers submitted:")
    print(f"  Query: {initial_query}")
    print(f"    1. {question_1}")
    print(f"    2. {question_2}")
    print(f"    3. {question_3}")
    print(f"  ✓ Status: {answers_data.get('status', 'unknown')}")

    # Display CSV books info if available
    csv_books_count = answers_data.get('csv_books_count')
    if csv_books_count:
        print(f"  ✓ CSV books: {csv_books_count} books from user's reading history")
    else:
        print(f"  ℹ No CSV uploaded - using query-based recommendations only")

    # Step 3: Get recommendations
    print("\n3️⃣  Generating recommendations...")
    rec_response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/recommendations")

    assert rec_response.status_code == 200, f"Failed to get recommendations: {rec_response.text}"

    rec_data = rec_response.json()
    recommendations = rec_data.get("recommendations", [])
    trace_id = rec_data.get("trace_id")
    trace_url = rec_data.get("trace_url")

    print(f"  ✓ Received {len(recommendations)} recommendations")
    print(f"  ✓ Trace ID: {trace_id}")
    print(f"  ✓ Trace URL: {trace_url}")

    # Validate recommendations
    assert len(recommendations) > 0, "Should receive at least one recommendation"
    assert trace_id is not None, "Trace ID should be present"

    # Display recommendations
    print("\n📚 Recommendations:")
    for rec in recommendations:
        book = rec.get('book', {})
        rank = rec.get('rank', '?')
        print(f"\n  [{rank}] {book.get('title', 'Unknown')}")
        print(f"      Author: {book.get('author', 'Unknown')}")
        print(f"      ISBN: {book.get('isbn', 'N/A')}")

        # Display rich metadata if available
        if book.get('categories'):
            print(f"      Categories: {', '.join(book['categories'][:3])}")
        if book.get('publication_year'):
            print(f"      Published: {book['publication_year']}")
        if book.get('average_rating'):
            print(f"      Rating: {book.get('average_rating')} ({book.get('ratings_count', 0)} ratings)")

        confidence = rec.get('confidence_score', 'N/A')
        explanation = rec.get('explanation', 'No explanation')
        print(f"      Confidence: {confidence}")
        print(f"      Explanation: {explanation[:150]}...")

    # Step 4: Submit feedback
    if recommendations:
        first_rec_id = recommendations[0].get("id")
        assert first_rec_id is not None, "First recommendation has no ID"
        print("\n4️⃣  Submitting feedback...")

        # Retry mechanism to handle race condition (DB commit happens after API response)
        max_retries = 3
        retry_delay = 0.5  # 500ms between retries
        feedback_submitted = False

        for attempt in range(max_retries):
            if attempt > 0:
                print(f"  ⏳ Retrying feedback submission (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)

            feedback_response = requests.post(
                f"{BASE_URL}/api/recommendations/{first_rec_id}/feedback",
                json={"feedback_type": "dislike"},
            )

            if feedback_response.status_code == 200:
                feedback_data = feedback_response.json()
                print(f"  ✓ Feedback submitted (Score ID: {feedback_data.get('langfuse_score_id')})")
                feedback_submitted = True
                break
            elif feedback_response.status_code == 404 and attempt < max_retries - 1:
                # Recommendation not found yet (DB not committed), retry
                continue
            else:
                # Other error or final attempt failed
                assert False, f"Failed to submit feedback: {feedback_response.text}"

        assert feedback_submitted, "Failed to submit feedback after all retries"

    print("\n✅ API Flow: PASSED")


# =============================================================================
# Main Test Runner
# =============================================================================


def main():
    """
    Run all tests in sequence when executed as a script.

    Note: When using pytest, this function is not called.
    Pytest will automatically discover and run test_* functions.
    """
    print("\n" + "🚀" * 35)
    print("LEAF BACKEND - COMPREHENSIVE TEST SUITE")
    print("🚀" * 35)

    start_time = time.time()

    try:
        # Run tests
        test_infrastructure()
        test_langfuse_integration()
        test_api_flow()

        # Flush Langfuse to ensure all data is sent
        print("\n" + "=" * 70)
        print("Flushing Langfuse data...")
        langfuse.flush()
        print("✓ Langfuse data flushed")

        # Summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"ALL TESTS PASSED (in {elapsed:.2f}s)")

        print("\n🎉 ALL TESTS PASSED!")
        print("\n" + "=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print(f"1. Check Langfuse dashboard: {settings.langfuse_base_url}/project")
        print("2. Verify traces match expected structure (see docstring above)")
        print("3. Check that generations show token usage and costs")
        print("4. Verify feedback score is linked to recommendation trace")
        print("=" * 70)

    except AssertionError as e:
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"❌ TEST FAILED (after {elapsed:.2f}s)")
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"❌ ERROR (after {elapsed:.2f}s)")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
