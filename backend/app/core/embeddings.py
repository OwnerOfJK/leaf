"""OpenAI embedding utilities with Langfuse tracking."""

from typing import List

from langfuse.openai import OpenAI
from langfuse import observe

from app.config import get_settings

settings = get_settings()

# Initialize OpenAI client with Langfuse wrapper
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

@observe()
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


def format_book_text(
    title: str,
    author: str,
    description: str | None = None,
    categories: list[str] | None = None,
    publication_year: int | None = None,
    page_count: int | None = None,
) -> str:
    """Format book metadata into text for embedding (Phase 1 enhanced format).

    Creates a rich text representation including title, author, description,
    categories, publication year, and page count for better semantic search.

    Args:
        title: Book title
        author: Book author
        description: Book description (optional, truncated to 2000 chars)
        categories: List of genre/category tags (optional)
        publication_year: Year of publication (optional)
        page_count: Number of pages (optional)

    Returns:
        Formatted text string optimized for embedding generation
    """
    parts = [f"{title} by {author}"]

    if description:
        parts.append(description)

    if categories:
        parts.append(f"Genres: {', '.join(categories)}")

    if publication_year:
        parts.append(f"Published: {publication_year}")

    if page_count:
        parts.append(f"Pages: {page_count}")

    return ". ".join(parts)
