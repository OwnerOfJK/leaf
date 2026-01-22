"""Recommendation engine with RAG pipeline and Langfuse tracing."""

import json
from decimal import Decimal

from langfuse import get_client, observe
from langfuse.openai import OpenAI
from scipy.spatial.distance import cosine as cosine_distance
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    CANDIDATE_DESCRIPTION_MAX_LENGTH,
    COLLABORATIVE_FILTERING_LIMIT,
    DEFAULT_TOP_K,
    DISLIKE_PENALTY,
    DISLIKE_SIMILARITY_THRESHOLD,
    DISLIKE_THRESHOLD,
    HIGH_RATING_THRESHOLD,
    LLM_MODEL,
    MAX_DISLIKES_IN_CONTEXT,
    MAX_FAVORITES_IN_CONTEXT,
    MIN_RELEVANT_BOOKS,
    QUALITY_SCORE_WEIGHTS,
    SIMILARITY_THRESHOLD,
)
from app.core.embeddings import create_embedding
from app.models.database import Book, Recommendation
from app.services import vector_search

settings = get_settings()
# Initialize OpenAI client with Langfuse wrapper for automatic tracking
openai_client = OpenAI(api_key=settings.openai_api_key)
langfuse = get_client()


@observe()
def generate_recommendations(
    db: Session,
    session_id: str,
    query: str,
    user_books: list[dict] | None = None,
    follow_up_answers: dict | None = None,
    generated_questions: dict | None = None,
) -> tuple[list[Recommendation], str]:
    """Generate personalized book recommendations using RAG pipeline.

    Pipeline steps:
    1. Query understanding: Combine query + follow-up Q&As
    2. Retrieval: Vector search using user books + general search
    3. Generation: LLM ranks and selects top 3 with explanations
    4. Storage: Save to PostgreSQL with trace_id

    Args:
        db: Database session
        session_id: Session identifier
        query: User's initial query
        user_books: Optional list of {book_id, title, author, user_rating, exclusive_shelf} from CSV
        follow_up_answers: Optional dictionary of follow-up answers
        generated_questions: Optional dictionary of generated questions

    Returns:
        Tuple of (list of Recommendation objects, trace_id)
    """
    # Step 1: Build enhanced query
    enhanced_query = _build_enhanced_query(query, follow_up_answers, generated_questions)

    # Step 2: Retrieve candidate books
    candidate_books = _retrieve_candidates(
        db=db,
        query=enhanced_query,
        user_books=user_books,
    )

    if not candidate_books:
        raise ValueError("No candidate books found")

    # Step 3: Generate recommendations using LLM
    recommendations_data = _generate_with_llm(
        query=enhanced_query,
        candidate_books=candidate_books,
        user_books=user_books,
    )

    # Step 4: Store recommendations in database
    recommendations = _store_recommendations(
        db=db,
        session_id=session_id,
        recommendations_data=recommendations_data,
    )

    trace_id = langfuse.get_current_trace_id()

    return recommendations, trace_id


@observe()
def _build_enhanced_query(
    query: str,
    follow_up_answers: dict | None = None,
    generated_questions: dict | None = None,
) -> str:
    """Combine initial query with follow-up questions and answers.

    Creates a rich context by including both the questions asked and the user's
    answers, preserving the conversational flow.

    Args:
        query: User's initial query
        follow_up_answers: Optional follow-up answers {question_1: answer, ...}
        generated_questions: Optional generated questions {1: question, 2: question, ...}

    Returns:
        Enhanced query string with Q&A pairs
    """
    parts = [f"Initial request: {query}"]

    # If we have questions and answers, format as Q&A pairs
    if follow_up_answers and generated_questions:
        # Iterate through questions in order (1, 2, 3)
        for q_num in sorted(generated_questions.keys()):
            question = generated_questions[q_num]
            answer_key = f"question_{q_num}"
            answer = follow_up_answers.get(answer_key)

            if answer:
                parts.append(f"Q: {question}")
                parts.append(f"A: {answer}")
            # Skip pairs where user didn't answer

    elif follow_up_answers:
        # Fallback: if we don't have questions, just include answers
        for key, value in follow_up_answers.items():
            if value:
                parts.append(f"{key}: {value}")

    return "\n".join(parts)


