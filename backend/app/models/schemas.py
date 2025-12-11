"""Pydantic schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Session Schemas
# ============================================================================


class SessionCreate(BaseModel):
    """Request schema for creating a new session."""

    initial_query: str = Field(..., min_length=1, description="User's initial book query")


class FollowUpAnswers(BaseModel):
    """Schema for follow-up question answers."""

    question_1: Optional[str] = Field(None, description="Answer to question 1")
    question_2: Optional[str] = Field(None, description="Answer to question 2")
    question_3: Optional[str] = Field(None, description="Answer to question 3")


class SessionAnswersSubmit(BaseModel):
    """Request schema for submitting follow-up answers."""

    answers: FollowUpAnswers


class SessionResponse(BaseModel):
    """Response schema for session creation."""

    session_id: str
    status: str = Field(..., description="processing_csv | ready")
    follow_up_questions: List[str]
    expires_at: int = Field(..., description="Unix timestamp (ms) when session expires")


class SessionAnswersResponse(BaseModel):
    """Response schema after submitting answers."""

    session_id: str
    status: str = Field(..., description="ready | processing_csv")
    csv_books_count: Optional[int] = Field(None, description="Number of books from CSV")


class SessionStatusResponse(BaseModel):
    """Response schema for CSV processing status."""

    session_id: str
    csv_status: str = Field(
        ..., description="pending | processing | completed | failed"
    )
    books_processed: Optional[int] = None
    books_total: Optional[int] = None
    new_books_added: Optional[int] = None


class GenerateQuestionRequest(BaseModel):
    """Request schema for generating a follow-up question."""

    question_number: int = Field(..., ge=1, le=3, description="Question number (1, 2, or 3)")


class GenerateQuestionResponse(BaseModel):
    """Response schema for generated question."""

    question: str = Field(..., description="Generated question text")
    question_number: int = Field(..., ge=1, le=3, description="Question number (1, 2, or 3)")


# ============================================================================
# Book Schemas
# ============================================================================


class BookBase(BaseModel):
    """Base book schema with common fields."""

    isbn: str
    title: str
    author: str
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    cover_url: Optional[str] = None

    # Rich metadata fields
    isbn13: Optional[str] = None
    page_count: Optional[int] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    language: Optional[str] = None
    average_rating: Optional[Decimal] = None
    ratings_count: Optional[int] = None


class BookResponse(BookBase):
    """Response schema for book data."""

    model_config = {"from_attributes": True}


# ============================================================================
# Recommendation Schemas
# ============================================================================


class RecommendationBase(BaseModel):
    """Base recommendation schema."""

    confidence_score: Decimal = Field(
        ..., ge=0, le=100, description="Cosine similarity score (0-100)"
    )
    explanation: str = Field(..., description="LLM-generated explanation")
    rank: int = Field(..., ge=1, le=3, description="Rank (1, 2, or 3)")


class RecommendationWithBook(RecommendationBase):
    """Recommendation with full book details."""

    id: int
    book: BookResponse
    rank: int

    model_config = {"from_attributes": True}


class RecommendationsResponse(BaseModel):
    """Response schema for recommendations endpoint."""

    session_id: str
    recommendations: List[RecommendationWithBook]
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None


# ============================================================================
# Feedback Schemas
# ============================================================================


class FeedbackSubmit(BaseModel):
    """Request schema for submitting feedback."""

    feedback_type: str = Field(..., pattern="^(like|dislike)$")


class FeedbackResponse(BaseModel):
    """Response schema after submitting feedback."""

    success: bool
    langfuse_score_id: Optional[str] = None


# ============================================================================
# Database Model Schemas (for internal use)
# ============================================================================


class BookCreate(BookBase):
    """Schema for creating a book in database."""

    embedding: Optional[List[float]] = Field(None, description="1536-dim vector")


class BookDB(BookBase):
    """Database book schema with all fields."""

    id: int
    embedding: Optional[List[float]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationCreate(RecommendationBase):
    """Schema for creating a recommendation in database."""

    session_id: str
    book_id: int
    trace_id: Optional[str] = None


class RecommendationDB(RecommendationBase):
    """Database recommendation schema with all fields."""

    id: int
    session_id: str
    book_id: int
    trace_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
