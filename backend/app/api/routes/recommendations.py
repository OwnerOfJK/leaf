"""API routes for recommendations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.core.redis_client import SessionManager, get_session_manager
from app.models.schemas import BookResponse, RecommendationWithBook, RecommendationsResponse
from app.services import book_service
from app.services.recommendation_engine import generate_recommendations

settings = get_settings()
router = APIRouter()


@router.get("/{session_id}/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    session_id: str,
    db: Session = Depends(get_db),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> RecommendationsResponse:
    """Generate and return book recommendations for a session.

    Uses the RAG pipeline to:
    1. Retrieve the user's query and context from Redis
    2. Perform vector search for candidate books
    3. Use LLM to select top 3 recommendations
    4. Store recommendations in PostgreSQL
    5. Return recommendations with full book details

    Args:
        session_id: Session identifier
        db: Database session
        session_mgr: Redis session manager

    Returns:
        Top 3 book recommendations with explanations
    """
    # Get session data from Redis
    session_data = session_mgr.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Extract session context
    query = session_data.get("initial_query")
    user_book_ids = session_data.get("books_from_csv", [])
    follow_up_answers = session_data.get("follow_up_answers", {})

    if not query:
        raise HTTPException(status_code=400, detail="Session has no query")

    # Generate recommendations using RAG pipeline
    try:
        recommendations, trace_id = generate_recommendations(
            db=db,
            session_id=session_id,
            query=query,
            user_book_ids=user_book_ids if user_book_ids else None,
            follow_up_answers=follow_up_answers if follow_up_answers else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Build response with full book details
    recommendations_with_books = []
    for rec in recommendations:
        book = book_service.get_book_by_id(db, rec.book_id)
        if not book:
            continue

        recommendations_with_books.append(
            RecommendationWithBook(
                id=rec.id,
                book=BookResponse.model_validate(book),
                confidence_score=rec.confidence_score,
                explanation=rec.explanation,
                rank=rec.rank,
            )
        )

    # Build Langfuse trace URL
    trace_url = None
    if trace_id:
        trace_url = f"{settings.langfuse_base_url}/trace/{trace_id}"

    return RecommendationsResponse(
        session_id=session_id,
        recommendations=recommendations_with_books,
        trace_id=trace_id,
        trace_url=trace_url,
    )
