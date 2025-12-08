"""Recommendation engine with RAG pipeline and Langfuse tracing."""

import json
from decimal import Decimal

from langfuse.decorators import observe
from langfuse.openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.embeddings import create_embedding, format_book_text
from app.models.database import Book, Recommendation
from app.services import book_service, vector_search

settings = get_settings()
# Initialize OpenAI client with Langfuse wrapper for automatic tracking
openai_client = OpenAI(api_key=settings.openai_api_key)

LLM_MODEL = "gpt-4o-mini"


@observe()
def generate_recommendations(
    db: Session,
    session_id: str,
    query: str,
    user_book_ids: list[int] | None = None,
    follow_up_answers: dict | None = None,
) -> tuple[list[Recommendation], str]:
    """Generate personalized book recommendations using RAG pipeline.

    Pipeline steps:
    1. Query understanding: Combine query + follow-up answers
    2. Retrieval: Vector search using user books + general search
    3. Generation: LLM ranks and selects top 3 with explanations
    4. Storage: Save to PostgreSQL with trace_id

    Args:
        db: Database session
        session_id: Session identifier
        query: User's initial query
        user_book_ids: Optional list of user's book IDs from CSV
        follow_up_answers: Optional dictionary of follow-up answers

    Returns:
        Tuple of (list of Recommendation objects, trace_id)
    """
    # Step 1: Build enhanced query
    enhanced_query = _build_enhanced_query(query, follow_up_answers)

    # Step 2: Retrieve candidate books
    candidate_books = _retrieve_candidates(
        db=db,
        query=enhanced_query,
        user_book_ids=user_book_ids,
    )

    if not candidate_books:
        raise ValueError("No candidate books found")

    # Step 3: Generate recommendations using LLM
    recommendations_data = _generate_with_llm(
        query=enhanced_query,
        candidate_books=candidate_books,
        user_book_ids=user_book_ids,
    )

    # Step 4: Store recommendations in database
    recommendations = _store_recommendations(
        db=db,
        session_id=session_id,
        recommendations_data=recommendations_data,
    )

    # Get trace_id from Langfuse context
    from langfuse.decorators import langfuse_context

    trace_id = langfuse_context.get_current_trace_id()

    return recommendations, trace_id


@observe()
def _build_enhanced_query(query: str, follow_up_answers: dict | None = None) -> str:
    """Combine initial query with follow-up answers.

    Args:
        query: User's initial query
        follow_up_answers: Optional follow-up answers

    Returns:
        Enhanced query string
    """
    if not follow_up_answers:
        return query

    # Combine query with answers
    parts = [query]
    for key, value in follow_up_answers.items():
        if value:
            parts.append(f"{key}: {value}")

    return " ".join(parts)


@observe()
def _retrieve_candidates(
    db: Session,
    query: str,
    user_book_ids: list[int] | None = None,
    top_k: int = 60,
) -> list[Book]:
    """Retrieve candidate books using vector search.

    Combines:
    - Books similar to user's reading history (if provided)
    - Books matching the query embedding

    Args:
        db: Database session
        query: Enhanced query string
        user_book_ids: Optional user book IDs
        top_k: Total candidates to return

    Returns:
        List of candidate Book objects
    """
    # Create query embedding
    query_embedding = create_embedding(query)

    candidates = []
    exclude_ids = user_book_ids or []

    # If user has books, get similar books
    if user_book_ids:
        user_similar = vector_search.search_similar_to_books(
            db=db,
            book_ids=user_book_ids,
            limit=10,
            exclude_ids=exclude_ids,
        )
        candidates.extend(user_similar)
        exclude_ids.extend([book.id for book in user_similar])

    # General search based on query
    query_similar = vector_search.search_similar_books(
        db=db,
        embedding=query_embedding,
        limit=top_k - len(candidates),
        exclude_ids=exclude_ids,
    )
    candidates.extend(query_similar)

    return candidates[:top_k]


@observe()
def _generate_with_llm(
    query: str,
    candidate_books: list[Book],
    user_book_ids: list[int] | None = None,
) -> list[dict]:
    """Use LLM to select top 3 recommendations with explanations.

    Args:
        query: User's query
        candidate_books: Candidate books from retrieval
        user_book_ids: Optional user book IDs for context

    Returns:
        List of dicts with book_id, confidence_score, explanation, rank
    """
    # Build user context
    context = f"User query: {query}\n\n"
    if user_book_ids:
        context += f"User has read {len(user_book_ids)} books.\n\n"

    # Format candidate books
    candidates_text = "Candidate books:\n"
    for i, book in enumerate(candidate_books, 1):
        candidates_text += f"{i}. [{book.id}] {book.title} by {book.author}\n"
        if book.description:
            desc = book.description[:200] + "..." if len(book.description) > 200 else book.description
            candidates_text += f"   Description: {desc}\n"
        if book.categories:
            candidates_text += f"   Categories: {', '.join(book.categories[:3])}\n"
        candidates_text += "\n"

    # LLM prompt
    system_prompt = """You are a book recommendation expert. Given a user's query and a list of candidate books, select the top 3 most relevant recommendations.

For each recommendation, provide:
1. The book ID from the candidate list
2. A confidence score (0-100) indicating how well it matches the user's needs
3. A concise explanation (2-3 sentences) of why this book is recommended

Return your response as a JSON array with exactly 3 recommendations, ordered by relevance (best first)."""

    user_prompt = f"""{context}{candidates_text}

Select the top 3 books that best match the user's query. Return as JSON array:
[
  {{"book_id": <id>, "confidence_score": <0-100>, "explanation": "<why this book>"}},
  ...
]"""

    # Call LLM
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    # Parse response with error handling
    try:
        result = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        raise ValueError(f"Failed to parse LLM response: {e}")

    # Handle both array and object with "recommendations" key
    recommendations = result if isinstance(result, list) else result.get("recommendations", [])

    if not recommendations:
        raise ValueError("LLM returned empty recommendations")

    # Validate recommendation structure
    for rec in recommendations[:3]:
        if "book_id" not in rec or "confidence_score" not in rec or "explanation" not in rec:
            raise ValueError(f"Invalid recommendation structure: {rec}")

    # Add rank to each recommendation
    for i, rec in enumerate(recommendations[:3], 1):
        rec["rank"] = i

    return recommendations[:3]


@observe()
def _store_recommendations(
    db: Session,
    session_id: str,
    recommendations_data: list[dict],
) -> list[Recommendation]:
    """Store recommendations in PostgreSQL.

    Args:
        db: Database session
        session_id: Session identifier
        recommendations_data: List of recommendation dicts from LLM

    Returns:
        List of created Recommendation objects
    """
    from langfuse.decorators import langfuse_context

    trace_id = langfuse_context.get_current_trace_id()

    recommendations = []
    for rec_data in recommendations_data:
        recommendation = Recommendation(
            session_id=session_id,
            book_id=rec_data["book_id"],
            confidence_score=Decimal(str(rec_data["confidence_score"])),
            explanation=rec_data["explanation"],
            rank=rec_data["rank"],
            trace_id=trace_id,
        )
        db.add(recommendation)
        recommendations.append(recommendation)

    db.flush()
    return recommendations
