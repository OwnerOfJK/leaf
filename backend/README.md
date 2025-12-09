# Leaf Backend

FastAPI backend for the Leaf book recommendation system.

**Status:** Production-ready (v2.0.0) - Advanced RAG pipeline with personalization features

**Key Features:**
- **Advanced RAG Pipeline** with quality scoring, semantic filtering, and dislike penalties
- **Dynamic Collaborative Filtering** that adapts based on query relevance
- **Async CSV Processing** for Goodreads library imports via Celery
- **Google Books API Integration** with rate limiting and metadata enrichment
- **Full Langfuse Observability** with hierarchical tracing and user feedback
- **Redis Session Management** with 1-hour TTL
- **Comprehensive Test Coverage** (unit + integration tests)

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `.env` with your actual credentials (database is pre-configured for local Docker):

```bash
# Database and Redis are already configured for docker-compose
# Update these with your API keys:
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
GOOGLE_BOOKS_API_KEY=AIza...
```

### 3. Start Infrastructure

```bash
# From project root
cd ..
docker-compose up -d
```

This starts:
- PostgreSQL 16 with pgvector extension (port 5432)
- Redis 7 (port 6379)

### 4. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

### 5. Start Development Server

```bash
uvicorn main:app --reload
```

**Server will be available at:**
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

### 6. Start Celery Worker (For CSV Upload Feature)

```bash
# In a separate terminal
celery -A app.workers.celery_app worker --loglevel=info
```

This worker processes CSV uploads asynchronously. Without it, CSV upload functionality will queue tasks but not process them.

## Testing the Backend

