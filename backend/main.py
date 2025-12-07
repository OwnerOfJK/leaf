"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title="Leaf - Book Recommendation API",
    description="Conversational book recommendation system with RAG pipeline",
    version="0.1.0",
    debug=settings.debug,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Leaf Book Recommendation API",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "database": "not configured yet",  # Will update when DB routes are added
        "redis": "not configured yet",
    }


@app.get("/test/db")
def test_database():
    """Test database connectivity and query."""
    from sqlalchemy import text
    from app.core.database import engine

    try:
        with engine.connect() as conn:
            # Test pgvector extension
            result = conn.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"))
            extension = result.fetchone()

            # Count tables
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result.fetchall()]

            return {
                "status": "connected",
                "pgvector_installed": extension is not None,
                "pgvector_version": extension[1] if extension else None,
                "tables": tables,
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/test/redis")
def test_redis():
    """Test Redis connectivity."""
    from app.core.redis_client import redis_client

    try:
        if not redis_client:
            return {"status": "error", "error": "Redis client not initialized"}

        # Test basic operations
        redis_client.set("test_key", "test_value", ex=10)
        value = redis_client.get("test_key")
        redis_client.delete("test_key")

        info = redis_client.info("server")

        return {
            "status": "connected",
            "test_write_read": "success" if value == "test_value" else "failed",
            "redis_version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# TODO: Include API routes when implemented
# from app.api.routes import sessions, recommendations, feedback
# app.include_router(sessions.router, prefix="/api", tags=["sessions"])
# app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
# app.include_router(feedback.router, prefix="/api", tags=["feedback"])
