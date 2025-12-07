# Leaf Backend

FastAPI backend for the Leaf book recommendation system.

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

## Testing the Backend

### Integration Tests

Run the comprehensive test suite:

```bash
# Make sure server is running first
uvicorn main:app --reload

# In another terminal
python test_comprehensive.py
```

The test suite validates:
1. **Infrastructure** - Database (pgvector), Redis connectivity
2. **Langfuse Integration** - Direct testing of `@observe()` decorators and OpenAI wrapper
3. **End-to-End API Flow** - Session creation → Recommendations → Feedback

After tests complete, check your Langfuse dashboard for traces.

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
│   ├── core/                ✓ Core infrastructure (complete)
│   │   ├── database.py      ✓ SQLAlchemy with context managers
│   │   ├── redis_client.py  ✓ Redis + SessionManager class
│   │   ├── langfuse_client.py ✓ Langfuse client initialization
│   │   └── embeddings.py    ✓ OpenAI embedding utilities
│   ├── models/              ✓ Data models (complete)
│   │   ├── database.py      ✓ Book & Recommendation ORM models
│   │   └── schemas.py       ✓ Pydantic request/response schemas
│   ├── api/routes/          ✓ API endpoints (complete)
│   │   ├── sessions.py      ✓ Session management
│   │   ├── recommendations.py ✓ Recommendation generation
│   │   └── feedback.py      ✓ User feedback submission
│   ├── services/            ✓ Business logic (complete)
│   │   ├── recommendation_engine.py ✓ RAG pipeline with Langfuse
│   │   ├── vector_search.py ✓ pgvector cosine similarity
│   │   └── book_service.py  ✓ Book CRUD operations
│   └── workers/             ⚠️ To be implemented (Celery for CSV)
├── scripts/                 ✓ Database utilities
│   ├── seed_books.py       ✓ Seed sample books for testing
│   ├── clear_db.py         ✓ Clear all data (preserve schema)
│   └── reset_db.py         ✓ Drop & recreate schema
├── alembic/                 ✓ Database migrations
│   └── versions/
│       └── 001_initial_migration.py ✓ Applied
├── main.py                  ✓ FastAPI app + test endpoints
├── test_comprehensive.py    ✓ Integration tests
├── requirements.txt         ✓ All dependencies
├── .env                     ✓ Environment configuration
└── README.md                ✓ This file
```

## Current Status

### ✅ Fully Functional (v0.8.0)

**Database Layer:**
- [x] PostgreSQL 16 with pgvector extension running
- [x] SQLAlchemy 2.0 engine with connection pooling
- [x] Context manager pattern for automatic commit/rollback
- [x] Database models: `Book` and `Recommendation`
- [x] Migrations applied successfully
- [x] IVFFlat vector index for cosine similarity search

**Cache Layer:**
- [x] Redis 7 running and tested
- [x] `SessionManager` class with full CRUD operations
- [x] Automatic TTL management (1-hour sessions)
- [x] CSV status tracking support
- [x] Session metadata support

**AI/ML Integration:**
- [x] OpenAI client configured with Langfuse wrapper
- [x] Embedding utilities (single + batch processing)
- [x] Langfuse client initialized
- [x] RAG pipeline with full `@observe` tracing

**API Layer:**
- [x] FastAPI application with CORS
- [x] Pydantic schemas for all API contracts
- [x] Health check endpoints
- [x] Database and Redis test endpoints
- [x] Interactive API documentation (Swagger UI)
- [x] Session management endpoints
- [x] Recommendation generation endpoint
- [x] Feedback submission endpoint

**Services Layer:**
- [x] `recommendation_engine.py` - Complete RAG pipeline with Langfuse
- [x] `vector_search.py` - pgvector cosine similarity queries
- [x] `book_service.py` - Book CRUD operations

**Utilities:**
- [x] `scripts/seed_books.py` - Seed 10 sample books
- [x] `scripts/clear_db.py` - Clear all data
- [x] `scripts/reset_db.py` - Drop & recreate schema

**Testing:**
- [x] `test_comprehensive.py` - Integration test suite
  - Infrastructure validation (DB, Redis, Langfuse)
  - Direct Langfuse integration testing
  - End-to-end API flow testing

### ⚠️ Not Yet Implemented

**Workers:**
- [ ] `celery_app.py` - Celery configuration
- [ ] `tasks.py` - Async CSV processing task
- [ ] CSV upload endpoint
- [ ] CSV processing status endpoint

**Optional Enhancements:**
- [ ] `session_service.py` - Advanced session orchestration
- [ ] `csv_processor.py` - Goodreads CSV parsing
- [ ] `google_books_api.py` - Google Books API integration for CSV uploads

## Database Schema

### `books` table
Stores book metadata with vector embeddings for similarity search.

```sql
- id (serial primary key)
- isbn (varchar 20, unique, indexed)
- title (text)
- author (text)
- description (text, nullable)
- categories (text[], nullable)
- cover_url (text, nullable)
- embedding (vector 1536, ivfflat indexed)
- created_at (timestamp)
```

**Indexes:**
- `idx_books_isbn` - Unique index on ISBN
- `idx_books_embedding` - IVFFlat index for vector similarity search (cosine distance)

### `recommendations` table
Stores generated recommendations with Langfuse trace linking.

```sql
- id (serial primary key)
- session_id (varchar 255, indexed)
- book_id (integer, indexed)
- confidence_score (decimal 5,2)
- explanation (text)
- rank (integer)
- trace_id (varchar 255) - Links to Langfuse
- created_at (timestamp, indexed)
```

**Retention:** 30-day auto-cleanup (to be implemented via scheduled job)

## RAG Pipeline Architecture

The recommendation engine (`app/services/recommendation_engine.py`) implements a 4-step RAG pipeline with full Langfuse tracing:

### 1. Query Understanding (`_build_enhanced_query`)
Combines user's initial query with optional follow-up answers into a single enhanced query string.

### 2. Retrieval (`_retrieve_candidates`)
- Creates embedding for enhanced query using OpenAI text-embedding-3-small
- Performs vector search using pgvector cosine similarity
- If user uploaded CSV: searches for books similar to their reading history
- Returns top 20 candidate books

### 3. Generation (`_generate_with_llm`)
- Formats candidate books with metadata (title, author, description, categories)
- Sends to GPT-4o-mini with system prompt instructing it to select top 3 books
- LLM returns JSON with confidence scores (0-100) and explanations
- Uses `response_format={"type": "json_object"}` for structured output

### 4. Storage (`_store_recommendations`)
- Saves recommendations to PostgreSQL
- Links to Langfuse trace_id for observability
- Returns recommendations with full book details

**Langfuse Tracing:**
All steps are decorated with `@observe()`, creating a hierarchical trace:
```
generate_recommendations (trace)
├─ _build_enhanced_query (span)
├─ _retrieve_candidates (span)
│  └─ create_embedding (generation - OpenAI API call)
├─ _generate_with_llm (span)
│  └─ chat.completions.create (generation - GPT-4o-mini call)
└─ _store_recommendations (span)
```

User feedback (like/dislike) is sent to Langfuse as scores linked to the trace.

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
python scripts/seed_books.py               # Add 10 sample books
python scripts/clear_db.py                 # Clear all data (keep schema)
python scripts/reset_db.py                 # Drop & recreate schema (DESTRUCTIVE)

# Testing
python test_comprehensive.py               # Run integration tests

# When Celery is implemented
celery -A app.workers.celery_app worker --loglevel=info
```

