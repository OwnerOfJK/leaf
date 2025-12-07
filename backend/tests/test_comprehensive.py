"""Comprehensive Test Suite for Leaf Backend

This test suite validates:
1. Infrastructure (Database, Redis, Langfuse)
2. Direct LLM integration with Langfuse tracking
3. End-to-end API flow (Session → Recommendations → Feedback)

EXPECTED LANGFUSE TRACES:
========================

After running this test, you should see the following traces in your Langfuse dashboard
(https://cloud.langfuse.com/project):

TRACE 1: "langfuse_integration_test"
├── test_embedding
│   └── GENERATION: embeddings.create (text-embedding-3-small)
│       - Input: "Hello, this is a test embedding..."
│       - Output: 1536-dim vector
│       - Tokens: ~15 input
└── test_chat_completion
    └── GENERATION: chat.completions.create (gpt-4o-mini)
        - Input: System + User message
        - Output: "Langfuse tracking works!"
        - Tokens: ~20 input, ~10 output

TRACE 2: "generate_recommendations"
├── _build_enhanced_query
│   - Combines user query with follow-up answers
├── _retrieve_candidates
│   ├── create_embedding
│   │   └── GENERATION: embeddings.create (text-embedding-3-small)
│   │       - Input: Enhanced query text
│   │       - Tokens: ~30 input
│   └── Vector search (pgvector - not traced)
├── _generate_with_llm
│   └── GENERATION: chat.completions.create (gpt-4o-mini)
│       - Input: Candidate books + user context
│       - Output: Top 3 recommendations with explanations
│       - Tokens: ~1000 input, ~300 output
└── _store_recommendations
    - Saves to PostgreSQL with trace_id

TRACE 3: Feedback Submission (if applicable)
└── SCORE: user_feedback
    - Value: 1.0 (like) or 0.0 (dislike)
    - Linked to TRACE 2 via trace_id

Total Expected Traces: 2-3
Total Expected Generations: 4-5
Total Expected Scores: 1 (if feedback submitted)

PREREQUISITES:
==============
1. Database seeded with books: python scripts/seed_books.py
2. Infrastructure running: docker-compose up -d postgres redis
3. Backend server running: uvicorn main:app --reload
4. Environment variables configured in .env

"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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

    try:
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
        return True

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to backend server!")
        print("   Make sure server is running: uvicorn main:app --reload")
        return False
    except AssertionError as e:
        print(f"\n❌ Infrastructure test failed: {e}")
        return False


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
    return embedding


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
    return message


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

    return trace_id


# =============================================================================
# Test 3: End-to-End API Flow
# =============================================================================


def test_api_flow():
    """Test complete recommendation flow via API."""
    print("\n" + "=" * 70)
    print("TEST 3: End-to-End API Flow")
    print("=" * 70)

    # Step 1: Create session
    print("\n1️⃣  Creating session...")
    session_response = requests.post(
        f"{BASE_URL}/api/sessions/create",
        json={
            "initial_query": "I love dystopian science fiction with strong protagonists"
        },
    )

    if session_response.status_code != 200:
        print(f"❌ Failed to create session: {session_response.text}")
        return False

    session_data = session_response.json()
    session_id = session_data["session_id"]
    print(f"  ✓ Session created: {session_id}")
    print(f"  ✓ Status: {session_data['status']}")

    # Step 2: Get recommendations
    print("\n2️⃣  Generating recommendations...")
    rec_response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/recommendations")

    if rec_response.status_code != 200:
        print(f"❌ Failed to get recommendations: {rec_response.text}")
        return False

    rec_data = rec_response.json()
    recommendations = rec_data["recommendations"]
    trace_id = rec_data.get("trace_id")
    trace_url = rec_data.get("trace_url")

    print(f"  ✓ Received {len(recommendations)} recommendations")
    print(f"  ✓ Trace ID: {trace_id}")
    print(f"  ✓ Trace URL: {trace_url}")

    # Display recommendations
    print("\n📚 Recommendations:")
    for rec in recommendations:
        print(f"\n  [{rec['rank']}] {rec['book']['title']}")
        print(f"      Author: {rec['book']['author']}")
        print(f"      Confidence: {rec['confidence_score']}")
        print(f"      Explanation: {rec['explanation'][:100]}...")

    # Step 3: Submit feedback
    if recommendations:
        first_rec_id = recommendations[0]["id"]
        print("\n3️⃣  Submitting feedback...")

        feedback_response = requests.post(
            f"{BASE_URL}/api/recommendations/{first_rec_id}/feedback",
            json={"feedback_type": "dislike"},
        )

        if feedback_response.status_code != 200:
            print(f"❌ Failed to submit feedback: {feedback_response.text}")
            return False

        feedback_data = feedback_response.json()
        print(f"  ✓ Feedback submitted (Score ID: {feedback_data.get('langfuse_score_id')})")

    print("\n✅ API Flow: PASSED")
    return True


# =============================================================================
# Main Test Runner
# =============================================================================


def main():
    """Run all tests in sequence."""
    print("\n" + "🚀" * 35)
    print("LEAF BACKEND - COMPREHENSIVE TEST SUITE")
    print("🚀" * 35)

    start_time = time.time()
    results = {}

    # Run tests
    results["infrastructure"] = test_infrastructure()

    if not results["infrastructure"]:
        print("\n❌ Infrastructure tests failed. Cannot continue.")
        sys.exit(1)

    results["langfuse"] = test_langfuse_integration() is not None
    results["api_flow"] = test_api_flow()

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

    all_passed = all(results.values())
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.upper():.<50} {status}")

    print(f"\nTotal time: {elapsed:.2f}s")

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n" + "=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print(f"1. Check Langfuse dashboard: {settings.langfuse_base_url}/project")
        print("2. Verify traces match expected structure (see docstring above)")
        print("3. Check that generations show token usage and costs")
        print("4. Verify feedback score is linked to recommendation trace")
        print("=" * 70)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