**Prerequisites**: Make sure all services are running (see [Quick Start](#quick-start) section above).

### Run Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run specific test file
pytest tests/unit/test_quality_scoring.py -v

# Run with coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html  # View report
```

**Test Coverage:**
- **29 unit tests**: Quality scoring, semantic filtering, dynamic weights, dislike penalties, LLM context, CSV upload
- **Integration tests**: Infrastructure validation, Langfuse tracing, end-to-end API flow, CSV processing

After running tests, check your Langfuse dashboard for traces.

### Basic Endpoints
```bash
# Health check
curl http://localhost:8000/

# Infrastructure status
curl http://localhost:8000/health
```

### Test Database Connection
```bash
curl http://localhost:8000/test/db
```

**Expected response:**
```json
{
  "status": "connected",
  "pgvector_installed": true,
  "pgvector_version": "0.8.0",
  "tables": ["books", "recommendations"]
}
```

### Test Redis Connection
```bash
curl http://localhost:8000/test/redis
```

**Expected response:**
```json
{
  "status": "connected",
  "test_write_read": "success",
  "redis_version": "7.x.x",
  "uptime_seconds": 123
}
```

## Project Structure

```
backend/
├── app/
│   ├── config.py            ✓ Settings + env loading (dotenv + pydantic-settings)
│   ├── constants.py         ✓ Centralized configuration constants
│   ├── core/                ✓ Core infrastructure (complete)
│   │   ├── database.py      ✓ SQLAlchemy with context managers
│   │   ├── redis_client.py  ✓ Redis + SessionManager class
│   │   ├── langfuse_client.py ✓ Langfuse client initialization
│   │   └── embeddings.py    ✓ OpenAI embedding utilities
│   ├── models/              ✓ Data models (complete)
│   │   ├── database.py      ✓ Book & Recommendation ORM models
│   │   └── schemas.py       ✓ Pydantic request/response schemas
│   ├── api/routes/          ✓ API endpoints (complete)
│   │   ├── sessions.py      ✓ Session management + CSV upload
│   │   ├── recommendations.py ✓ Recommendation generation
│   │   └── feedback.py      ✓ User feedback submission
│   ├── services/            ✓ Business logic (complete)
│   │   ├── recommendation_engine.py ✓ RAG pipeline with Langfuse
│   │   ├── vector_search.py ✓ pgvector cosine similarity
│   │   ├── book_service.py  ✓ Book CRUD operations
│   │   └── google_books_api.py ✓ Google Books API integration
│   ├── utils/               ✓ Utilities (complete)
│   │   └── csv_processor.py ✓ Goodreads CSV parsing
│   └── workers/             ✓ Async task processing (complete)
│       ├── celery_app.py    ✓ Celery configuration
│       └── tasks.py         ✓ CSV processing task
├── scripts/                 ✓ Database utilities
│   ├── data_collection/    ✓ Production data collection (Goodreads 10k + NYT)
│   ├── seed_books.py       ✓ Seed sample books for testing
│   ├── clear_db.py         ✓ Clear all data (preserve schema)
│   └── reset_db.py         ✓ Drop & recreate schema
├── tests/                   ✓ Test suites
│   ├── unit/               ✓ Unit tests (29 tests)
│   │   ├── test_quality_scoring.py
│   │   ├── test_semantic_filtering.py
│   │   ├── test_dynamic_weights.py
│   │   ├── test_dislike_penalties.py
│   │   ├── test_llm_context.py
│   │   └── test_csv_upload.py
│   ├── integration/        ✓ Integration tests
│   │   ├── test_integration_pipeline.py
│   │   └── test_api.py
│   └── data/               ✓ Test data files
├── alembic/                 ✓ Database migrations
│   └── versions/
│       ├── 001_initial_migration.py ✓ Initial schema (books + recommendations)
│       └── 4b25be72aa78_add_rich_metadata_fields_to_books_table.py ✓ Rich metadata fields
├── main.py                  ✓ FastAPI app + test endpoints
├── requirements.txt         ✓ All dependencies
├── .env                     ✓ Environment configuration
└── README.md                ✓ This file
```

## Current Status

### ✅ Production-Ready (v2.0.0)

**Advanced RAG Pipeline:**
- [x] Quality scoring system (metadata-based ranking)
- [x] Semantic filtering (query-relevant favorites only)
- [x] Dynamic collaborative weighting (adapts to signal strength)
- [x] Dislike penalty system (avoids books similar to 1-2★ ratings)
- [x] Enhanced LLM context (includes user preferences and reading history)
- [x] Full Langfuse observability with hierarchical tracing

**Core Infrastructure:**
- [x] PostgreSQL 16 with pgvector extension (IVFFlat index for vector search)
- [x] Redis 7 for session management (1-hour TTL with auto-extension)
- [x] SQLAlchemy 2.0 with context manager pattern
- [x] Celery for async CSV processing with progress tracking

**API & Services:**
- [x] FastAPI with CORS, Pydantic validation, and interactive docs (Swagger UI)
- [x] Session management with CSV upload support (multipart/form-data)
- [x] Recommendation generation with personalized explanations
- [x] User feedback submission (linked to Langfuse traces)
- [x] Google Books API integration with rate limiting and exponential backoff

**Testing & Configuration:**
- [x] **29 unit tests** covering all advanced features (quality scoring, semantic filtering, dynamic weights, dislike penalties, LLM context, CSV upload)
- [x] **2 integration test suites** (core API flow + CSV upload workflow)
- [x] **Centralized configuration** in `app/constants.py` with validation

### Test Organization

Tests are organized into unit and integration categories:

```
tests/
├── unit/                       # Fast, isolated tests (no external dependencies)
│   ├── test_quality_scoring.py
│   ├── test_semantic_filtering.py
│   ├── test_dynamic_weights.py
│   ├── test_dislike_penalties.py
│   ├── test_llm_context.py
│   └── test_csv_upload.py
└── integration/                # Require services (DB, Redis, API)
    ├── test_integration_pipeline.py
    └── test_api.py
```

**Run tests:**
```bash
# All tests
pytest

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# With coverage
pytest --cov=app --cov-report=html
```

## Database Schema

### `books` table
Stores book metadata with vector embeddings for similarity search and rich metadata for quality scoring.

```sql
-- Identity
- id (serial primary key)
- isbn (varchar 20, unique, indexed)
- isbn13 (varchar 20, nullable, indexed)

-- Core Metadata
- title (text)
- author (text)

-- Rich Metadata (from Google Books API)
- description (text, nullable)
- categories (text[], nullable)
- page_count (integer, nullable)
- publisher (text, nullable)
- publication_year (integer, nullable, indexed)
- language (varchar 10, nullable)

-- Global Ratings (from Google Books API)
- average_rating (decimal 3,2, nullable)
- ratings_count (integer, nullable)

-- Media
- cover_url (text, nullable)

-- AI/ML
- embedding (vector 1536, nullable, ivfflat indexed)

-- Metadata
- data_source (varchar 50, nullable)
- created_at (timestamp)
- updated_at (timestamp)
```

**Indexes:**
- `ix_books_isbn` - Unique index on ISBN
- `ix_books_isbn13` - Index on ISBN13
- `ix_books_publication_year` - Index on publication year
- `idx_books_embedding` - IVFFlat index for vector similarity search (cosine distance, lists=100)
- `idx_books_categories` - GIN index for array search on categories

### `recommendations` table
Stores generated recommendations with Langfuse trace linking.

```sql
- id (serial primary key)
- session_id (varchar 255, indexed)
- book_id (integer, indexed)
- confidence_score (decimal 5,2)
- explanation (text)
- rank (integer)
- trace_id (varchar 255, nullable) - Links to Langfuse
- created_at (timestamp, indexed)
```

**Indexes:**
- `ix_recommendations_session_id` - Index on session_id
- `ix_recommendations_book_id` - Index on book_id
- `ix_recommendations_created_at` - Index on created_at for time-based queries

**Retention:** 30-day auto-cleanup (to be implemented via scheduled job)

## Advanced RAG Pipeline

The recommendation engine (`app/services/recommendation_engine.py`) implements a sophisticated 4-stage pipeline with personalization features:

### Pipeline Stages

**1. Query Understanding** - Combines user's query with follow-up answers

**2. Intelligent Retrieval** with multiple enhancement layers:
- **Semantic Filtering**: Filters user's favorites by query relevance (prevents unrelated 5★ books from dominating)
- **Dynamic Collaborative Weighting**: Adjusts collaborative filtering strength based on signal quality (requires minimum relevant books per `MIN_RELEVANT_BOOKS`)
- **Quality Scoring**: Re-ranks candidates based on metadata richness (description, categories, ratings)
- **Dislike Penalties**: Penalizes books similar to user's low-rated books (threshold defined by `DISLIKE_THRESHOLD`, similarity threshold per `DISLIKE_SIMILARITY_THRESHOLD`)

**3. LLM Generation** - GPT-4o-mini selects top 3 books with personalized explanations that reference user's reading history

**4. Storage** - Saves recommendations to PostgreSQL with Langfuse trace_id for feedback tracking

### Key Enhancements

**Quality Scoring**: Books are scored based on metadata completeness using weights defined in `QUALITY_SCORE_WEIGHTS`:
- Description quality (long vs short)
- Categories count (multiple vs single)
- Ratings credibility (high vs medium rating counts)
- Other metadata (page_count, publisher)

**Semantic Filtering**: Only uses user's favorites that are semantically relevant to current query (threshold per `SIMILARITY_THRESHOLD`)

**Dynamic Weighting**: Collaborative filtering weight scales dynamically based on number of relevant favorites

**Dislike Penalties**: Books similar to user's dislikes (per `DISLIKE_THRESHOLD`) have similarity reduced by penalty factor (per `DISLIKE_PENALTY` when above `DISLIKE_SIMILARITY_THRESHOLD`)

### Configuration Parameters

All tunable parameters are centralized in `app/constants.py`:

**Key Configuration Categories:**
- **LLM Configuration**: Model selection for generation
- **Quality Scoring Weights**: Weights for metadata quality assessment (description, categories, ratings, etc.)
- **Semantic Filtering**: Thresholds for query relevance filtering
- **Rating Thresholds**: Definitions for "favorites" and "dislikes"
- **Dislike Penalties**: Similarity penalty multipliers and thresholds
- **Retrieval**: Candidate selection limits
- **LLM Context**: Context size limits for generation
- **CSV Processing**: Upload size limits and processing intervals

See `app/constants.py` for current values and inline documentation on each parameter's purpose and tuning guidance.

### Langfuse Tracing

All stages are fully traced with `@observe()` decorators:
```
generate_recommendations (trace)
├─ _build_enhanced_query (span)
├─ _retrieve_candidates (span)
│  ├─ _filter_relevant_books (span) - Semantic filtering
│  ├─ create_embedding (generation)
│  ├─ _apply_quality_scoring (span) - Quality re-ranking
│  └─ _apply_dislike_penalties (span) - Penalty application
├─ _generate_with_llm (span)
│  └─ chat.completions.create (generation - GPT-4o-mini)
└─ _store_recommendations (span)
```

User feedback (like/dislike) is sent to Langfuse as scores linked to the trace.

## Recommendation Flow: From Query to Results

This section explains how the system generates personalized book recommendations through a multi-stage refinement process.

### 1. Initial Retrieval (Vector Search)

When a user submits a query, the system:
- Creates an embedding for the query using OpenAI text-embedding-3-small
- Performs two parallel vector searches using pgvector cosine similarity:
  - **Query-based search**: Finds books semantically similar to the query
  - **Collaborative search** (if CSV uploaded): Finds books similar to user's reading history (limited by `COLLABORATIVE_FILTERING_LIMIT`)
- Retrieves initial candidate books (total per `DEFAULT_TOP_K`)

**Example**: User queries "fantasy with magic systems"
- Query embedding captures semantic meaning of "fantasy" + "magic systems"
- Vector search returns books with similar themes in their embeddings

### 2. Semantic Filtering (Query-Relevant Favorites)

**Problem**: If a user has many coding books rated highly but queries for fantasy, we don't want coding books to dominate recommendations.

**Solution**: Filter user's favorites by semantic relevance to current query
- Calculate cosine similarity between query embedding and each of user's high-rated books (per `HIGH_RATING_THRESHOLD`)
- Only use favorites above similarity threshold (per `SIMILARITY_THRESHOLD`)
- Require minimum relevant books to activate collaborative filtering (per `MIN_RELEVANT_BOOKS`)

**Example**:
- User has many coding books (highly rated) + some fantasy books (highly rated)
- Query: "fantasy with magic systems"
- Only the fantasy books pass semantic filter (coding books filtered out)
- Result: Collaborative search uses only relevant fantasy favorites

### 3. Quality Scoring (Metadata-Based Re-ranking)

**Problem**: Some books have rich metadata (long descriptions, multiple categories, many ratings) while others are sparse.

**Solution**: Score each candidate based on metadata quality using weights defined in `QUALITY_SCORE_WEIGHTS`:
- **Description**: Long descriptions score higher than short ones
- **Categories**: Multiple categories score higher than single
- **Ratings**: High rating counts score higher than low counts
- **Other**: Presence of page_count, publisher, etc.

**Adjustment**: Multiply similarity score by quality score
- Book A: High similarity but sparse metadata → Lower adjusted score
- Book B: Lower similarity but rich metadata → Higher adjusted score
- Result: Book B ranks higher despite lower raw similarity

### 4. Dislike Penalties (Avoid Similar Books)

**Problem**: User rated a book poorly but system might recommend similar books in the same series.

**Solution**: Penalize candidates similar to user's dislikes (ratings at or below `DISLIKE_THRESHOLD`)
- Requires minimum number of dislikes to activate (filters outliers)
- Calculate similarity between each candidate and each disliked book
- If similarity above threshold (per `DISLIKE_SIMILARITY_THRESHOLD`), apply penalty
- Penalty: Multiply similarity by penalty factor (per `DISLIKE_PENALTY`)

**Example**:
- User rated a book poorly
- Candidate has high similarity to that disliked book
- Original similarity → Penalized: similarity × penalty factor
- Result: Book ranks much lower but isn't eliminated (LLM has final say)

### 5. LLM Generation (Intelligent Selection)

After refinement, the top candidates (per `DEFAULT_TOP_K`) are sent to the LLM (per `LLM_MODEL`) with:
- **User context**:
  - Books they loved (high ratings per `HIGH_RATING_THRESHOLD`) with titles/authors (limited by `MAX_FAVORITES_IN_CONTEXT`)
  - Books they disliked (low ratings per `DISLIKE_THRESHOLD`) with warning to avoid similar themes (limited by `MAX_DISLIKES_IN_CONTEXT`)
  - Rating distribution across all rating levels
- **Candidate metadata**: title, author, description (truncated per `CANDIDATE_DESCRIPTION_MAX_LENGTH`), categories, ratings, publication year
- **Instruction**: Select top 3 books with confidence scores and personalized explanations

**LLM's job**: Make final intelligent decision considering:
- How well each book matches the query
- Similarity to books user loved
- Dissimilarity from books user disliked
- Quality and relevance signals from earlier stages

**Example explanation**: "Like The Martian and Project Hail Mary, this book balances hard sci-fi with deeply human characters. Unlike Neuromancer's dense cyberpunk style, it offers accessible storytelling with warmth."

### 6. Storage & Feedback Loop

Final recommendations are:
- Stored in PostgreSQL with Langfuse `trace_id`
- Returned to user with full book details
- User feedback (like/dislike) sent to Langfuse as scores linked to trace
- Enables tracking recommendation quality over time

### Dynamic Collaborative Weighting

The system intelligently adjusts how much to weight collaborative filtering vs. query search:

| Scenario | Collaborative Weight | Behavior |
|----------|---------------------|----------|
| No CSV uploaded | Low (approaching 0%) | Pure semantic search on query |
| CSV with no favorites | Low | Weak signal from all books |
| CSV with favorites but none relevant to query | Low-Medium | Moderate signal from all favorites |
| CSV with relevant favorites (≥ `MIN_RELEVANT_BOOKS`) | Medium-High | Strong signal from relevant favorites |

**Example**: If user has multiple relevant favorites, collaborative weight increases
- More books from collaborative search (higher weight)
- Fewer books from query search (lower weight)
- Total candidates retrieved per `DEFAULT_TOP_K` and `COLLABORATIVE_FILTERING_LIMIT`

This prevents:
- Over-reliance on collaborative when signal is weak
- Ignoring user preferences when signal is strong
- Recommending unrelated books based on irrelevant favorites

### Why This Approach Works

1. **Graceful degradation**: Works perfectly without CSV, improves with better data
2. **Context-aware**: Only uses user data relevant to current query
3. **Quality-first**: Prioritizes books with rich, reliable metadata
4. **User-respecting**: Actively avoids books similar to dislikes
5. **Transparent**: Full Langfuse tracing shows exact decision process
6. **Tunable**: All thresholds configurable in `app/constants.py`

## CSV Processing Workflow

The backend supports async CSV upload for Goodreads library exports (`app/workers/tasks.py`):

### 1. Upload & Validation
- User uploads CSV via `POST /api/sessions/create` (multipart/form-data)
- Validates file extension and size (max per `CSV_UPLOAD_MAX_SIZE_MB`)
- Saves to temporary location (`/tmp/leaf_csv_uploads/{session_id}.csv`)
- Sets CSV status to "pending" in Redis

### 2. Async Processing (Celery Task)
- Task queued in Redis, picked up by Celery worker
- Parses CSV with Goodreads-specific format handling:
  - Cleans ISBN values (removes `="..."` Excel formula notation)
  - Extracts title, author, user rating (0-5)
  - Validates and filters books without ISBNs
- Status updated to "processing"

### 3. Book Enrichment (Per Book)
- Checks if book exists in PostgreSQL (by ISBN or ISBN13)
- If not found:
  - Fetches metadata from Google Books API
  - Exponential backoff for rate limiting (429 errors)
  - Generates embedding for title + author + description (truncated per `MAX_DESCRIPTION_LENGTH`)
  - Inserts into PostgreSQL with rich metadata
- Updates progress in Redis periodically (interval per `CSV_PROGRESS_UPDATE_INTERVAL`)
- Extends session TTL to prevent expiration during processing

### 4. Session Update
- Stores user's book IDs and ratings in Redis session
- Sets `csv_uploaded: true` and `books_from_csv: [...]`
- Updates status to "completed" (or "failed" on error)
- Deletes temporary CSV file

### 5. Frontend Polling
- Frontend polls `GET /api/sessions/{id}/status` periodically
- Receives progress: `{books_total, books_processed, new_books_added}`
- Proceeds to questions page when status is "completed"

**Processing time:** Depends on number of books and Google Books API rate limits

## Core Infrastructure Details

### Database Connection (`app/core/database.py`)
- Uses SQLAlchemy 2.0 context manager pattern
- Automatic commit on success
- Automatic rollback on exception
- Connection pooling with pre-ping health checks
- FastAPI dependency injection ready

### Redis Session Manager (`app/core/redis_client.py`)
```python
from app.core.redis_client import session_manager

# Create session
session_manager.create_session("session_id", {
    "initial_query": "...",
    "csv_uploaded": True
})

# Get session
data = session_manager.get_session("session_id")

# Update session
session_manager.update_session("session_id", updated_data)

# Set CSV status
session_manager.set_csv_status("session_id", "processing")

# Extend TTL (for long-running tasks)
session_manager.extend_session_ttl("session_id")
```

### OpenAI Embeddings (`app/core/embeddings.py`)
```python
from app.core.embeddings import create_embedding, create_embeddings_batch

# Single embedding
embedding = create_embedding("Book title and description")

# Batch embeddings (up to 2048 items)
embeddings = create_embeddings_batch([text1, text2, text3])
```

## Development Commands

```bash
# Start development server
uvicorn main:app --reload

# Start with custom host/port
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Database migrations
alembic upgrade head                        # Apply migrations
alembic revision --autogenerate -m "msg"    # Generate migration (review before using!)
alembic downgrade -1                        # Rollback one migration

# Docker commands
docker-compose up -d                        # Start all services
docker-compose down                         # Stop all services
docker-compose logs -f postgres             # View logs
docker-compose ps                           # Check status

# Database utilities
python scripts/seed_books.py               # Add 10 sample books for testing
python scripts/clear_db.py                 # Clear all data (keep schema)
python scripts/reset_db.py                 # Drop & recreate schema (DESTRUCTIVE)

# Data collection (production database seeding)
python scripts/data_collection/seed_goodreads_10k.py              # Load Goodreads 10k dataset
python scripts/data_collection/collect_nyt_bestsellers.py         # Collect NYT bestsellers (2008-2025)
python scripts/data_collection/collect_nyt_bestsellers.py --resume # Resume from checkpoint

# Testing
pytest                                     # Run all tests
pytest tests/unit/ -v                      # Run unit tests only
pytest tests/integration/ -v               # Run integration tests only
pytest --cov=app --cov-report=html         # Generate coverage report

# Celery worker (for CSV processing)
celery -A app.workers.celery_app worker --loglevel=info
```

## Available Endpoints

### Production Endpoints
- `GET /` - Basic health check
- `GET /health` - Detailed infrastructure status (DB + Redis)

### Session Management
- `POST /api/sessions/create` - Create new session with initial query (supports CSV upload via multipart/form-data)
- `POST /api/sessions/{session_id}/answers` - Submit follow-up answers
- `GET /api/sessions/{session_id}/status` - Get CSV processing status and progress

### Recommendations
- `GET /api/sessions/{session_id}/recommendations` - Get top 3 book recommendations

### Feedback
- `POST /api/recommendations/{recommendation_id}/feedback` - Submit like/dislike feedback

### Test/Debug Endpoints
- `GET /test/db` - Test database connectivity + pgvector
- `GET /test/redis` - Test Redis connectivity + operations
- `GET /docs` - Swagger UI (interactive API documentation)
- `GET /redoc` - ReDoc (alternative documentation)

## Environment Variables

See `.env.example` for all required variables. Key variables:

```bash
# Required
DATABASE_URL=postgresql://leaf_user:leaf_password@localhost:5432/leaf
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
GOOGLE_BOOKS_API_KEY=AIza...

# Celery (for CSV processing)
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Optional (have defaults)
REDIS_SESSION_TTL=3600                      # 1 hour
ENVIRONMENT=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3000
```

## Configuration Management

Environment variables are loaded in `app/config.py` using a hybrid approach:

1. **`dotenv.load_dotenv()`** - Loads `.env` file into `os.environ` (required for Langfuse)
2. **`pydantic-settings`** - Reads from `os.environ` and provides type-safe Settings object
3. **Langfuse decorators** - Require env vars in `os.environ` for `@observe()` to work

This ensures both pydantic-settings validation and Langfuse's global decorator instance work correctly.

## Optional Enhancements

The backend is production-ready with all planned features implemented. Future improvements could include:

**Performance & Scaling:**
- Recommendation result caching (Redis/Memcached)
- Batch processing for multiple users
- Database read replicas for query scaling
- CDN integration for book cover images

**Analytics & A/B Testing:**
- A/B testing framework for recommendation algorithms
- User behavior analytics dashboard
- Recommendation quality metrics tracking
- API usage tracking and rate limiting

**Advanced Features:**
- Dynamic follow-up question generation
- Multi-modal recommendations (book covers, sample text)
- Genre-specific tuning (different thresholds per category)
- Temporal decay (weight recent books more heavily)

## Troubleshooting

### Database connection fails
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Verify connection
docker exec -it leaf_postgres psql -U leaf_user -d leaf -c "SELECT version();"
```

### Redis connection fails
```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis
docker exec -it leaf_redis redis-cli ping
```

### Migrations fail
```bash
# Check database connection first
curl http://localhost:8000/test/db

# Reset database (WARNING: deletes all data)
alembic downgrade base
alembic upgrade head
```

### Import errors
```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## System Architecture Summary

```
Foundation & Infrastructure:  ████████████████████ 100%
Advanced RAG Pipeline:        ████████████████████ 100%
API & Services:               ████████████████████ 100%
Background Workers:           ████████████████████ 100%
Testing & Configuration:      ████████████████████ 100%

Overall:                      ████████████████████ 100% (v2.0.0)
```

**All features implemented and tested:**
- ✓ Advanced RAG pipeline (quality scoring, semantic filtering, dynamic weights, dislike penalties)
- ✓ Full Langfuse observability with hierarchical tracing
- ✓ Async CSV processing with Google Books API integration
- ✓ Comprehensive test coverage (29 unit tests + 2 integration test suites)
- ✓ Production-ready configuration and documentation
