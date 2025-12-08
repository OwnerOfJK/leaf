"""API routes for session management."""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.redis_client import SessionManager, get_session_manager
from app.models.schemas import SessionAnswersResponse, SessionAnswersSubmit, SessionResponse, SessionStatusResponse
from app.workers.tasks import process_csv_upload

logger = logging.getLogger(__name__)
router = APIRouter()

# Temporary directory for CSV uploads
UPLOAD_DIR = Path("/tmp/leaf_csv_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/create", response_model=SessionResponse)
async def create_session(
    initial_query: str = Form(..., min_length=1),
    csv_file: Optional[UploadFile] = File(None),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Create a new recommendation session with optional CSV upload.

    Accepts multipart/form-data with:
    - initial_query: User's book preference query (required)
    - csv_file: Optional Goodreads library export CSV

    If CSV is uploaded:
    - Saves file to temporary location
    - Triggers async Celery task for processing
    - Returns status "processing_csv"

    Args:
        initial_query: User's initial book query
        csv_file: Optional Goodreads CSV file
        session_mgr: Redis session manager

    Returns:
        Session response with session_id and status
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())

    # Store initial session data in Redis
    session_data = {
        "initial_query": initial_query,
        "csv_uploaded": False,
        "books_from_csv": [],
        "follow_up_answers": {},
    }
    session_mgr.create_session(session_id, session_data)

    status = "ready"

    # Handle CSV upload if provided
    if csv_file:
        # Validate file extension
        if not csv_file.filename or not csv_file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .csv files are allowed."
            )

        # Save uploaded file to temporary location
        file_path = UPLOAD_DIR / f"{session_id}.csv"
        try:
            content = await csv_file.read()
            file_path.write_bytes(content)
            logger.info(f"Saved CSV file for session {session_id}: {file_path}")

            # Set CSV status to pending
            session_mgr.set_csv_status(session_id, "pending")

            # Trigger async Celery task
            task = process_csv_upload.delay(session_id, str(file_path))
            logger.info(f"Queued CSV processing task for session {session_id}, task_id: {task.id}")

            status = "processing_csv"

        except Exception as e:
            logger.error(f"Failed to save CSV file for session {session_id}: {e}")
            # Clean up file if it was partially written
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(
                status_code=500,
                detail="Failed to process CSV file. Please try again."
            )

    # Follow-up questions are handled by the frontend (hardcoded UI prompts)
    # Backend returns empty array - frontend displays its own question set
    return SessionResponse(
        session_id=session_id,
        status=status,
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


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
def get_session_status(
    session_id: str,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SessionStatusResponse:
    """Get CSV processing status for a session.

    Frontend polls this endpoint to check if CSV processing is complete.
    Returns current status and progress information.

    Args:
        session_id: Session identifier
        session_mgr: Redis session manager

    Returns:
        CSV processing status with progress details
    """
    # Check if session exists
    session_data = session_mgr.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Get CSV status
    csv_status = session_mgr.get_csv_status(session_id)
    if not csv_status:
        # No CSV was uploaded for this session
        csv_status = "none"

    # Get processing metadata
    metadata = session_mgr.get_metadata(session_id)

    # Build response
    response = SessionStatusResponse(
        session_id=session_id,
        csv_status=csv_status,
    )

    # Add progress details if available
    if metadata:
        response.books_total = metadata.get("total_books")
        response.books_processed = metadata.get("processed")
        response.new_books_added = metadata.get("added")

    return response
