"""
Centralized Configuration Constants for Recommendation Engine

This file contains all tunable parameters for the book recommendation system.
The engine uses a multi-stage RAG pipeline with the following components:

PIPELINE STAGES:
1. RETRIEVAL STAGE:
   - Quality Scoring: Re-rank candidates by metadata richness
   - Dynamic Collaborative Filtering: Use user's relevant favorites
   - Semantic Filtering: Filter user books by query relevance

2. PENALTY STAGE:
   - Dislike Penalties: Downrank books similar to dislikes

3. GENERATION STAGE:
   - LLM Selection: GPT-4o-mini selects top 3 with explanations
   - Enhanced Context: Uses user's reading history and preferences

TUNING GUIDE:
- Increase SIMILARITY_THRESHOLD (0.4 → 0.5) for stricter filtering
- Decrease DISLIKE_PENALTY (0.5 → 0.3) for gentler penalties
- Adjust QUALITY_SCORE_WEIGHTS to prioritize different metadata
"""

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

LLM_MODEL = "gpt-4o-mini"
"""Language model used for recommendation generation."""


# =============================================================================
# QUALITY SCORING CONFIGURATION
# =============================================================================
# Adjusts similarity scores based on book metadata quality (0.0-1.0 multiplier)

QUALITY_SCORE_WEIGHTS = {
    "description_long": 0.5,     # Description > 100 chars (most important)
    "description_short": 0.2,    # Description present but short
    "categories_multiple": 0.2,  # 2+ categories (better genre signal)
    "categories_single": 0.1,    # 1 category
    "ratings_high": 0.2,         # 100+ ratings (high credibility)
    "ratings_medium": 0.1,       # 10+ ratings (medium credibility)
    "page_count": 0.05,          # Page count present
    "publisher": 0.05,           # Publisher present
}
"""
Weights for calculating book metadata quality score.
Quality score is used to boost high-quality books in search results.

Example:
    - Book with full metadata: 0.5 + 0.2 + 0.2 + 0.05 + 0.05 = 1.0
    - Book with no metadata: 0.0
    - Final similarity = original_similarity * quality_score
"""


# =============================================================================
# SEMANTIC FILTERING CONFIGURATION
# =============================================================================
# Controls when to use collaborative filtering based on query relevance

SIMILARITY_THRESHOLD = 0.4
"""
Minimum cosine similarity (0.0-1.0) for relevance filtering.

User's favorite books must be at least 40% similar to the query to be used
for collaborative filtering.

Tuning:
    - Higher (e.g., 0.5): Only very relevant books pass filter (stricter)
    - Lower (e.g., 0.3): Somewhat relevant books pass filter (more lenient)

Example:
    User has 20 coding books rated 5★
    Query: "fantasy with magic"
    With threshold 0.4: Coding books excluded (similarity < 0.4)
    Result: Collaborative filtering skipped, uses query search instead
"""

MIN_RELEVANT_BOOKS = 2
"""
Minimum number of relevant high-rated books needed for collaborative filtering.

If user has fewer than this many relevant favorites, collaborative filtering
is skipped entirely.

Tuning:
    - Higher (e.g., 3): Requires more signal before using collaborative
    - Lower (e.g., 1): Uses collaborative with minimal signal

Default: 2 (requires at least 2 relevant favorites)
"""

HIGH_RATING_THRESHOLD = 4
"""
Books rated at or above this threshold are considered "favorites".

Used for:
    - Identifying books to use in collaborative filtering
    - Building LLM context (shows user's loved books)

Default: 4 (books rated 4-5 stars)
"""


# =============================================================================
# DISLIKE PENALTY CONFIGURATION
# =============================================================================
# Prevents recommending books similar to ones the user disliked

DISLIKE_THRESHOLD = 2
"""
Books rated at or below this threshold are considered "dislikes".

Used for:
    - Identifying books to avoid in recommendations
    - Building LLM context (shows user's disliked books)
    - Applying similarity penalties to candidates

Default: 2 (books rated 1-2 stars)
"""

