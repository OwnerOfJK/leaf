"""API routes for recommendation feedback."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from langfuse import get_client
from app.models.database import Recommendation
from app.models.schemas import FeedbackResponse, FeedbackSubmit

router = APIRouter()
langfuse = get_client()

@router.post("/{recommendation_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    recommendation_id: int,
    request: FeedbackSubmit,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Submit feedback (like/dislike) for a recommendation.

    Feedback is stored in Langfuse as a score, NOT in PostgreSQL.
    This maintains Langfuse as the single source of truth for user feedback.

    Args:
        recommendation_id: Recommendation database ID
        request: Feedback submission (like/dislike)
        db: Database session

    Returns:
        Feedback submission confirmation
    """
    # Get recommendation from database
    stmt = select(Recommendation).where(Recommendation.id == recommendation_id)
    recommendation = db.scalars(stmt).first()

    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if not recommendation.trace_id:
        raise HTTPException(
            status_code=400,
            detail="Recommendation has no trace_id - cannot submit feedback",
        )

    # Convert feedback to score (like=1, dislike=0)
    score_value = 1.0 if request.feedback_type == "like" else 0.0

    # Submit score to Langfuse
    try:
        score = langfuse.create_score(
            trace_id=recommendation.trace_id,
            name="user_feedback",
            value=score_value,
            data_type="NUMERIC",
            metadata={
                "recommendation_id": recommendation_id,
                "rank": request.rank,
                "book_id": recommendation.book_id,
            },
            comment=f"User {request.feedback_type}d recommendation {recommendation_id} (rank {request.rank})",
        )

        return FeedbackResponse(
            success=True,
            langfuse_score_id=score.id if hasattr(score, "id") else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")