@observe()
def _retrieve_candidates(
    db: Session,
    query: str,
    user_books: list[dict] | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[Book]:
    """Retrieve candidate books using vector search with dynamic collaborative weights.

    Strategy:
    - If user has ≥2 relevant high-rated books: use collaborative filtering
    - If user has <2 relevant high-rated books: skip collaborative, rely on query search
    - Always apply quality scoring to re-rank candidates

    Prevents unrelated books from dominating recommendations when user's query
    diverges from their reading history.

    Args:
        db: Database session
        query: Enhanced query string
        user_books: Optional list of {book_id, title, author, user_rating, exclusive_shelf}
        top_k: Total candidates to return

    Returns:
        List of candidate Book objects
    """
    # Create query embedding
    query_embedding = create_embedding(query)

    candidates = []
    exclude_ids = []

    # Dynamic collaborative filtering based on semantic relevance
    if user_books:
        # Only exclude books that have been read, not books marked as to-read or currently-reading
        exclude_ids = [b['book_id'] for b in user_books if b.get('exclusive_shelf') == 'read']



        # Filter high-rated books (4-5 stars) that have been read by semantic relevance to query
        # Only use read books for collaborative filtering (not to-read or currently-reading)
        high_rated_books = [
            b for b in user_books
            if b['user_rating'] >= HIGH_RATING_THRESHOLD and b.get('exclusive_shelf') == 'read'
        ]

        if high_rated_books:
            relevant_books = _filter_relevant_books(
                db=db,
                query_embedding=query_embedding,
                user_books=high_rated_books,
                similarity_threshold=SIMILARITY_THRESHOLD,
            )

            # Only use collaborative filtering if we have enough relevant signal
            if len(relevant_books) >= MIN_RELEVANT_BOOKS:
                # Use collaborative filtering based on relevant books only
                relevant_ids = [b['book_id'] for b in relevant_books]
                user_similar = vector_search.search_similar_to_books(
                    db=db,
                    book_ids=relevant_ids,
                    limit=COLLABORATIVE_FILTERING_LIMIT,
                    exclude_ids=exclude_ids,
                )
                candidates.extend(user_similar)
                exclude_ids.extend([book.id for book in user_similar])

    # General search based on query (fills remaining slots)
    query_similar = vector_search.search_similar_books(
        db=db,
        embedding=query_embedding,
        limit=top_k - len(candidates),
        exclude_ids=exclude_ids,
    )
    candidates.extend(query_similar)

    # Apply quality scoring to re-rank candidates
    candidates = _apply_quality_scoring(candidates)

    # Apply dislike penalties
    candidates = _apply_dislike_penalties(db, candidates, user_books)

    return candidates[:top_k]


@observe()
def _generate_with_llm(
    query: str,
    candidate_books: list[Book],
    user_books: list[dict] | None = None,
) -> list[dict]:
    """Use LLM to select top 3 recommendations with explanations.

    Args:
        query: User's query
        candidate_books: Candidate books from retrieval
        user_books: Optional list of {book_id, title, author, user_rating, exclusive_shelf} for context

    Returns:
        List of dicts with book_id, confidence_score, explanation, rank
    """
    # Build enhanced user context
    context = f"User query: {query}\n\n"

    if user_books:
        # Extract user preferences (only from read books)
        read_books = [b for b in user_books if b.get('exclusive_shelf') == 'read']
        high_rated = [b for b in read_books if b['user_rating'] >= HIGH_RATING_THRESHOLD]
        low_rated = [b for b in read_books if b['user_rating'] > 0 and b['user_rating'] <= DISLIKE_THRESHOLD]

        context += f"User's reading history: {len(read_books)} books read\n\n"

        # Add favorite books
        if high_rated:
            context += f"Books user loved (rated {HIGH_RATING_THRESHOLD}-5★):\n"
            for book in high_rated[:MAX_FAVORITES_IN_CONTEXT]:
                context += f"  - {book['title']} by {book['author']} ({book['user_rating']}★)\n"
            if len(high_rated) > MAX_FAVORITES_IN_CONTEXT:
                context += f"  ... and {len(high_rated) - MAX_FAVORITES_IN_CONTEXT} more\n"
            context += "\n"

        # Add disliked books
        if low_rated:
            context += f"Books user disliked (rated 1-{DISLIKE_THRESHOLD}★):\n"
            for book in low_rated[:MAX_DISLIKES_IN_CONTEXT]:
                context += f"  - {book['title']} by {book['author']} ({book['user_rating']}★)\n"
            if len(low_rated) > MAX_DISLIKES_IN_CONTEXT:
                context += f"  ... and {len(low_rated) - MAX_DISLIKES_IN_CONTEXT} more\n"
            context += "\n"

        # Add rating distribution (only for read books)
        rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for book in read_books:
            rating = int(book['user_rating'])
            if rating in rating_counts:
                rating_counts[rating] += 1

        context += "Rating distribution:\n"
        context += f"  5★: {rating_counts[5]} | 4★: {rating_counts[4]} | 3★: {rating_counts[3]} | "
        context += f"2★: {rating_counts[2]} | 1★: {rating_counts[1]}\n\n"

    # Format candidate books and build index-to-id mapping
    index_to_book_id: dict[int, int] = {}
    candidates_text = "Candidate books:\n"
    for i, book in enumerate(candidate_books, 1):
        index_to_book_id[i] = book.id
        candidates_text += f"{i}. {book.title} by {book.author}\n"
        if book.description:
            max_len = CANDIDATE_DESCRIPTION_MAX_LENGTH
            desc = book.description[:max_len] + "..." if len(book.description) > max_len else book.description
            candidates_text += f"   Description: {desc}\n"
        if book.categories:
            candidates_text += f"   Categories: {', '.join(book.categories[:3])}\n"
        candidates_text += "\n"

    # LLM prompt
    system_prompt = """You are a book recommendation expert. Given a user's query, their reading history, and a list of candidate books, select the top 3 most relevant recommendations.

Consider the following when making recommendations:
- The user's current query and what they're looking for
- Books they loved (high ratings) - recommend similar themes/authors/styles
- Books they disliked (low ratings) - avoid similar books
- Their overall rating distribution and reading preferences
- Quality and relevance of candidate books to the query

For each recommendation, provide:
1. The book ID from the candidate list
2. A confidence score (0-100) indicating how well it matches the user's needs
3. A concise explanation (2-3 sentences) of why this book is recommended based on their preferences

Return exactly 3 recommendations, ordered by relevance (best first)."""

    user_prompt = f"""{context}{candidates_text}

Select the top 3 books that best match the user's query."""

    # JSON schema for structured outputs
    recommendation_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "book_recommendations",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_number": {
                                    "type": "integer",
                                    "description": "The candidate number (1, 2, 3, etc.) from the list",
                                },
                                "confidence_score": {
                                    "type": "integer",
                                    "description": "How well this book matches the user's needs (0-100)",
                                },
                                "explanation": {
                                    "type": "string",
                                    "description": "2-3 sentence explanation of why this book is recommended",
                                },
                            },
                            "required": ["candidate_number", "confidence_score", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["recommendations"],
                "additionalProperties": False,
            },
        },
    }

    # Call LLM with structured outputs
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        response_format=recommendation_schema,
    )

    # Parse response - structured outputs guarantees valid schema
    try:
        result = json.loads(response.choices[0].message.content)
        recommendations = result["recommendations"]
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        raise ValueError(f"Failed to parse LLM response: {e}")

    if not recommendations:
        raise ValueError("LLM returned empty recommendations")

    # Truncate to top 3 (defensive fallback)
    recommendations = recommendations[:3]

    # Map candidate_number to actual book_id and add rank
    mapped_recommendations = []
    for i, rec in enumerate(recommendations, 1):
        candidate_num = rec["candidate_number"]
        if candidate_num not in index_to_book_id:
            # Skip invalid candidate numbers
            continue
        mapped_recommendations.append({
            "book_id": index_to_book_id[candidate_num],
            "confidence_score": rec["confidence_score"],
            "explanation": rec["explanation"],
            "rank": i,
        })

    if not mapped_recommendations:
        raise ValueError("No valid book IDs found in LLM response")

    return mapped_recommendations


