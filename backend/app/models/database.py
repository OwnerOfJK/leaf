"""SQLAlchemy database models."""

from datetime import datetime
from typing import List

from pgvector.sqlalchemy import Vector
from sqlalchemy import DECIMAL, TIMESTAMP, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Book(Base):
    """Book metadata storage with embeddings for vector search.

    Combines book metadata from Google Books API + user uploads.
    Embeddings generated using OpenAI text-embedding-3-small (1536 dimensions).
    Enhanced with rich metadata for quality scoring and semantic search.
    """

    __tablename__ = "books"

    # Identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    isbn13: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    # Core Metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False)

    # Normalized fields for deduplication (lowercase, no punctuation)
    title_normalized: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    author_normalized: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)

    # Rich Metadata (from Google Books API)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[List[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Global Ratings (from Google Books API)
    average_rating: Mapped[float | None] = mapped_column(DECIMAL(3, 2), nullable=True)
    ratings_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Media
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI/ML
    embedding: Mapped[List[float] | None] = mapped_column(Vector(1536), nullable=True)

    # Metadata
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Book(id={self.id}, isbn='{self.isbn}', title='{self.title}')>"


class Recommendation(Base):
    """Generated recommendations with Langfuse trace linking.

    Links to Redis session (valid for 1 hour), then becomes historical reference.
    Links to Langfuse via trace_id for full trace details and user feedback.
    Retention: 30 days (auto-delete older records via scheduled job).
    """

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    book_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<Recommendation(id={self.id}, session_id='{self.session_id}', rank={self.rank})>"
