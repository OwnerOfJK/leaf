"""OpenAI embedding utilities with Langfuse tracking."""

from typing import List

from langfuse.openai import OpenAI

from app.config import get_settings

settings = get_settings()

# Initialize OpenAI client with Langfuse wrapper
# This automatically tracks all OpenAI calls in Langfuse
openai_client = OpenAI(api_key=settings.openai_api_key)

# Embedding model configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def create_embedding(text: str) -> List[float]:
    """Generate embedding for a single text.

    Args:
        text: Text to embed

    Returns:
        List of 1536 floats representing the embedding vector
    """
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts in a single API call.

    More efficient than individual calls. OpenAI supports up to 2048 inputs per request.

    Args:
        texts: List of texts to embed (max 2048)

    Returns:
        List of embedding vectors, one per input text
    """
    if len(texts) > 2048:
        raise ValueError("Maximum 2048 texts per batch request")

    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    # Ensure embeddings are in same order as input
    return [item.embedding for item in response.data]


def format_book_text(title: str, author: str, description: str | None = None) -> str:
    """Format book metadata into text for embedding.

    Args:
        title: Book title
        author: Book author
        description: Book description (optional)

    Returns:
        Formatted text string for embedding
    """
    if description:
        return f"{title} by {author}. {description}"
    return f"{title} by {author}"
