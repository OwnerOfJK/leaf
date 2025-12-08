# Data Architecture & Recommendation Strategy

## Document Purpose

This document defines how Leaf stores and utilizes two distinct types of data to generate personalized book recommendations:

1. **Global book metadata** (shared across all users, stored in PostgreSQL)
2. **User-specific reading data** (session-scoped, stored in Redis)

This architecture enables a hybrid recommendation approach that combines semantic search (what the user asks for) with collaborative filtering (what they've historically enjoyed), while gracefully degrading when user data is unavailable.

**Key Features:**
- **Enhanced embeddings** using title, author, description, and categories
- **Dynamic collaborative weighting** based on signal strength
- **Metadata quality scoring** to prioritize high-quality book data
- **Dislike penalty system** to avoid books similar to user's dislikes

---

## Table of Contents

1. [Data Sources Overview](#1-data-sources-overview)
2. [Database Schema (PostgreSQL)](#2-database-schema-postgresql)
3. [Redis Session Structure](#3-redis-session-structure)
4. [Data Flow: CSV Processing](#4-data-flow-csv-processing)
5. [Recommendation Algorithm](#5-recommendation-algorithm)
6. [Enhanced Features](#6-enhanced-features)
7. [Fallback Strategies](#7-fallback-strategies)
8. [Configuration Parameters](#8-configuration-parameters)
9. [Data Utilization Summary](#9-data-utilization-summary)
10. [Example: End-to-End Flow](#10-example-end-to-end-flow)
11. [Key Design Principles](#11-key-design-principles)
12. [Migration Guide](#12-migration-guide)
13. [Implementation Checklist](#13-implementation-checklist)

---

## 1. Data Sources Overview

### Source 1: Open Library Dump (Initial 300k Books)

**Purpose:** Populate the shared book database

**Available Fields:**
- ISBN/ISBN13
- Title
- Author(s)
- Publication year
- ❌ Missing: Description (critical for embeddings)

**Strategy:** Use as seed data, enrich with Google Books API for descriptions

---

### Source 2: Google Books API (Enrichment Source)

**Purpose:** Fetch rich metadata for books (both initial population and user uploads)

**Example API Response:**
```json
{
  "volumeInfo": {
    "title": "Atomic Habits",
    "subtitle": "An Easy & Proven Way to Build Good Habits & Break Bad Ones",
    "authors": ["James Clear"],
    "publisher": "Penguin",
    "publishedDate": "2018-10-16",
    "description": "The #1 New York Times bestseller. Over 25 million copies sold!...",
    "pageCount": 321,
    "categories": ["Business & Economics"],
    "averageRating": 3.5,
    "ratingsCount": 7,
    "imageLinks": {
      "thumbnail": "http://books.google.com/books/content?id=..."
    },
    "language": "en",
    "industryIdentifiers": [
      {"type": "ISBN_13", "identifier": "9780735211292"},
      {"type": "ISBN_10", "identifier": "0735211299"}
    ]
  }
}
```

**Fields to Extract:**
- ✅ `description` - **CRITICAL** for embeddings (enables semantic search)
- ✅ `imageLinks.thumbnail` - Cover image URL
- ✅ `categories` - Genre/topic tags (now used in embeddings)
- ✅ `pageCount` - Book length (now used in embeddings)
- ✅ `publisher` - Publisher name
- ✅ `publishedDate` - Extract publication year (now used in embeddings)
- ✅ `averageRating` - Global rating across all Google Books users
- ✅ `ratingsCount` - Number of ratings (used in quality scoring)
- ✅ `language` - Language code (e.g., "en", "de")
- ✅ `industryIdentifiers` - ISBN-10 and ISBN-13

---

### Source 3: Goodreads CSV (User Upload)

**Purpose:** Understand user's reading history and preferences

**CSV Format:**
```csv
Book Id,Title,Author,ISBN,ISBN13,My Rating,Average Rating,Publisher,
Number of Pages,Year Published,Date Read,Bookshelves,...
```

**Example Row:**
```csv
29227774,"Light Bringer","Pierce Brown","1473646804","9781473646803",5,4.77,
"Hodder & Stoughton",682,2023,2024/04/14,,,read,,,,1,0
```

**Fields to Extract:**
- ✅ `ISBN` / `ISBN13` - Book identifier (to match against database)
- ✅ `My Rating` - **USER-SPECIFIC** rating (1-5 stars)
- ✅ `Title` / `Author` - Fallback for display (avoid DB joins)
- ❌ `Average Rating` - Ignore (prefer Google Books global rating)
- ❌ `Date Read`, `Bookshelves`, `My Review` - Not used in MVP

**Critical Insight:** The CSV contains two types of data:
1. **Book identifiers** (ISBN) → Match against shared database
2. **User preferences** (My Rating) → Store per-session, influences recommendations

---

## 2. Database Schema (PostgreSQL)

### `books` Table - Global Book Metadata

This table stores **shared book data** accessible to all users. User-specific data does NOT belong here.
```sql
CREATE TABLE books (
    -- Identity
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(20) UNIQUE NOT NULL,
    isbn13 VARCHAR(20),
    
    -- Core Metadata (always present)
    title TEXT NOT NULL,
    author TEXT NOT NULL,  -- comma-separated if multiple authors
    
    -- Rich Metadata (from Google Books API)
    description TEXT,  -- CRITICAL: used for embeddings
    categories TEXT[],  -- e.g., ["Science Fiction", "Thriller"]
    page_count INTEGER,
    publisher TEXT,
    publication_year INTEGER,
    language VARCHAR(10),  -- e.g., "en", "de"
    
    -- Global Ratings (from Google Books API)
    average_rating DECIMAL(3,2),  -- 0.00 to 5.00
    ratings_count INTEGER,
    
    -- Media
    cover_url TEXT,
    
    -- AI/ML
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    
    -- Metadata
    data_source VARCHAR(50),  -- 'open_library_google_books' | 'user_csv_google_books'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_books_isbn ON books(isbn);
CREATE INDEX idx_books_isbn13 ON books(isbn13);
CREATE INDEX idx_books_embedding ON books USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_books_categories ON books USING GIN(categories);
CREATE INDEX idx_books_publication_year ON books(publication_year);
```

**What Goes in This Table:**
- ✅ Book metadata (title, author, description)
- ✅ Global ratings from Google Books (average_rating, ratings_count)
- ✅ Embeddings for vector search
- ❌ User ratings from Goodreads CSV (these are relational, not book properties)
- ❌ User-specific data (read dates, personal reviews)

**SQLAlchemy Model:**
```python
# app/models/database.py
from sqlalchemy import DECIMAL, INTEGER, TIMESTAMP, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from datetime import datetime
from typing import List

class Book(Base):
    __tablename__ = "books"
    
    # Identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isbn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    isbn13: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    
    # Core Metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Rich Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[List[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Global Ratings
    average_rating: Mapped[float | None] = mapped_column(DECIMAL(3, 2), nullable=True)
    ratings_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Media
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # AI/ML
    embedding: Mapped[List[float] | None] = mapped_column(Vector(1536), nullable=True)
    
    # Metadata
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
```

---

### `recommendations` Table - Generated Recommendations

Stores recommendations with Langfuse trace linking (30-day retention).
```sql
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    book_id INTEGER REFERENCES books(id),
    confidence_score DECIMAL(5,2),
    explanation TEXT,
    rank INTEGER,
    trace_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_recommendations_session_id ON recommendations(session_id);
CREATE INDEX idx_recommendations_book_id ON recommendations(book_id);
CREATE INDEX idx_recommendations_created_at ON recommendations(created_at);
```

---

## 3. Redis Session Structure

### Session Data (User-Specific Context)

**Key:** `session:{session_id}`  
**TTL:** 3600 seconds (1 hour)
```json
{
  "initial_query": "I want a sci-fi book like The Martian but darker",
  
  "follow_up_answers": {
    "question_1": "Medium length, 300-400 pages",
    "question_2": "Plot-driven",
    "question_3": "Recent publications preferred"
  },
  
  "csv_uploaded": true,
  
  "books_from_csv": [
    {
      "book_id": 12345,
      "title": "Project Hail Mary",
      "author": "Andy Weir",
      "user_rating": 5
    },
    {
      "book_id": 12346,
      "title": "The Expanse: Leviathan Wakes",
      "author": "James S.A. Corey",
      "user_rating": 4
    },
    {
      "book_id": 12347,
      "title": "Foundation",
      "author": "Isaac Asimov",
      "user_rating": 2
    }
  ],
  
  "created_at": "2024-12-08T10:30:00Z"
}
```

**Critical Fields:**
- `books_from_csv[].book_id` - References PostgreSQL books.id
- `books_from_csv[].user_rating` - **USER-SPECIFIC** 1-5 star rating from Goodreads CSV
- `books_from_csv[].title` / `author` - For display purposes (avoids DB joins in session context)

**Why User Ratings Go Here (Not in Database):**
- User A rates "1984" as 5 stars
- User B rates "1984" as 2 stars
- Same book, different user preferences
- Cannot store in books table (it's not a book property, it's a user ↔ book relationship)
- Session-scoped data expires after 1 hour (no persistent user accounts in MVP)

---

## 4. Data Flow: CSV Processing

### CSV Processing Worker (Celery Task)
```python
# app/workers/tasks.py
import pandas as pd
from app.core.embeddings import create_embedding, format_book_text_for_embedding
from app.services.google_books_api import fetch_from_google_books

@celery.task
def process_csv_task(session_id: str, csv_path: str):
    """Process Goodreads CSV and extract user reading preferences.
    
    Steps:
    1. Parse CSV and extract ISBN + user ratings
    2. Check if each book exists in shared database
    3. If missing: fetch from Google Books API and store
    4. Generate embeddings for new books (using enhanced format)
    5. Store user's book list (with ratings) in Redis session
    """
    
    redis_client.set(f"session:{session_id}:csv_status", "processing")
    
    df = pd.read_csv(csv_path)
    user_books = []  # Will contain {book_id, title, author, user_rating}
    new_books_added = 0
    
    for idx, row in df.iterrows():
        # Extract book identifier
        isbn = row['ISBN13'] or row['ISBN']
        if not isbn:
            continue
        
        # Extract USER-SPECIFIC rating (critical!)
        user_rating = row.get('My Rating')  # 1-5 stars or empty
        
        # Step 1: Check if book exists in shared database
        existing_book = db.query(Book).filter_by(isbn=isbn).first()
        
        if existing_book:
            # Book already in database
            user_books.append({
                "book_id": existing_book.id,
                "title": existing_book.title,
                "author": existing_book.author,
                "user_rating": int(user_rating) if user_rating else None
            })
            continue
        
        # Step 2: Book not in database - fetch from Google Books API
        google_data = fetch_from_google_books(isbn)
        
        if not google_data:
            logger.warning(f"ISBN {isbn} not found in Google Books API")
            continue
        
        # Step 3: Insert into shared books table
        new_book = Book(
            isbn=isbn,
            isbn13=extract_isbn13(google_data),
            title=google_data['title'],
            author=', '.join(google_data.get('authors', [])),
            description=google_data.get('description'),  # CRITICAL for embeddings
            categories=google_data.get('categories', []),
            page_count=google_data.get('pageCount'),
            publisher=google_data.get('publisher'),
            publication_year=extract_year(google_data.get('publishedDate')),
            average_rating=google_data.get('averageRating'),  # GLOBAL rating
            ratings_count=google_data.get('ratingsCount'),
            cover_url=google_data.get('imageLinks', {}).get('thumbnail'),
            language=google_data.get('language', 'en'),
            data_source='user_csv_google_books'
        )
        db.add(new_book)
        db.commit()
        
        # Step 4: Generate embedding using ENHANCED format
        book_text = format_book_text_for_embedding(new_book)
        embedding = create_embedding(book_text)
        new_book.embedding = embedding
        db.commit()
        
        # Step 5: Add to user's reading list with USER rating
        user_books.append({
            "book_id": new_book.id,
            "title": new_book.title,
            "author": new_book.author,
            "user_rating": int(user_rating) if user_rating else None
        })
        new_books_added += 1
        
        # Update progress metadata
        redis_client.setex(
            f"session:{session_id}:metadata",
            3600,
            json.dumps({
                "total_books_in_csv": len(df),
                "books_processed": idx + 1,
                "new_books_added": new_books_added
            })
        )
    
    # Step 6: Update Redis session with user books + ratings
    session_data = json.loads(redis_client.get(f"session:{session_id}"))
    session_data["books_from_csv"] = user_books  # Includes user_rating!
    redis_client.setex(f"session:{session_id}", 3600, json.dumps(session_data))
    
    # Mark as completed
    redis_client.setex(f"session:{session_id}:csv_status", 3600, "completed")
```

**Key Points:**
1. Extract `My Rating` from CSV (user-specific preference)
2. Check if book exists in shared database by ISBN
3. If missing, fetch from Google Books API and store
4. Generate embedding using **enhanced format** (includes categories, page count, year)
5. Store user's book list with ratings in Redis (session-scoped)
6. User ratings stay in Redis, never pollute books table

---

## 5. Recommendation Algorithm

### Overview: Hybrid Approach with Enhanced Features

The recommendation engine uses **four complementary strategies**:

1. **Semantic Search** (from enhanced book embeddings)
   - User query → embedding
   - Find books semantically similar to what they described
   - Enhanced embeddings now include categories, page count, publication year

2. **Collaborative Filtering** (from user reading history)
   - User liked books A, B, C (high ratings)
   - Find books similar to their favorites
   - Weight dynamically adjusted based on signal strength

3. **Semantic Filtering of User Favorites** (hybrid approach)
   - Filter user's 5★ books by relevance to current query
   - Only use favorites contextually related to what they're asking for
   - Prevents unrelated 5★ books from dominating recommendations

4. **Quality-Aware Ranking** (metadata quality scoring)
   - Prioritize books with rich metadata (descriptions, categories, ratings)
   - Penalize books with sparse or missing information
   - Ensures high-quality recommendations

5. **Dislike Avoidance** (penalty system)
   - Identify books user rated poorly (1-2 stars)
   - Apply penalty to candidates very similar to dislikes
   - LLM receives context about books to avoid

---

### Implementation: Recommendation Engine
```python
# app/services/recommendation_engine.py
from langfuse.decorators import observe, langfuse_context
from scipy.spatial.distance import cosine as cosine_distance
from app.core.embeddings import create_embedding
from app.services import vector_search

# Configuration
SIMILARITY_THRESHOLD = 0.3  # 30% cosine similarity for relevance filtering
MIN_RELEVANT_BOOKS = 2      # Minimum relevant 5★ books to use filtering

# Dislike penalty configuration
DISLIKE_PENALTY_CONFIG = {
    "enabled": True,
    "min_dislikes": 2,           # Need 2+ dislikes to activate
    "similarity_threshold": 0.6,  # Only penalize if >60% similar
    "penalty_strength": 0.3,      # 30% score reduction
}

@observe()
def generate_recommendations(
    db: Session,
    session_id: str,
    query: str,
    user_books: list[dict] | None = None,
    follow_up_answers: dict | None = None,
) -> tuple[list[Recommendation], str]:
    """Generate personalized book recommendations using RAG pipeline.
    
    Args:
        db: Database session
        session_id: Session identifier
        query: User's initial query
        user_books: List of {book_id, title, author, user_rating} from CSV
        follow_up_answers: Optional dictionary of follow-up answers
    
    Returns:
        Tuple of (list of Recommendation objects, trace_id)
    """
    
    # Step 1: Build enhanced query
    enhanced_query = _build_enhanced_query(query, follow_up_answers)
    
    # Step 2: Retrieve candidate books using hybrid search
    candidate_books = _retrieve_candidates(
        db=db,
        query=enhanced_query,
        user_books=user_books,
    )
    
    if not candidate_books:
        raise ValueError("No candidate books found")
    
    # Step 3: Generate recommendations using LLM
    recommendations_data = _generate_with_llm(
        query=enhanced_query,
        candidate_books=candidate_books,
        user_books=user_books,
    )
    
    # Step 4: Store recommendations
    recommendations = _store_recommendations(
        db=db,
        session_id=session_id,
        recommendations_data=recommendations_data,
    )
    
    trace_id = langfuse_context.get_current_trace_id()
    return recommendations, trace_id


@observe()
def _retrieve_candidates(
    db: Session,
    query: str,
    user_books: list[dict] | None = None,
    top_k: int = 20,
) -> list[Book]:
    """Retrieve candidate books using hybrid search with enhanced features.
    
    Enhanced Features:
    1. Dynamic collaborative weighting based on signal strength
    2. Semantic filtering of user favorites
    3. Metadata quality scoring
    4. Dislike penalty system
    
    Args:
        db: Database session
        query: Enhanced query string
        user_books: List of {book_id, title, author, user_rating}
        top_k: Total candidates to return
    
    Returns:
        List of candidate Book objects
    """
    
    query_embedding = create_embedding(query)
    candidates = []
    exclude_ids = []
    
    # Determine collaborative weight dynamically
    collaborative_weight = 0.0
    
    if user_books:
        # Filter for highly-rated books (4-5 stars)
        highly_rated = [b for b in user_books if b.get('user_rating', 0) >= 4]
        
        if highly_rated:
            # Apply semantic filtering to find query-relevant favorites
            relevant_favorites = _filter_relevant_books(
                db=db,
                query_embedding=query_embedding,
                user_books=highly_rated,
                similarity_threshold=SIMILARITY_THRESHOLD,
            )
            
            if len(relevant_favorites) >= MIN_RELEVANT_BOOKS:
                # BEST CASE: Use contextually relevant 5★ books
                book_ids = [b['book_id'] for b in relevant_favorites]
                # Dynamic weight: scales from 0.2 (2 books) to 0.5 (5+ books)
                collaborative_weight = min(0.5, 0.2 + (len(relevant_favorites) - 2) * 0.1)
            elif highly_rated:
                # FALLBACK 1: Use ALL 5★ books
                book_ids = [b['book_id'] for b in highly_rated]
                # Dynamic weight: scales from 0.15 to 0.3
                collaborative_weight = min(0.3, 0.15 + (len(highly_rated) - 1) * 0.05)
        elif user_books:
            # FALLBACK 2: No high ratings, use all books
            book_ids = [b['book_id'] for b in user_books]
            # Weak signal: scales from 0.1 to 0.2
            collaborative_weight = min(0.2, 0.1 + (len(user_books) - 1) * 0.02)
        
        # Exclude user's books from results
        exclude_ids = [b['book_id'] for b in user_books]
        
        # Get collaborative candidates
        if collaborative_weight > 0:
            user_similar = vector_search.search_similar_to_books(
                db=db,
                book_ids=book_ids,
                limit=int(top_k * collaborative_weight),
                exclude_ids=exclude_ids,
            )
            candidates.extend(user_similar)
            exclude_ids.extend([book.id for book in user_similar])
    
    # Semantic search fills remaining slots
    semantic_count = top_k - len(candidates)
    query_similar = vector_search.search_similar_books(
        db=db,
        embedding=query_embedding,
        limit=semantic_count,
        exclude_ids=exclude_ids,
    )
    candidates.extend(query_similar)
    
    # Apply metadata quality scoring
    candidates = _apply_quality_scoring(candidates)
    
    # Apply dislike penalty if warranted
    if user_books and DISLIKE_PENALTY_CONFIG["enabled"]:
        strong_dislikes = [
            b for b in user_books 
            if b.get('user_rating', 0) <= 2 and b.get('user_rating', 0) > 0
        ]
        
        if len(strong_dislikes) >= DISLIKE_PENALTY_CONFIG["min_dislikes"]:
            candidates = _apply_dislike_penalty(db, candidates, strong_dislikes)
    
    return candidates[:top_k]


@observe()
def _filter_relevant_books(
    db: Session,
    query_embedding: list[float],
    user_books: list[dict],
    similarity_threshold: float = 0.3,
) -> list[dict]:
    """Filter user's favorite books by semantic relevance to query.
    
    This prevents unrelated 5★ books from dominating recommendations.
    
    Example:
    - User has 20 coding books rated 5★
    - Query: "fantasy with strong magic systems"
    - Result: Only return 5★ fantasy books (if any exist in their library)
    
    Args:
        db: Database session
        query_embedding: Query embedding vector
        user_books: List of {book_id, title, author, user_rating}
        similarity_threshold: Minimum cosine similarity to be considered relevant
    
    Returns:
        Filtered list of user_books that are contextually relevant to query
    """
    book_ids = [b['book_id'] for b in user_books]
    
    # Fetch books with embeddings
    books = db.query(Book).filter(Book.id.in_(book_ids)).all()
    
    relevant_books = []
    for book in books:
        if not book.embedding:
            continue
        
        # Compute cosine similarity between query and book
        similarity = 1 - cosine_distance(query_embedding, book.embedding)
        
        if similarity >= similarity_threshold:
            # Find original user_book dict to preserve rating
            user_book = next(b for b in user_books if b['book_id'] == book.id)
            relevant_books.append(user_book)
    
    return relevant_books


@observe()
def _apply_quality_scoring(candidates: list[Book]) -> list[Book]:
    """Apply metadata quality scoring and re-rank candidates.
    
    Quality Score Components:
    - Description (50%): Long description (>100 chars) = 0.5, Short = 0.2
    - Categories (20%): 2+ categories = 0.2, 1 category = 0.1
    - Ratings (20%): 100+ ratings = 0.2, 10+ ratings = 0.1
    - Additional metadata (10%): page_count + publisher = 0.05 each
    
    Args:
        candidates: List of candidate books with similarity scores
    
    Returns:
        Re-ranked list with quality-adjusted scores
    """
    for candidate in candidates:
        quality_score = _calculate_quality_score(candidate)
        
        # Adjust similarity score by quality
        # This ensures high-quality books rank higher
        if hasattr(candidate, 'similarity'):
            candidate.similarity = candidate.similarity * quality_score
        
        candidate.quality_score = quality_score
    
    # Re-sort by adjusted similarity
    candidates.sort(key=lambda x: getattr(x, 'similarity', 0), reverse=True)
    return candidates


def _calculate_quality_score(book: Book) -> float:
    """Calculate metadata quality score for a book.
    
    Returns score from 0.0 (poor metadata) to 1.0 (excellent metadata).
    """
    score = 0.0
    
    # Description (most important for semantic search)
    if book.description and len(book.description) > 100:
        score += 0.5
    elif book.description:
        score += 0.2
    
    # Categories (genre/topic signal)
    if book.categories and len(book.categories) >= 2:
        score += 0.2
    elif book.categories:
        score += 0.1
    
    # Ratings (credibility signal)
    if book.ratings_count and book.ratings_count > 100:
        score += 0.2
    elif book.ratings_count and book.ratings_count > 10:
        score += 0.1
    
    # Additional metadata
    if book.page_count:
        score += 0.05
    if book.publisher:
        score += 0.05
    
    return min(score, 1.0)


@observe()
def _apply_dislike_penalty(
    db: Session,
    candidates: list[Book],
    disliked_books: list[dict],
) -> list[Book]:
    """Apply penalty to candidates similar to disliked books.
    
    Strategy (Hybrid Approach):
    1. Only activate if user has 2+ strong dislikes (filters outliers)
    2. Only penalize candidates >60% similar to a disliked book
    3. Apply moderate penalty (30% score reduction)
    4. LLM still sees disliked books in context for final decision
    
    Args:
        db: Database session
        candidates: Retrieved candidate books
        disliked_books: Books user rated 1-2 stars
    
    Returns:
        Candidates with dislike penalties applied
    """
    config = DISLIKE_PENALTY_CONFIG
    
    disliked_book_ids = [b['book_id'] for b in disliked_books]
    disliked_books_data = db.query(Book).filter(Book.id.in_(disliked_book_ids)).all()
    
    for candidate in candidates:
        if not candidate.embedding:
            continue
        
        max_similarity = 0
        for disliked in disliked_books_data:
            if not disliked.embedding:
                continue
            similarity = 1 - cosine_distance(candidate.embedding, disliked.embedding)
            max_similarity = max(max_similarity, similarity)
        
        # Only penalize if very similar (> threshold)
        if max_similarity >= config["similarity_threshold"]:
            # Calculate penalty based on how similar it is
            # penalty ranges from 0 (at threshold) to penalty_strength (at 100% similarity)
            penalty_range = max_similarity - config["similarity_threshold"]
            max_range = 1.0 - config["similarity_threshold"]
            penalty = (penalty_range / max_range) * config["penalty_strength"]
            
            # Apply penalty to similarity score
            if hasattr(candidate, 'similarity'):
                candidate.similarity *= (1 - penalty)
            
            # Track that penalty was applied (for observability)
            candidate.dislike_penalty_applied = True
            candidate.dislike_penalty_amount = penalty
    
    # Re-sort after penalties
    candidates.sort(key=lambda x: getattr(x, 'similarity', 0), reverse=True)
    return candidates


@observe()
def _generate_with_llm(
    query: str,
    candidate_books: list[Book],
    user_books: list[dict] | None = None,
) -> list[dict]:
    """Use LLM to select top 3 recommendations with explanations.
    
    The LLM receives:
    - User's query (what they're looking for)
    - User's favorite books (what they've historically enjoyed)
    - User's disliked books (what to AVOID - important!)
    - 20 candidate books (pre-filtered by retrieval)
    
    The LLM's job: Select 3 best matches considering ALL signals
    
    Args:
        query: User's query
        candidate_books: Candidate books from retrieval
        user_books: List of {book_id, title, author, user_rating}
    
    Returns:
        List of dicts with book_id, confidence_score, explanation, rank
    """
    
    # Build rich context for LLM
    context = f"User query: {query}\n\n"
    
    # INJECT USER PREFERENCES INTO PROMPT
    if user_books:
        # Show LLM what the user has loved
        highly_rated = [b for b in user_books if b.get('user_rating', 0) >= 4]
        
        if highly_rated:
            context += "The user particularly loved these books:\n"
            for book in highly_rated[:5]:  # Top 5 favorites
                rating_str = f" (rated {book['user_rating']}/5 stars)" if book.get('user_rating') else ""
                context += f"- {book['title']} by {book['author']}{rating_str}\n"
            context += "\n"
        
        # Show LLM what the user disliked (IMPORTANT: to avoid similar books)
        low_rated = [b for b in user_books if b.get('user_rating', 0) <= 2 and b.get('user_rating', 0) > 0]
        
        if low_rated:
            context += "IMPORTANT - The user did NOT enjoy these books:\n"
            for book in low_rated[:3]:
                rating_str = f" (rated {book['user_rating']}/5 stars)" if book.get('user_rating') else ""
                context += f"- {book['title']} by {book['author']}{rating_str}\n"
            context += "\nAvoid recommending books with similar themes, writing styles, or narrative approaches to these disliked books.\n\n"
    
    # Format candidate books with GLOBAL ratings and quality indicators
    candidates_text = "Candidate books (pre-filtered by semantic similarity and quality):\n"
    for i, book in enumerate(candidate_books, 1):
        candidates_text += f"\n{i}. [{book.id}] {book.title} by {book.author}\n"
        
        if book.description:
            desc = book.description[:200] + "..." if len(book.description) > 200 else book.description
            candidates_text += f"   Description: {desc}\n"
        
        if book.categories:
            candidates_text += f"   Categories: {', '.join(book.categories[:3])}\n"
        
        if book.average_rating:
            candidates_text += f"   Average Rating: {book.average_rating}/5"
            if book.ratings_count:
                candidates_text += f" ({book.ratings_count} ratings)"
            candidates_text += "\n"
        
        if book.page_count:
            candidates_text += f"   Pages: {book.page_count}\n"
        
        if book.publication_year:
            candidates_text += f"   Published: {book.publication_year}\n"
    
    # LLM System Prompt
    system_prompt = """You are an expert book recommendation assistant.

Your task: Select the TOP 3 books that best match:
1. The user's current query (what they're explicitly looking for)
2. The user's reading history (books they've loved vs disliked)

CRITICAL: Pay special attention to books the user disliked. Avoid recommending books with similar themes, writing styles, or narrative approaches.

For each recommendation:
- Use the cosine similarity score as confidence (0-100)
- Write a personalized explanation (2-3 sentences) that:
  * References why it matches their query
  * Connects to books they've loved (if applicable)
  * Explicitly contrasts with books they disliked (if applicable)
  * Explains what makes it a great fit for THIS user

Be specific and personal in your explanations. Make the user feel understood."""
    
    user_prompt = f"""{context}{candidates_text}

Select the top 3 books that best match this user's preferences. Return as JSON:
[
  {{
    "book_id": <id>,
    "confidence_score": <0-100>,
    "explanation": "<personalized explanation>"
  }},
  ...
]"""
    
    # Call LLM with Langfuse tracing
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    
    # Parse and add rank
    result = json.loads(response.choices[0].message.content)
    recommendations = result if isinstance(result, list) else result.get("recommendations", [])
    
    for i, rec in enumerate(recommendations[:3], 1):
        rec["rank"] = i
    
    return recommendations[:3]
```

---

## 6. Enhanced Features

### Feature 1: Enhanced Embedding Text

**Purpose:** Create richer embeddings by including categories, page count, and publication year in addition to title, author, and description.

**Implementation:**
```python
# app/core/embeddings.py

def format_book_text_for_embedding(
    book: Book,
    max_description_length: int = 500
) -> str:
    """Format book metadata into rich text for embedding.
    
    Enhanced format includes:
    - Title and author (identity)
    - Description (semantic content)
    - Categories (genre/topic signals)
    - Publication year (recency)
    - Page count (length preference)
    
    Args:
        book: Book object with metadata
        max_description_length: Maximum description length (token budget)
    
    Returns:
        Formatted text string for embedding
    """
    parts = [f"{book.title} by {book.author}"]
    
    # Description (most important)
    if book.description:
        desc = book.description[:max_description_length]
        if len(book.description) > max_description_length:
            desc += "..."
        parts.append(desc)
    
    # Categories (genre/topic signal)
    if book.categories:
        parts.append(f"Categories: {', '.join(book.categories[:3])}")
    
    # Publication context
    if book.publication_year:
        parts.append(f"Published: {book.publication_year}")
    
    # Page count (length signal)
    if book.page_count:
        length = "short" if book.page_count < 200 else "medium" if book.page_count < 400 else "long"
        parts.append(f"Length: {length} ({book.page_count} pages)")
    
    return ". ".join(parts)
```

**Benefits:**
- Categories normalize genre understanding across sparse descriptions
- Publication year helps with "recent books" queries
- Page count helps with "quick read" vs "epic" preferences
- More robust embeddings when description is missing or short

**Example:**
```python
# Old format:
"The Name of the Wind by Patrick Rothfuss. A tale of magic and adventure..."

# New enhanced format:
"The Name of the Wind by Patrick Rothfuss. A tale of magic and adventure... Categories: Fantasy, Adventure. Published: 2007. Length: long (662 pages)."
```

---

### Feature 2: Dynamic Collaborative Weights

**Purpose:** Adjust collaborative filtering strength based on available signal, rather than using static weights.

**Logic:**
```python
# Relevant favorites found
if len(relevant_favorites) >= 2:
    # Scale from 0.2 (2 books) to 0.5 (5+ books)
    weight = min(0.5, 0.2 + (len(relevant_favorites) - 2) * 0.1)

# No relevant favorites, but has 5★ books
elif len(all_favorites) > 0:
    # Scale from 0.15 (1 book) to 0.3 (5+ books)
    weight = min(0.3, 0.15 + (len(all_favorites) - 1) * 0.05)

# No high ratings, but has some books
elif len(all_books) > 0:
    # Scale from 0.1 (1 book) to 0.2 (10+ books)
    weight = min(0.2, 0.1 + (len(all_books) - 1) * 0.02)

# No CSV
else:
    weight = 0.0
```

**Weight Examples:**
```python
# Scenario 1: 2 relevant favorites
weight = 0.2  # Cautious, limited signal
candidates: 4 collaborative + 16 semantic

# Scenario 2: 5 relevant favorites
weight = 0.5  # Confident, strong signal
candidates: 10 collaborative + 10 semantic

# Scenario 3: 10 relevant favorites
weight = 0.5  # Capped to avoid overfitting
candidates: 10 collaborative + 10 semantic
```

**Benefits:**
- More accurate confidence calibration
- Prevents weak signals from having too much influence
- Prevents strong signals from dominating too much

---

### Feature 3: Metadata Quality Scoring

**Purpose:** Prioritize books with rich metadata (descriptions, categories, ratings) over books with sparse information.

**Scoring Components:**
```python
def _calculate_quality_score(book: Book) -> float:
    """
    Component breakdown:
    - Description (50%): Long = 0.5, Short = 0.2
    - Categories (20%): 2+ = 0.2, 1 = 0.1
    - Ratings (20%): 100+ = 0.2, 10+ = 0.1
    - Other (10%): page_count + publisher = 0.05 each
    """
    score = 0.0
    
    # Description (most important)
    if book.description and len(book.description) > 100:
        score += 0.5  # Rich description
    elif book.description:
        score += 0.2  # Minimal description
    
    # Categories
    if book.categories and len(book.categories) >= 2:
        score += 0.2  # Multiple categories
    elif book.categories:
        score += 0.1  # Single category
    
    # Ratings (credibility)
    if book.ratings_count and book.ratings_count > 100:
        score += 0.2  # Well-reviewed
    elif book.ratings_count and book.ratings_count > 10:
        score += 0.1  # Some reviews
    
    # Additional metadata
    if book.page_count:
        score += 0.05
    if book.publisher:
        score += 0.05
    
    return min(score, 1.0)
```

**Application:**
```python
# Before quality scoring
Book A: similarity = 0.8, description = 500 chars, categories = 3
Book B: similarity = 0.85, description = None, categories = None

# After quality scoring
Book A: quality = 0.9, adjusted_similarity = 0.8 * 0.9 = 0.72
Book B: quality = 0.3, adjusted_similarity = 0.85 * 0.3 = 0.255

# Book A now ranks higher despite lower raw similarity
```

**Benefits:**
- Prevents "empty" books from polluting recommendations
- Ensures users get books with rich information
- Better LLM context (more description = better explanations)

---

### Feature 4: Dislike Penalty System

**Purpose:** Avoid recommending books very similar to books the user disliked, while still allowing LLM final say.

**Strategy (Hybrid Approach):**
1. Only activate if user has 2+ strong dislikes (filters outliers)
2. Only penalize candidates >60% similar to a disliked book
3. Apply moderate penalty (30% score reduction)
4. LLM still sees disliked books in context for final decision

**Configuration:**
```python
DISLIKE_PENALTY_CONFIG = {
    "enabled": True,
    "min_dislikes": 2,           # Need 2+ dislikes to activate
    "similarity_threshold": 0.6,  # Only penalize if >60% similar
    "penalty_strength": 0.3,      # 30% score reduction
}
```

**Penalty Calculation:**
```python
# Example: Candidate is 75% similar to a disliked book
similarity_to_disliked = 0.75
threshold = 0.6
penalty_strength = 0.3

# Calculate penalty
penalty_range = 0.75 - 0.6 = 0.15
max_range = 1.0 - 0.6 = 0.4
penalty = (0.15 / 0.4) * 0.3 = 0.1125

# Apply to similarity score
original_similarity = 0.8
adjusted_similarity = 0.8 * (1 - 0.1125) = 0.71

# Book ranks lower but isn't eliminated
```

**LLM Context Enhancement:**
```python
if low_rated:
    context += "IMPORTANT - The user did NOT enjoy these books:\n"
    for book in low_rated[:3]:
        context += f"- {book['title']} by {book['author']} ({book['user_rating']}/5)\n"
    context += "\nAvoid recommending books with similar themes, writing styles, or narrative approaches.\n\n"
```

**Benefits:**
- Proactive filtering at retrieval stage (reduces bad candidates)
- LLM still has final say (can override if genuinely different)
- Handles edge cases (single dislike = outlier, ignored)
- Moderate penalties (doesn't eliminate potentially good books)

**Example Flow:**
```python
# User disliked "Neuromancer" (1★) and "Foundation" (2★)
# Query: "Hard sci-fi with strong characters"

# Candidate: "Snow Crash" (cyberpunk, 75% similar to Neuromancer)
# → Penalty applied: similarity reduced from 0.8 to 0.71
# → Still in candidate pool, but ranks lower

# Candidate: "Project Hail Mary" (hard sci-fi, 35% similar to Neuromancer)
# → No penalty: similarity < 60% threshold
# → Unaffected by dislike penalty

# LLM sees both candidates plus context about dislikes
# LLM can make informed decision with full context
```

---

## 7. Fallback Strategies

### Fallback Hierarchy (When User Data is Unavailable)

The system gracefully degrades through multiple fallback levels:
```python
# Fallback Level 1: Query-relevant 5★ books (BEST)
if len(relevant_favorites) >= MIN_RELEVANT_BOOKS:
    use_books = relevant_favorites
    collaborative_weight = min(0.5, 0.2 + (len(relevant_favorites) - 2) * 0.1)
    
# Fallback Level 2: All 5★ books (GOOD)
elif len(highly_rated) > 0:
    use_books = highly_rated
    collaborative_weight = min(0.3, 0.15 + (len(highly_rated) - 1) * 0.05)
    
# Fallback Level 3: All books from CSV (ACCEPTABLE)
elif len(user_books) > 0:
    use_books = user_books
    collaborative_weight = min(0.2, 0.1 + (len(user_books) - 1) * 0.02)
    
# Fallback Level 4: No CSV at all (STILL WORKS)
else:
    use_books = []
    collaborative_weight = 0.0  # 100% semantic search
```

### Fallback Scenarios Explained

#### Scenario 1: No CSV Uploaded

**Situation:** User submits query without uploading Goodreads CSV

**Behavior:**
- Pure semantic search (100%)
- Query embedding compared against all 300k+ books
- Enhanced embeddings ensure high-quality matches
- No personalization, but still highly relevant results

**Example:**
```python
query = "Epic fantasy with complex magic systems"
collaborative_weight = 0.0

# → Returns books semantically similar to description
# → Works perfectly, just not personalized to user's taste
# → Quality scoring ensures best books rise to top
```

---

#### Scenario 2: CSV with No High Ratings

**Situation:** User uploaded CSV but rated all books 1-3 stars (no favorites)

**Behavior:**
- Use all books for collaborative filtering (weak weight: 0.1-0.2)
- Semantic search fills majority (80-90%)
- Weak personalization signal, but better than nothing

**Example:**
```python
user_books = [
    {"book_id": 101, "user_rating": 3},
    {"book_id": 102, "user_rating": 2},
    {"book_id": 103, "user_rating": 3}
]

collaborative_weight = min(0.2, 0.1 + (3 - 1) * 0.02) = 0.14

# → 14% collaborative (3 books) + 86% semantic
# → Primarily relies on query, uses CSV as weak signal
```

---

#### Scenario 3: CSV with High Ratings, None Relevant to Query

**Situation:** User has 15 coding books rated 5★, asks for fantasy recommendation

**Behavior:**
- Semantic filtering finds no relevant 5★ books (similarity < 0.3)
- Falls back to using all 5★ books (moderate weight: 0.15-0.3)
- Still gets collaborative signal (general quality preferences)

**Example:**
```python
query = "Epic fantasy with magic"
user_5_star_books = [
    {"book_id": 201, "title": "Clean Code", "user_rating": 5},
    {"book_id": 202, "title": "Design Patterns", "user_rating": 5},
    # ... 13 more coding books
]

# Semantic filter: No relevant favorites (coding ≠ fantasy)
relevant_favorites = []

# Fallback: Use all 5★ books with lower weight
collaborative_weight = min(0.3, 0.15 + (15 - 1) * 0.05) = 0.3

# → 30% collaborative (all 5★ coding books) + 70% semantic (fantasy query)
# → Benefits from user's general taste (well-written, structured narratives)
# → Quality scoring ensures best fantasy books still rise to top
```

---

#### Scenario 4: CSV with Relevant High Ratings (IDEAL)

**Situation:** User has 5 fantasy books rated 5★, asks for fantasy recommendation

**Behavior:**
- Semantic filtering finds relevant 5★ books (similarity ≥ 0.3)
- Strong collaborative signal (weight: 0.2-0.5)
- Highly personalized recommendations

**Example:**
```python
query = "Epic fantasy with magic"
user_5_star_books = [
    {"book_id": 301, "title": "The Name of the Wind", "user_rating": 5},
    {"book_id": 302, "title": "Mistborn", "user_rating": 5},
    {"book_id": 303, "title": "The Way of Kings", "user_rating": 5},
    # ... + 2 more fantasy books
]

# Semantic filter: 5 relevant favorites (all fantasy books)
relevant_favorites = [301, 302, 303, 304, 305]

# Dynamic weight calculation
collaborative_weight = min(0.5, 0.2 + (5 - 2) * 0.1) = 0.5

# → 50% collaborative (fantasy favorites) + 50% semantic (query)
# → Highly personalized: "books like your fantasy favorites"
# → Quality scoring + dislike penalties refine results further
```

---

### Visual Representation of Fallbacks
```
┌──────────────────────────────────────────────────────────────────┐
│ RECOMMENDATION STRATEGY DECISION TREE                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User uploaded CSV?                                              │
│  ├─ NO  → Pure Semantic Search (weight=0.0)                     │
│  │        ✓ Still works perfectly (enhanced embeddings)         │
│  │        ✓ Quality scoring ensures best books                  │
│  │        ✗ No personalization                                  │
│  │                                                               │
│  └─ YES → User has 4-5★ books?                                  │
│      ├─ NO  → Use all books (weight=0.1-0.2)                   │
│      │        ✓ Weak personalization                            │
│      │        ✓ Better than nothing                             │
│      │                                                           │
│      └─ YES → Query-relevant 5★ books exist?                    │
│          ├─ NO  → Use all 5★ (weight=0.15-0.3)                 │
│          │        ✓ Moderate personalization                    │
│          │        ✓ General taste preferences                   │
│          │        ✓ Quality scoring prioritizes best            │
│          │                                                       │
│          └─ YES → Use relevant 5★ (weight=0.2-0.5)             │
│                   ✓ Strong personalization (BEST)               │
│                   ✓ Dynamic weight based on count               │
│                   ✓ Quality scoring + dislike penalties         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. Configuration Parameters

### Core Configuration
```python
# app/services/recommendation_engine.py

# Semantic Filtering
SIMILARITY_THRESHOLD = 0.3  # 30% cosine similarity for relevance
MIN_RELEVANT_BOOKS = 2      # Minimum relevant 5★ books to use filtering

# Rating Thresholds
HIGH_RATING_THRESHOLD = 4   # Books rated 4-5 stars
LOW_RATING_THRESHOLD = 2    # Books rated 1-2 stars (dislikes)

# Retrieval Configuration
TOP_K_CANDIDATES = 20       # Total candidates to retrieve

# Embedding Configuration
MAX_DESCRIPTION_LENGTH = 500  # Max chars for description in embedding

# Dislike Penalty System
DISLIKE_PENALTY_CONFIG = {
    "enabled": True,
    "min_dislikes": 2,           # Need 2+ dislikes to activate
    "similarity_threshold": 0.6,  # Only penalize if >60% similar
    "penalty_strength": 0.3,      # 30% score reduction
}
```

### Threshold Explanations

#### `SIMILARITY_THRESHOLD = 0.3`
- **Purpose:** Determine if a user's 5★ book is relevant to their current query
- **Range:** 0.0 (no similarity) to 1.0 (identical)
- **Recommended:** 0.3 (moderate)
- **Effects:**
  - Higher (0.4-0.5): Stricter filtering, fewer relevant books found
  - Lower (0.2): More lenient, might include loosely related books

---

#### `MIN_RELEVANT_BOOKS = 2`
- **Purpose:** Minimum number of relevant 5★ books to use semantic filtering
- **Rationale:** Need sufficient signal for reliable collaborative filtering
- **Effects:**
  - Higher (3-5): More conservative, falls back more often
  - Lower (1): More aggressive, uses single relevant book as signal

---

#### `DISLIKE_PENALTY_CONFIG`

**`min_dislikes = 2`:**
- Single dislike might be an outlier
- Need multiple dislikes to establish pattern

**`similarity_threshold = 0.6`:**
- Only penalize very similar books (>60%)
- Moderately similar books (40-60%) unaffected

**`penalty_strength = 0.3`:**
- Reduces score by up to 30%
- Doesn't eliminate books entirely (LLM has final say)

---

### Dynamic Collaborative Weight Examples
```python
# Example 1: 2 relevant favorites
relevant_favorites = 2
weight = 0.2 + (2 - 2) * 0.1 = 0.2
# → 20% collaborative, 80% semantic

# Example 2: 5 relevant favorites
relevant_favorites = 5
weight = 0.2 + (5 - 2) * 0.1 = 0.5
# → 50% collaborative, 50% semantic

# Example 3: 10 relevant favorites (capped)
relevant_favorites = 10
weight = min(0.5, 0.2 + (10 - 2) * 0.1) = 0.5
# → 50% collaborative, 50% semantic (capped)
```

---

### Tuning Guide

**If recommendations are too narrow (not diverse enough):**
- ✅ Decrease `SIMILARITY_THRESHOLD` (0.3 → 0.2)
- ✅ Decrease `MIN_RELEVANT_BOOKS` (2 → 1)
- ✅ Increase `TOP_K_CANDIDATES` (20 → 30)
- ✅ Disable dislike penalty temporarily

**If recommendations are not personalized enough:**
- ✅ Increase collaborative weight caps (0.5 → 0.6)
- ✅ Decrease semantic dominance
- ✅ Lower `MIN_RELEVANT_BOOKS` (2 → 1)

**If recommendations include unrelated books:**
- ✅ Increase `SIMILARITY_THRESHOLD` (0.3 → 0.4)
- ✅ Increase `MIN_RELEVANT_BOOKS` (2 → 3)
- ✅ Increase quality score thresholds

**If recommendations avoid good books similar to dislikes:**
- ✅ Increase `similarity_threshold` in dislike config (0.6 → 0.7)
- ✅ Decrease `penalty_strength` (0.3 → 0.2)
- ✅ Rely more on LLM context

---

## 9. Data Utilization Summary

### Global Book Metadata (PostgreSQL `books` Table)

**Source:** Google Books API + Open Library  
**Shared Across:** All users  
**Used For:**

1. **Enhanced Embedding Generation**
```python
   book_text = format_book_text_for_embedding(book)
   # "Title by Author. Description. Categories: X, Y. Published: 2020. Length: medium (320 pages)."
   embedding = create_embedding(book_text)
```
   - Enables semantic search with richer context
   - Categories normalize genre understanding
   - Publication year helps with recency preferences

2. **Vector Search**
```sql
   SELECT * FROM books 
   ORDER BY embedding <=> query_embedding::vector
   LIMIT 20;
```
   - Find semantically similar books
   - Enhanced embeddings improve match quality

3. **Quality Scoring**
   - Description length → metadata richness
   - Categories count → genre clarity
   - Ratings count → credibility
   - Quality-adjusted ranking prioritizes best books

4. **Display & Context**
   - `cover_url`: Book covers in UI
   - `categories`: Show genre tags
   - `page_count`: "Medium-length book (320 pages)"
   - `average_rating`: "Highly-rated (4.5 stars)"

5. **LLM Context**
   - Description helps LLM understand book content
   - Categories help match to user preferences
   - Global ratings provide quality signal
   - Publication year helps with recency requests

**Limitations:**
- No personalization without user data
- Same recommendations for everyone with identical query
- Quality scoring helps but doesn't replace personalization

---

### User-Specific Data (Redis Session)

**Source:** Goodreads CSV  
**Scoped To:** Single session (1 hour TTL)  
**Used For:**

1. **Dynamic Collaborative Filtering**
```python
   highly_rated = [b for b in user_books if b['user_rating'] >= 4]
   weight = min(0.5, 0.2 + (len(highly_rated) - 2) * 0.1)
   similar_books = search_similar_to_books(highly_rated, weight=weight)
```
   - Find books similar to user's favorites
   - Weight adjusts based on signal strength
   - More favorites = higher confidence

2. **Semantic Filtering**
```python
   relevant_favorites = filter_by_similarity(
       user_favorites, 
       query_embedding, 
       threshold=0.3
   )
```
   - Only use favorites relevant to query
   - Prevents unrelated 5★ books from dominating
   - Falls back gracefully if no relevant books

3. **Dislike Penalty**
```python
   if len(strong_dislikes) >= 2:
       apply_dislike_penalty(candidates, strong_dislikes)
```
   - Penalize candidates similar to dislikes
   - Moderate penalty (doesn't eliminate)
   - Requires 2+ dislikes to activate

4. **LLM Personalization**
```
   "User loved: Project Hail Mary (5★), The Expanse (4★)
    User disliked: Foundation (2★)
    
    Recommend books that match their taste, avoid similar to dislikes..."
```
   - LLM references user's history in explanations
   - Makes recommendations feel personal
   - Explains why book matches user's taste

5. **Exclusion List**
```python
   exclude_ids = [book['book_id'] for book in user_books]
```
   - Don't recommend books user has already read

**Benefits:**
- Highly personalized recommendations
- Dynamic adaptation to signal strength
- Considers both likes and dislikes
- No persistent storage needed

---

## 10. Example: End-to-End Flow

### Scenario: User with Diverse Reading History

**Input:**
```json
{
  "query": "I want a character-driven sci-fi book with humor",
  "user_books": [
    // Sci-fi favorites (relevant to query)
    {"book_id": 101, "title": "The Martian", "user_rating": 5},
    {"book_id": 102, "title": "Project Hail Mary", "user_rating": 5},
    
    // Other favorites (not relevant to query)
    {"book_id": 201, "title": "Sapiens", "user_rating": 5},
    {"book_id": 202, "title": "Atomic Habits", "user_rating": 5},
    
    // Disliked books
    {"book_id": 103, "title": "Neuromancer", "user_rating": 2},
    {"book_id": 104, "title": "Foundation", "user_rating": 1}
  ]
}
```

---

### Step 1: Semantic Filtering
```python
query_embedding = create_embedding(
    "character-driven sci-fi book with humor"
)

# Check each 5★ book for relevance
for book in user_5_star_books:
    similarity = cosine_similarity(query_embedding, book.embedding)
    
# Results (enhanced embeddings improve matching):
# - The Martian: similarity = 0.82 ✅ (relevant - sci-fi + humor)
# - Project Hail Mary: similarity = 0.85 ✅ (relevant - sci-fi + humor)
# - Sapiens: similarity = 0.18 ❌ (not relevant - non-fiction)
# - Atomic Habits: similarity = 0.12 ❌ (not relevant - self-help)

relevant_favorites = [101, 102]  # Only sci-fi books
```

**Dynamic Weight Calculation:**
```python
len(relevant_favorites) = 2
collaborative_weight = 0.2 + (2 - 2) * 0.1 = 0.2

# → 20% collaborative (2 books = cautious)
# → 80% semantic (rely more on query)
```

---

### Step 2: Hybrid Retrieval
```python
# Collaborative: Books similar to The Martian & Project Hail Mary (20%)
collaborative_candidates = search_similar_to_books([101, 102], limit=4)
# Results: [305, 306, 307, 308]

# Semantic: Books matching query description (80%)
semantic_candidates = search_similar_books(query_embedding, limit=16)
# Results: [401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416]

# Combine (exclude user's books: 101, 102, 103, 104, 201, 202)
all_candidates = collaborative_candidates + semantic_candidates
# Results: 20 candidate books (deduplicated, sorted by similarity)
```

---

### Step 3: Quality Scoring
```python
for candidate in all_candidates:
    quality_score = calculate_quality_score(candidate)
    candidate.similarity *= quality_score

# Example adjustments:
# Book A: similarity=0.8, quality=0.9 → adjusted=0.72
# Book B: similarity=0.85, quality=0.3 → adjusted=0.255
# Book A now ranks higher despite lower raw similarity
```

---

### Step 4: Dislike Penalty
```python
strong_dislikes = [
    {"book_id": 103, "title": "Neuromancer", "user_rating": 2},
    {"book_id": 104, "title": "Foundation", "user_rating": 1}
]

# Penalty activated (2 dislikes >= min_dislikes)

for candidate in all_candidates:
    max_similarity = max(
        similarity_to(candidate, Neuromancer),
        similarity_to(candidate, Foundation)
    )
    
    if max_similarity >= 0.6:  # Threshold
        penalty = calculate_penalty(max_similarity)
        candidate.similarity *= (1 - penalty)

# Example:
# "Snow Crash" (cyberpunk): 72% similar to Neuromancer
# → Penalty applied: similarity reduced by 18%
# → Still in pool, but ranks lower

# "A Long Way to a Small, Angry Planet": 25% similar to Neuromancer
# → No penalty (< 60% threshold)
```

---

### Step 5: LLM Generation

**LLM Input:**
```
User query: "character-driven sci-fi book with humor"

User loved:
- The Martian (5/5 stars)
- Project Hail Mary (5/5 stars)

IMPORTANT - User did NOT enjoy:
- Neuromancer (2/5 stars)
- Foundation (1/5 stars)

Avoid books with similar themes, writing styles, or narrative approaches.

Candidates:
1. [305] A Long Way to a Small, Angry Planet by Becky Chambers
   Description: Character-focused space opera about diverse crew...
   Categories: Science Fiction, Character Study
   Average Rating: 4.1/5 (8,200 ratings)
   Pages: 518
   Published: 2014
   Quality Score: 0.9

2. [401] Hitchhiker's Guide to the Galaxy by Douglas Adams
   Description: Comedic science fiction following Arthur Dent...
   Categories: Science Fiction, Comedy
   Average Rating: 4.2/5 (15,600 ratings)
   Pages: 224
   Published: 1979
   Quality Score: 0.95

...
```

**LLM Output:**
```json
[
  {
    "book_id": 305,
    "confidence_score": 93,
    "explanation": "Like The Martian and Project Hail Mary, Becky Chambers balances hard sci-fi with deeply human characters and optimistic humor. The crew's interpersonal dynamics and problem-solving mirror what you loved in Andy Weir's work. Unlike the dense, cyberpunk style of Neuromancer, this offers accessible character-driven storytelling with warmth.",
    "rank": 1
  },
  {
    "book_id": 401,
    "confidence_score": 89,
    "explanation": "Douglas Adams' signature humor and character-driven storytelling match your preferences perfectly. While more absurdist than The Martian's grounded comedy, the wit and clever problem-solving will feel familiar. This avoids the slow-paced, philosophical approach of Foundation in favor of fast-paced adventure.",
    "rank": 2
  },
  {
    "book_id": 402,
    "confidence_score": 85,
    "explanation": "This book combines the survival elements you enjoyed in The Martian with rich character development and laugh-out-loud moments. The protagonist's humor under pressure and scientific approach align with your taste, while offering emotional depth. Far more accessible than Neuromancer's dense prose.",
    "rank": 3
  }
]
```

---

### Key Insights from This Example

1. **Semantic filtering worked:** Only used relevant 5★ books (sci-fi), ignored unrelated ones (non-fiction)
2. **Dynamic weight appropriate:** 2 favorites = 0.2 weight (cautious, limited signal)
3. **Quality scoring refined results:** High-quality books ranked higher
4. **Dislike penalty applied:** Books similar to Neuromancer/Foundation penalized
5. **LLM was highly personalized:** Explanations referenced specific books user loved AND explicitly contrasted with dislikes
6. **Enhanced embeddings improved matching:** Categories + publication year helped find better semantic matches

---

## 11. Key Design Principles

### 1. Separation of Concerns

**Global Book Data (PostgreSQL)**
- Shared across all users
- Permanent storage
- High-quality metadata from Google Books API
- Enhanced embeddings for better semantic search

**User Reading Data (Redis)**
- Session-scoped (1 hour TTL)
- User-specific preferences
- Enables collaborative filtering
- No persistent user accounts needed

---

### 2. No User Data Pollution

❌ **WRONG: Storing user ratings in books table**
```sql
CREATE TABLE books (
  ...
  user_rating INTEGER  -- Which user? This breaks multi-user systems
);
```

✅ **CORRECT: User ratings in session**
```json
{
  "session": {
    "books_from_csv": [
      {"book_id": 101, "user_rating": 5}  // User A's rating
    ]
  }
}
```

**Rationale:** User ratings are **relational data** (user ↔ book), not book properties.

---

### 3. Hybrid Recommendation Strategy

Combines five complementary signals:

1. **Semantic Understanding** (from enhanced embeddings)
   - "Find books about X with Y characteristics"
   - Works without user data (cold start solved)
   - Enhanced with categories, page count, publication year

2. **Collaborative Filtering** (from user ratings)
   - "Find books similar to what I loved"
   - Personalizes recommendations
   - Dynamically weighted based on signal strength

3. **Semantic Filtering** (hybrid approach)
   - "Only use favorites relevant to current query"
   - Prevents unrelated favorites from dominating
   - Graceful fallback if no relevant books

4. **Quality Scoring** (metadata richness)
   - "Prioritize books with rich information"
   - Ensures high-quality recommendations
   - Prevents sparse metadata from polluting results

5. **Dislike Avoidance** (penalty system)
   - "Avoid books similar to what I disliked"
   - Moderate penalties (doesn't eliminate)
   - LLM has final say with full context

**Best results:** All five signals work together

---

### 4. Graceful Degradation

System never fails, just adapts:
- ✅ Has relevant 5★ books → Strong personalization (dynamic weight: 0.2-0.5)
- ✅ Has any 5★ books → Moderate personalization (dynamic weight: 0.15-0.3)
- ✅ Has any books → Weak personalization (dynamic weight: 0.1-0.2)
- ✅ No CSV → Pure semantic search (still excellent results with enhanced embeddings)

Each level maintains quality through:
- Enhanced embeddings (better semantic matching)
- Quality scoring (prioritizes rich metadata)
- LLM generation (intelligent final selection)

---

### 5. Privacy-Friendly Architecture

- No persistent user accounts
- No long-term user data storage
- Sessions expire after 1 hour
- User data automatically purged
- GDPR-friendly by design

---

### 6. Adaptive Confidence

- Dynamic collaborative weights adjust to signal strength
- Quality scoring ensures metadata richness
- Dislike penalties scale with similarity
- System calibrates confidence based on available data

---

## 12. Migration Guide

### Alembic Migration: Add Rich Metadata to Books Table
```python
# backend/alembic/versions/002_enrich_books_metadata.py
"""Enrich books table with Google Books metadata

Revision ID: 002_enrich_books
Revises: 001_initial
Create Date: 2024-12-08
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002_enrich_books'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rich metadata columns to books table."""
    
    # Add new columns
    op.add_column('books', sa.Column('isbn13', sa.String(20), nullable=True))
    op.add_column('books', sa.Column('page_count', sa.Integer(), nullable=True))
    op.add_column('books', sa.Column('publisher', sa.Text(), nullable=True))
    op.add_column('books', sa.Column('publication_year', sa.Integer(), nullable=True))
    op.add_column('books', sa.Column('average_rating', sa.DECIMAL(3, 2), nullable=True))
    op.add_column('books', sa.Column('ratings_count', sa.Integer(), nullable=True))
    op.add_column('books', sa.Column('language', sa.String(10), nullable=True))
    op.add_column('books', sa.Column('data_source', sa.String(50), nullable=True))
    op.add_column('books', sa.Column('updated_at', sa.TIMESTAMP(), 
                                      server_default=sa.text('now()'), 
                                      nullable=False))
    
    # Create indexes
    op.create_index('idx_books_isbn13', 'books', ['isbn13'])
    op.create_index('idx_books_publication_year', 'books', ['publication_year'])
    
    # Create GIN index for array search on categories
    op.execute('CREATE INDEX idx_books_categories ON books USING GIN(categories)')
    
    print("✅ Migration complete: Books table enriched with metadata")


def downgrade() -> None:
    """Remove rich metadata columns from books table."""
    
    # Drop indexes
    op.drop_index('idx_books_categories', table_name='books')
    op.drop_index('idx_books_publication_year', table_name='books')
    op.drop_index('idx_books_isbn13', table_name='books')
    
    # Drop columns
    op.drop_column('books', 'updated_at')
    op.drop_column('books', 'data_source')
    op.drop_column('books', 'language')
    op.drop_column('books', 'ratings_count')
    op.drop_column('books', 'average_rating')
    op.drop_column('books', 'publication_year')
    op.drop_column('books', 'publisher')
    op.drop_column('books', 'page_count')
    op.drop_column('books', 'isbn13')
```

### Running the Migration
```bash
cd backend

# Generate migration (verify it matches above)
alembic revision --autogenerate -m "Enrich books metadata"

# Apply migration
alembic upgrade head

# Verify
alembic current
```

---

## 13. Implementation Checklist

### Phase 1: Database Schema

- [ ] Run migration to add new columns to `books` table
- [ ] Verify indexes created (isbn13, categories, publication_year)
- [ ] Update `Book` model in `app/models/database.py`
- [ ] Test database connectivity with new schema

---

### Phase 2: Enhanced Embeddings

- [ ] Implement `format_book_text_for_embedding()` in `app/core/embeddings.py`
- [ ] Include title, author, description, categories, year, page_count
- [ ] Add token budget limit (max_description_length=500)
- [ ] Test embedding generation with various metadata completeness levels
- [ ] Regenerate embeddings for existing books (if applicable)

---

### Phase 3: Google Books API Integration

- [ ] Create `app/services/google_books_api.py`
- [ ] Implement `fetch_from_google_books(isbn)` function
- [ ] Extract all metadata fields (description, categories, pageCount, etc.)
- [ ] Implement helper functions (`extract_isbn13()`, `extract_year()`)
- [ ] Handle API errors (not found, rate limits, invalid ISBN)
- [ ] Implement exponential backoff for rate limiting
- [ ] Test with various ISBNs (valid, invalid, missing data)

---

### Phase 4: CSV Processing

- [ ] Update `app/workers/tasks.py`
- [ ] Extract `My Rating` from CSV (user-specific field)
- [ ] Store `books_from_csv` with structure: `{book_id, title, author, user_rating}`
- [ ] Handle missing ratings gracefully (user_rating = None)
- [ ] Use enhanced embedding format for new books
- [ ] Test with CSVs of varying sizes (10, 100, 1000 books)
- [ ] Test with CSVs missing ratings column
- [ ] Verify user ratings stored in Redis, NOT in books table

---

### Phase 5: Quality Scoring System

- [ ] Implement `_calculate_quality_score()` in `recommendation_engine.py`
- [ ] Score components: description (50%), categories (20%), ratings (20%), other (10%)
- [ ] Implement `_apply_quality_scoring()` to adjust candidate rankings
- [ ] Test with books of varying metadata completeness
- [ ] Verify high-quality books rank higher than sparse ones

---

### Phase 6: Dynamic Collaborative Weights

- [ ] Implement dynamic weight calculation in `_retrieve_candidates()`
- [ ] Scale weight based on number of relevant favorites (0.2 to 0.5)
- [ ] Scale weight based on all favorites (0.15 to 0.3)
- [ ] Scale weight based on all books (0.1 to 0.2)
- [ ] Test with different numbers of user books (1, 3, 5, 10, 20)
- [ ] Verify weights adjust appropriately

---

### Phase 7: Semantic Filtering

- [ ] Implement `_filter_relevant_books()` in `recommendation_engine.py`
- [ ] Compute cosine similarity between query and user's 5★ books
- [ ] Apply similarity threshold (default: 0.3)
- [ ] Return only contextually relevant favorites
- [ ] Test scenarios:
  - [ ] User asks for fantasy, has fantasy 5★ books (should pass filter)
  - [ ] User asks for fantasy, has coding 5★ books (should fail filter)
  - [ ] User asks for "books like X", has X rated 5★ (should pass)

---

### Phase 8: Dislike Penalty System

- [ ] Implement `_apply_dislike_penalty()` in `recommendation_engine.py`
- [ ] Check for minimum dislikes (default: 2)
- [ ] Calculate similarity to each disliked book
- [ ] Apply penalty only if similarity > threshold (default: 0.6)
- [ ] Scale penalty based on similarity (up to penalty_strength=0.3)
- [ ] Test scenarios:
  - [ ] Single dislike (should not activate)
  - [ ] Two dislikes (should activate)
  - [ ] Candidate 70% similar to dislike (should penalize)
  - [ ] Candidate 40% similar to dislike (should not penalize)

---

### Phase 9: LLM Generation Enhancement

- [ ] Update `_generate_with_llm()` prompt with user preferences
- [ ] Include highly-rated books in context
- [ ] Include low-rated books as "IMPORTANT - avoid similar" signal
- [ ] Test LLM explanations reference user's history
- [ ] Verify explanations contrast with dislikes when applicable
- [ ] Verify personalization improves with user data

---

### Phase 10: Configuration & Tuning

- [ ] Add all configuration parameters to `recommendation_engine.py`
- [ ] Document threshold values and their effects
- [ ] Create tuning guide for adjusting thresholds
- [ ] Test with different threshold values
- [ ] Establish baseline performance metrics
- [ ] Document recommended configurations for different use cases

---

### Phase 11: Testing

**Unit Tests:**
- [ ] Test `format_book_text_for_embedding()` with various metadata
- [ ] Test `_calculate_quality_score()` with different completeness levels
- [ ] Test `_filter_relevant_books()` with various similarities
- [ ] Test `_apply_dislike_penalty()` with various scenarios
- [ ] Test dynamic weight calculations
- [ ] Test fallback logic in `_retrieve_candidates()`

**Integration Tests:**
- [ ] Test full recommendation flow without CSV
- [ ] Test full recommendation flow with CSV
- [ ] Test with CSV containing only high ratings
- [ ] Test with CSV containing only low ratings
- [ ] Test with diverse reading history (multiple genres)
- [ ] Test with narrow reading history (single genre)
- [ ] Test with user who rates everything 5 stars
- [ ] Test with user who rates everything 2-3 stars

**Performance Tests:**
- [ ] Measure vector search latency (should be <500ms)
- [ ] Measure quality scoring overhead (should be <50ms)
- [ ] Measure dislike penalty overhead (should be <100ms)
- [ ] Measure end-to-end recommendation time (should be <5s)
- [ ] Test with 100+ books in CSV
- [ ] Test concurrent requests

---

### Phase 12: Observability

- [ ] Verify Langfuse traces capture all enhancement steps
- [ ] Log quality scores for observability
- [ ] Log fallback decisions (which level was used)
- [ ] Track collaborative weight used per request
- [ ] Monitor similarity scores distribution
- [ ] Add metrics for:
  - [ ] % of requests with CSV
  - [ ] % using relevant favorites vs all favorites
  - [ ] Average quality score of recommendations
  - [ ] % of requests with dislike penalties applied
  - [ ] Average dislike penalty amount

---

### Phase 13: Documentation

- [ ] Update PRODUCT.md with new data architecture
- [ ] Document all enhanced features
- [ ] Document fallback strategies
- [ ] Create configuration tuning guide
- [ ] Add examples for each enhancement
- [ ] Update API documentation

---

## Appendix A: Helper Functions

### Google Books API Integration
```python
# app/services/google_books_api.py
import requests
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def fetch_from_google_books(isbn: str) -> dict | None:
    """Fetch book metadata from Google Books API.
    
    Args:
        isbn: Book ISBN (10 or 13 digits)
    
    Returns:
        Dictionary with volumeInfo data, or None if not found
    """
    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": f"isbn:{isbn}",
                "key": settings.google_books_api_key
            },
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"Google Books API error: {response.status_code}")
            return None
        
        data = response.json()
        
        if not data.get('items'):
            logger.warning(f"No results found for ISBN: {isbn}")
            return None
        
        # Extract volumeInfo (first result)
        volume_info = data['items'][0]['volumeInfo']
        return volume_info
        
    except requests.RequestException as e:
        logger.error(f"Google Books API request failed: {e}")
        return None


def extract_isbn13(volume_info: dict) -> str | None:
    """Extract ISBN-13 from volume info."""
    identifiers = volume_info.get('industryIdentifiers', [])
    for identifier in identifiers:
        if identifier.get('type') == 'ISBN_13':
            return identifier.get('identifier')
    return None


def extract_year(published_date: str | None) -> int | None:
    """Extract year from publishedDate string.
    
    Args:
        published_date: Date string (formats: "2018", "2018-10", "2018-10-16")
    
    Returns:
        Year as integer, or None if invalid
    """
    if not published_date:
        return None
    try:
        return int(published_date.split('-')[0])
    except (ValueError, IndexError):
        return None
```

---

### Enhanced Embedding Utility
```python
# app/core/embeddings.py
from typing import List
from langfuse.openai import OpenAI
from app.config import get_settings
from app.models.database import Book

settings = get_settings()
openai_client = OpenAI(api_key=settings.openai_api_key)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_DESCRIPTION_LENGTH = 500  # Token budget


def format_book_text_for_embedding(
    book: Book,
    max_description_length: int = MAX_DESCRIPTION_LENGTH
) -> str:
    """Format book metadata into rich text for embedding.
    
    Enhanced format includes:
    - Title and author (identity)
    - Description (semantic content)
    - Categories (genre/topic signals)
    - Publication year (recency)
    - Page count (length preference)
    
    Args:
        book: Book object with metadata
        max_description_length: Maximum description length (token budget)
    
    Returns:
        Formatted text string for embedding
    """
    parts = [f"{book.title} by {book.author}"]
    
    # Description (most important)
    if book.description:
        desc = book.description[:max_description_length]
        if len(book.description) > max_description_length:
            desc += "..."
        parts.append(desc)
    
    # Categories (genre/topic signal)
    if book.categories:
        parts.append(f"Categories: {', '.join(book.categories[:3])}")
    
    # Publication context
    if book.publication_year:
        parts.append(f"Published: {book.publication_year}")
    
    # Page count (length signal)
    if book.page_count:
        if book.page_count < 200:
            length = "short"
        elif book.page_count < 400:
            length = "medium"
        else:
            length = "long"
        parts.append(f"Length: {length} ({book.page_count} pages)")
    
    return ". ".join(parts)


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
```

---

## Appendix B: Configuration Reference

### Complete Configuration File
```python
# app/services/recommendation_engine.py - Configuration Section

# ============================================================================
# CORE CONFIGURATION
# ============================================================================

# Semantic Filtering
SIMILARITY_THRESHOLD = 0.3  # 30% cosine similarity for relevance
MIN_RELEVANT_BOOKS = 2      # Minimum relevant 5★ books to use filtering

# Rating Thresholds
HIGH_RATING_THRESHOLD = 4   # Books rated 4-5 stars
LOW_RATING_THRESHOLD = 2    # Books rated 1-2 stars (dislikes)

# Retrieval Configuration
TOP_K_CANDIDATES = 20       # Total candidates to retrieve

# Embedding Configuration
MAX_DESCRIPTION_LENGTH = 500  # Max chars for description in embedding

# ============================================================================
# DISLIKE PENALTY SYSTEM
# ============================================================================

DISLIKE_PENALTY_CONFIG = {
    "enabled": True,              # Enable/disable penalty system
    "min_dislikes": 2,           # Minimum dislikes to activate (filters outliers)
    "similarity_threshold": 0.6,  # Only penalize if >60% similar
    "penalty_strength": 0.3,      # 30% score reduction (moderate)
}

# ============================================================================
# QUALITY SCORING WEIGHTS
# ============================================================================

QUALITY_SCORE_WEIGHTS = {
    "description_long": 0.5,    # Description > 100 chars
    "description_short": 0.2,   # Description present but short
    "categories_multiple": 0.2, # 2+ categories
    "categories_single": 0.1,   # 1 category
    "ratings_high": 0.2,        # 100+ ratings
    "ratings_medium": 0.1,      # 10+ ratings
    "page_count": 0.05,         # Page count present
    "publisher": 0.05,          # Publisher present
}

# ============================================================================
# DYNAMIC WEIGHT BOUNDS
# ============================================================================

# Relevant favorites (query-contextual)
RELEVANT_FAVORITES_MIN_WEIGHT = 0.2  # 2 books
RELEVANT_FAVORITES_MAX_WEIGHT = 0.5  # 5+ books
RELEVANT_FAVORITES_INCREMENT = 0.1   # Per additional book

# All favorites (fallback)
ALL_FAVORITES_MIN_WEIGHT = 0.15      # 1 book
ALL_FAVORITES_MAX_WEIGHT = 0.3       # 5+ books
ALL_FAVORITES_INCREMENT = 0.05       # Per additional book

# All books (weak signal)
ALL_BOOKS_MIN_WEIGHT = 0.1           # 1 book
ALL_BOOKS_MAX_WEIGHT = 0.2           # 10+ books
ALL_BOOKS_INCREMENT = 0.02           # Per additional book
```

---

## Conclusion

This architecture achieves:

✅ **Clean separation:** Global book data vs user preferences  
✅ **Enhanced embeddings:** Rich semantic understanding with categories, page count, and year  
✅ **Dynamic personalization:** Collaborative weights adjust to signal strength  
✅ **Quality-aware ranking:** Prioritizes books with rich metadata  
✅ **Intelligent dislike avoidance:** Penalizes similar books while allowing LLM final say  
✅ **Graceful degradation:** Works perfectly without user data, improves with it  
✅ **Privacy-friendly:** User data expires after 1 hour  

**Key Insight:** By combining enhanced embeddings, dynamic weighting, quality scoring, and dislike penalties, we achieve highly personalized recommendations that adapt to available signal strength while maintaining high quality and user satisfaction.

---

**Document Version:** 3.0  
**Last Updated:** December 8, 2024  
**Status:** Ready for Implementation with Enhanced Features

**Changes from v2.0:**
- Added enhanced embedding text (categories, page count, publication year)
- Added dynamic collaborative weights (scales based on signal strength)
- Added metadata quality scoring system
- Added dislike penalty system (hybrid approach with LLM context)
- Updated all code examples and implementation checklist
- Added comprehensive configuration reference