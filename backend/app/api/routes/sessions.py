"""API routes for session management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.redis_client import SessionManager, get_session_manager
from app.models.schemas import SessionAnswersResponse, SessionAnswersSubmit, SessionCreate, SessionResponse

router = APIRouter()


@router.post("/create", response_model=SessionResponse)
def create_session(
    request: SessionCreate,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Create a new recommendation session.

    Stores the user's initial query in Redis and returns a session ID.
    No CSV upload in Phase 1 - that will be added later.

    Args:
        request: Session creation request with initial query
        session_mgr: Redis session manager

    Returns:
        Session response with session_id and status
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())

    # Store session data in Redis
    session_data = {
        "initial_query": request.initial_query,
        "csv_uploaded": False,
        "books_from_csv": [],
        "follow_up_answers": {},
    }
    session_mgr.create_session(session_id, session_data)

    # For now, return empty follow-up questions (will be implemented later)
    return SessionResponse(
        session_id=session_id,
        status="ready",
        follow_up_questions=[],
    )


@router.post("/{session_id}/answers", response_model=SessionAnswersResponse)
def submit_answers(
    session_id: str,
    request: SessionAnswersSubmit,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SessionAnswersResponse:
    """Submit follow-up question answers.

    Updates the session with user's answers to follow-up questions.
    These answers will be incorporated into the recommendation generation.

    Args:
        session_id: Session identifier
        request: Follow-up answers
        session_mgr: Redis session manager

    Returns:
        Updated session status
    """
    # Get existing session
    session_data = session_mgr.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Update with follow-up answers
    session_data["follow_up_answers"] = request.answers.model_dump(exclude_none=True)
    session_mgr.update_session(session_id, session_data)

    # Count CSV books if available
    csv_books_count = len(session_data.get("books_from_csv", []))

    return SessionAnswersResponse(
        session_id=session_id,
        status="ready",
        csv_books_count=csv_books_count if csv_books_count > 0 else None,
    )
