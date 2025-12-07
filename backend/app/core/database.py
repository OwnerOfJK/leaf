"""Database connection and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.debug,  # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions.

    Uses context manager for automatic commit/rollback and cleanup.

    Usage in FastAPI endpoints:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Book).all()

    Behavior:
        - Automatically commits on success
        - Automatically rolls back on exception
        - Automatically closes session
    """
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