DISLIKE_PENALTY = 0.5
"""
Similarity multiplier applied to books similar to dislikes (0.0-1.0).

When a candidate book is too similar to a disliked book, its similarity
score is multiplied by this penalty factor.

Tuning:
    - Higher (e.g., 0.7): Gentler penalty (slight downranking)
    - Lower (e.g., 0.2): Harsher penalty (strong downranking)
    - 0.0: Complete elimination of similar books

Example:
    User rated "Twilight" 1★
    Candidate "Midnight Sun" has similarity 0.9
    Similarity to Twilight: 0.7 (above threshold)
    Final similarity: 0.9 * 0.5 = 0.45 (penalized)

Default: 0.5 (halves the similarity)
"""

DISLIKE_SIMILARITY_THRESHOLD = 0.5
"""
Minimum similarity to disliked books required to trigger penalty (0.0-1.0).

Only books that are at least 60% similar to a disliked book will be penalized.

Tuning:
    - Higher (e.g., 0.7): Only very similar books penalized
    - Lower (e.g., 0.5): Somewhat similar books also penalized

Example:
    User disliked "Twilight"
    Candidate A: 70% similar → penalized (above 0.6)
    Candidate B: 50% similar → not penalized (below 0.6)

Default: 0.6 (60% similarity threshold)
"""


# =============================================================================
# CANDIDATE RETRIEVAL CONFIGURATION
# =============================================================================

DEFAULT_TOP_K = 20
"""
Default number of candidate books to retrieve before LLM selection.

The pipeline retrieves this many candidates through vector search and
collaborative filtering, then the LLM selects the top 3 from these candidates.

Default: 60 candidates → LLM selects 3
"""

COLLABORATIVE_FILTERING_LIMIT = 10
"""
Maximum number of books to retrieve via collaborative filtering.

When the user has relevant favorites, this many books similar to those
favorites are retrieved.

Default: 10 books
"""


# =============================================================================
# LLM CONTEXT CONFIGURATION
# =============================================================================

MAX_FAVORITES_IN_CONTEXT = 5
"""
Maximum number of user's favorite books to show in LLM context.

Shows the user's top-rated books to help LLM understand preferences.

Default: 5 books
"""

MAX_DISLIKES_IN_CONTEXT = 3
"""
Maximum number of user's disliked books to show in LLM context.

Shows books the user rated poorly to help LLM avoid similar recommendations.

Default: 3 books
"""

CANDIDATE_DESCRIPTION_MAX_LENGTH = 200
"""
Maximum length of book descriptions shown to LLM for each candidate.

Longer descriptions are truncated to this length.

Default: 200 characters
"""


# =============================================================================
# VALIDATION
# =============================================================================

def validate_constants():
    """
    Validate that all constants are within acceptable ranges.

    Raises:
        ValueError: If any constant is out of range
    """
    # Similarity thresholds must be between 0 and 1
    if not 0.0 <= SIMILARITY_THRESHOLD <= 1.0:
        raise ValueError(f"SIMILARITY_THRESHOLD must be 0.0-1.0, got {SIMILARITY_THRESHOLD}")

    if not 0.0 <= DISLIKE_SIMILARITY_THRESHOLD <= 1.0:
        raise ValueError(f"DISLIKE_SIMILARITY_THRESHOLD must be 0.0-1.0, got {DISLIKE_SIMILARITY_THRESHOLD}")

    if not 0.0 <= DISLIKE_PENALTY <= 1.0:
        raise ValueError(f"DISLIKE_PENALTY must be 0.0-1.0, got {DISLIKE_PENALTY}")

    # Rating thresholds must be between 1 and 5
    if not 1 <= DISLIKE_THRESHOLD <= 5:
        raise ValueError(f"DISLIKE_THRESHOLD must be 1-5, got {DISLIKE_THRESHOLD}")

    if not 1 <= HIGH_RATING_THRESHOLD <= 5:
        raise ValueError(f"HIGH_RATING_THRESHOLD must be 1-5, got {HIGH_RATING_THRESHOLD}")

    # Counts must be positive
    if MIN_RELEVANT_BOOKS < 1:
        raise ValueError(f"MIN_RELEVANT_BOOKS must be >= 1, got {MIN_RELEVANT_BOOKS}")

    if DEFAULT_TOP_K < 1:
        raise ValueError(f"DEFAULT_TOP_K must be >= 1, got {DEFAULT_TOP_K}")

    if COLLABORATIVE_FILTERING_LIMIT < 1:
        raise ValueError(f"COLLABORATIVE_FILTERING_LIMIT must be >= 1, got {COLLABORATIVE_FILTERING_LIMIT}")


# Run validation on import
validate_constants()
