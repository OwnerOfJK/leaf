"""Langfuse client for observability and tracing."""

from langfuse import Langfuse

from app.config import get_settings

settings = get_settings()

# Initialize Langfuse client
langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)


def get_langfuse() -> Langfuse:
    """Dependency for getting Langfuse client.

    Usage in FastAPI endpoints:
        @app.post("/recommendations")
        def create_recommendation(
            lf: Langfuse = Depends(get_langfuse)
        ):
            trace = lf.trace(name="recommendation")
            ...
    """
    return langfuse