## Available Endpoints

### Production Endpoints
- `GET /` - Basic health check
- `GET /health` - Detailed infrastructure status (DB + Redis)

### Session Management
- `POST /api/sessions/create` - Create new session with initial query
- `POST /api/sessions/{session_id}/answers` - Submit follow-up answers

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

## Next Implementation Steps

The core recommendation system is complete. Optional enhancements:

1. **CSV Upload Feature** (Celery workers)
   - `app/workers/celery_app.py` - Celery configuration
   - `app/workers/tasks.py` - Async CSV processing
   - `POST /api/sessions/create` - Accept CSV file upload
   - `GET /api/sessions/{id}/status` - Poll CSV processing status

2. **Google Books API Integration**
   - `app/services/google_books_api.py` - Fetch book metadata by ISBN
   - Enrich database with more books from user CSVs

3. **Advanced Features**
   - Follow-up question generation based on query
   - More sophisticated LLM prompting
   - A/B testing different recommendation algorithms
   - Recommendation explanation improvements

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

## Implementation Progress

```
Foundation & Infrastructure:  ████████████████████ 100%
Database Schema & Models:     ████████████████████ 100%
Core Services:                ████████████████████ 100%
API Routes:                   ████████████████████ 100%
Business Logic (Services):    ████████████████████ 100%
Testing:                      ████████████████████ 100%
Background Workers (Celery):  ░░░░░░░░░░░░░░░░░░░░   0%

Overall:                      ██████████████████░░  85%
```

The **core recommendation system is production-ready**! The RAG pipeline, API endpoints, and Langfuse integration are fully functional. CSV upload via Celery workers is optional.