@observe()
def _filter_relevant_books(
    db: Session,
    query_embedding: list[float],
    user_books: list[dict],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Filter user's favorite books by semantic relevance to query.

    This prevents unrelated 5★ books from dominating recommendations.

    Example:
    - User has 20 coding books rated 5★
    - Query: "fantasy with strong magic systems"
    - Result: Only return 5★ fantasy books (if any exist in library)

    Args:
        db: Database session
        query_embedding: Query embedding vector
        user_books: List of {book_id, title, author, user_rating, exclusive_shelf}
        similarity_threshold: Minimum cosine similarity (default 0.3)

    Returns:
        Filtered list of user_books that are contextually relevant
    """
    book_ids = [b['book_id'] for b in user_books]

    # Fetch books with embeddings
    books = db.query(Book).filter(Book.id.in_(book_ids)).all()

    relevant_books = []
    for book in books:
        if book.embedding is None:
            continue

        # Compute cosine similarity between query and book
        similarity = 1 - cosine_distance(query_embedding, book.embedding)

        if similarity >= similarity_threshold:
            # Find original user_book dict to preserve rating
            user_book = next(b for b in user_books if b['book_id'] == book.id)
            relevant_books.append(user_book)

    return relevant_books


@observe()
def _apply_dislike_penalties(
    db: Session,
    candidates: list[Book],
    user_books: list[dict] | None = None,
) -> list[Book]:
    """Penalize candidates similar to user's disliked books.

    Prevents recommending books similar to ones the user rated poorly.

    Example:
    - User rated "Twilight" 1★
    - Candidate "Midnight Sun" has 70% similarity to Twilight
    - Result: Multiply Midnight Sun's similarity by 0.5 (penalty)

    Args:
        db: Database session
        candidates: List of candidate books with similarity scores
        user_books: Optional list of {book_id, title, author, user_rating, exclusive_shelf}

    Returns:
        Candidates with penalties applied and re-sorted
    """
    if not user_books:
        return candidates

    # Get disliked books (rated 1-2 stars) that have been read
    # Exclude books with rating 0 (not rated)
    disliked_books = [
        b for b in user_books
        if b['user_rating'] > 0 and b['user_rating'] <= DISLIKE_THRESHOLD and b.get('exclusive_shelf') == 'read'
    ]

    if not disliked_books:
        return candidates

    # Fetch disliked books with embeddings
    disliked_ids = [b['book_id'] for b in disliked_books]
    disliked_book_objs = db.query(Book).filter(Book.id.in_(disliked_ids)).all()

    # For each candidate, check similarity to disliked books
    books_penalized = 0
    for candidate in candidates:
        if candidate.embedding is None:
            continue

        for disliked_book in disliked_book_objs:
            if disliked_book.embedding is None:
                continue

            similarity = 1 - cosine_distance(candidate.embedding, disliked_book.embedding)

            if similarity >= DISLIKE_SIMILARITY_THRESHOLD:
                # Apply penalty
                if hasattr(candidate, 'similarity'):
                    candidate.original_similarity_before_penalty = candidate.similarity
                    candidate.similarity *= DISLIKE_PENALTY
                    candidate.penalized_due_to_dislike = True
                    candidate.penalized_due_to_book_id = disliked_book.id
                    books_penalized += 1
                break  # Only penalize once per candidate
                
    # Re-sort after penalties
    candidates.sort(key=lambda x: getattr(x, 'similarity', 0), reverse=True)
    return candidates


def _calculate_quality_score(book: Book) -> float:
    """Calculate metadata quality score for a book.

    Returns score from 0.0 (poor metadata) to 1.0 (excellent metadata).

    Components:
    - Description (50%): Long = 0.5, Short = 0.2
    - Categories (20%): 2+ = 0.2, 1 = 0.1
    - Ratings (20%): 100+ = 0.2, 10+ = 0.1
    - Other (10%): page_count + publisher = 0.05 each

    Args:
        book: Book object with metadata

    Returns:
        Quality score between 0.0 and 1.0
    """
    score = 0.0

    # Description (most important for semantic search)
    if book.description and len(book.description) > 100:
        score += QUALITY_SCORE_WEIGHTS["description_long"]
    elif book.description:
        score += QUALITY_SCORE_WEIGHTS["description_short"]

    # Categories (genre/topic signal)
    if book.categories and len(book.categories) >= 2:
        score += QUALITY_SCORE_WEIGHTS["categories_multiple"]
    elif book.categories:
        score += QUALITY_SCORE_WEIGHTS["categories_single"]

    # Ratings (credibility signal)
    if book.ratings_count and book.ratings_count > 100:
        score += QUALITY_SCORE_WEIGHTS["ratings_high"]
    elif book.ratings_count and book.ratings_count > 10:
        score += QUALITY_SCORE_WEIGHTS["ratings_medium"]

    # Additional metadata
    if book.page_count:
        score += QUALITY_SCORE_WEIGHTS["page_count"]
    if book.publisher:
        score += QUALITY_SCORE_WEIGHTS["publisher"]

    return min(score, 1.0)


@observe()
def _apply_quality_scoring(candidates: list[Book]) -> list[Book]:
    """Apply metadata quality scoring and re-rank candidates.

    Quality score adjusts the similarity score to prioritize
    high-quality metadata books.

    Args:
        candidates: List of candidate books with similarity scores

    Returns:
        Re-ranked list with quality-adjusted scores
    """
    for candidate in candidates:
        quality_score = _calculate_quality_score(candidate)

        # Store original similarity for observability
        if hasattr(candidate, 'similarity'):
            candidate.original_similarity = candidate.similarity
            candidate.quality_score = quality_score
            # Adjust similarity by quality
            candidate.similarity = candidate.similarity * quality_score

    # Re-sort by adjusted similarity
    candidates.sort(key=lambda x: getattr(x, 'similarity', 0), reverse=True)
    return candidates


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
