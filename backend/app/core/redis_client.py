"""Redis client for session management."""

import json
from typing import Any

import redis

from app.config import get_settings

settings = get_settings()

# Create Redis client
redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,  # Automatically decode bytes to strings
)


class SessionManager:
    """Manages user sessions in Redis with automatic TTL handling."""

    def __init__(self, client: redis.Redis, ttl: int = settings.redis_session_ttl):
        self.client = client
        self.ttl = ttl

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"session:{session_id}"

    def _status_key(self, session_id: str) -> str:
        """Generate Redis key for CSV processing status."""
        return f"session:{session_id}:csv_status"

    def _metadata_key(self, session_id: str) -> str:
        """Generate Redis key for session metadata."""
        return f"session:{session_id}:metadata"

    def create_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Create a new session with TTL.

        Args:
            session_id: Unique session identifier
            data: Session data to store (will be JSON serialized)
        """
        key = self._session_key(session_id)
        self.client.setex(key, self.ttl, json.dumps(data))

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve session data.

        Args:
            session_id: Unique session identifier

        Returns:
            Session data dict or None if not found/expired
        """
        key = self._session_key(session_id)
        data = self.client.get(key)
        return json.loads(data) if data else None

    def update_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Update existing session data and refresh TTL.

        Args:
            session_id: Unique session identifier
            data: Updated session data (will be JSON serialized)
        """
        key = self._session_key(session_id)
        self.client.setex(key, self.ttl, json.dumps(data))

    def extend_session_ttl(self, session_id: str) -> None:
        """Extend session TTL without modifying data.

        Useful during long-running CSV processing.
        """
        key = self._session_key(session_id)
        self.client.expire(key, self.ttl)

    def delete_session(self, session_id: str) -> None:
        """Delete session and all related keys."""
        keys_to_delete = [
            self._session_key(session_id),
            self._status_key(session_id),
            self._metadata_key(session_id),
        ]
        self.client.delete(*keys_to_delete)

    def set_csv_status(self, session_id: str, status: str) -> None:
        """Set CSV processing status.

        Args:
            session_id: Unique session identifier
            status: One of: pending, processing, completed, failed
        """
        key = self._status_key(session_id)
        self.client.setex(key, self.ttl, status)

    def get_csv_status(self, session_id: str) -> str | None:
        """Get CSV processing status."""
        key = self._status_key(session_id)
        return self.client.get(key)

    def set_metadata(self, session_id: str, metadata: dict[str, Any]) -> None:
        """Set session metadata (e.g., CSV processing progress)."""
        key = self._metadata_key(session_id)
        self.client.setex(key, self.ttl, json.dumps(metadata))

    def get_metadata(self, session_id: str) -> dict[str, Any] | None:
        """Get session metadata."""
        key = self._metadata_key(session_id)
        data = self.client.get(key)
        return json.loads(data) if data else None

    def store_generated_question(
        self, session_id: str, question_number: int, question: str
    ) -> None:
        """Store a generated question in the session.

        Updates the session data to include the generated question.

        Args:
            session_id: Unique session identifier
            question_number: Question number (1, 2, or 3)
            question: Generated question text
        """
        session_data = self.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")

        # Initialize generated_questions dict if not present
        if "generated_questions" not in session_data:
            session_data["generated_questions"] = {}

        # Store the question
        session_data["generated_questions"][question_number] = question

        # Update session with extended TTL
        self.update_session(session_id, session_data)

    def get_generated_questions(self, session_id: str) -> dict[int, str]:
        """Get all generated questions for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            Dict mapping question number to question text
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return {}

        return session_data.get("generated_questions", {})


# Global session manager instance
session_manager = SessionManager(redis_client)


def get_session_manager() -> SessionManager:
    """Dependency for getting session manager.

    Usage in FastAPI endpoints:
        @app.get("/session/{session_id}")
        def get_session(
            session_id: str,
            manager: SessionManager = Depends(get_session_manager)
        ):
            return manager.get_session(session_id)
    """
    return session_manager
