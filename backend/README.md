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
│   ├── config.py            ✓ Settings management with Pydantic
│   ├── core/                ✓ Core infrastructure (complete)
│   │   ├── database.py      ✓ SQLAlchemy with context managers
│   │   ├── redis_client.py  ✓ Redis + SessionManager class
│   │   ├── langfuse_client.py ✓ Langfuse client initialization
│   │   └── embeddings.py    ✓ OpenAI embedding utilities
│   ├── models/              ✓ Data models (complete)
│   │   ├── database.py      ✓ Book & Recommendation ORM models
│   │   └── schemas.py       ✓ Pydantic request/response schemas
│   ├── api/routes/          ⚠️ To be implemented
│   ├── services/            ⚠️ To be implemented
│   └── workers/             ⚠️ To be implemented
├── alembic/                 ✓ Database migrations
│   └── versions/
│       └── 001_initial_migration.py ✓ Applied
├── main.py                  ✓ FastAPI app + test endpoints
├── requirements.txt         ✓ All dependencies
├── .env                     ✓ Environment configuration
└── README.md                ✓ This file
```

## Current Status

### ✅ Fully Functional Infrastructure (v0.1.0)

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
- [x] OpenAI client configured
- [x] Embedding utilities (single + batch processing)
- [x] Langfuse client initialized
- [x] Ready for RAG pipeline implementation

**API Layer:**
- [x] FastAPI application with CORS
- [x] Pydantic schemas for all API contracts
- [x] Health check endpoints
- [x] Database and Redis test endpoints
- [x] Interactive API documentation (Swagger UI)

### ⚠️ Not Yet Implemented

**API Routes:**
- [ ] `POST /api/sessions/create` - Create session + upload CSV
- [ ] `POST /api/sessions/{id}/answers` - Submit follow-up answers
- [ ] `GET /api/sessions/{id}/recommendations` - Get recommendations
- [ ] `POST /api/recommendations/{id}/feedback` - Submit feedback
- [ ] `GET /api/sessions/{id}/status` - CSV processing status

**Services Layer:**
- [ ] `recommendation_engine.py` - RAG pipeline with Langfuse tracing
- [ ] `vector_search.py` - pgvector cosine similarity queries
- [ ] `book_service.py` - Book CRUD operations
- [ ] `session_service.py` - Session orchestration
- [ ] `csv_processor.py` - Goodreads CSV parsing
- [ ] `google_books_api.py` - Google Books API integration

**Workers:**
- [ ] `celery_app.py` - Celery configuration
- [ ] `tasks.py` - Async CSV processing task

**Testing:**
- [ ] Unit tests for services
- [ ] Integration tests for API routes
- [ ] End-to-end tests for RAG pipeline

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

# When Celery is implemented
celery -A app.workers.celery_app worker --loglevel=info

# When tests are implemented
pytest
pytest -v                                   # Verbose
pytest tests/test_services.py              # Specific file
```

## Available Endpoints

### Production Endpoints
- `GET /` - Basic health check
- `GET /health` - Detailed infrastructure status (DB + Redis)

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

## Next Implementation Steps

To build a **minimal viable recommendation system**, implement in this order:

1. **Book Service** (`app/services/book_service.py`)
   - CRUD operations for books
   - Check if book exists by ISBN
   - Create book with embedding

2. **Session Routes** (`app/api/routes/sessions.py`)
   - `POST /api/sessions/create` - Create session (no CSV for now)
   - Session validation and error handling

3. **Vector Search Service** (`app/services/vector_search.py`)
   - pgvector cosine similarity queries
   - Return top N similar books

4. **Recommendation Engine** (`app/services/recommendation_engine.py`)
   - Basic RAG pipeline
   - Query embedding + vector search + LLM ranking
   - Langfuse tracing with `@observe` decorator

5. **Recommendation Routes** (`app/api/routes/recommendations.py`)
   - `GET /api/sessions/{id}/recommendations` - Return top 3 books

6. **Feedback Routes** (`app/api/routes/feedback.py`)
   - `POST /api/recommendations/{id}/feedback` - Store in Langfuse

This gives you an end-to-end flow: create session → get recommendations → provide feedback.

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
API Routes:                   ░░░░░░░░░░░░░░░░░░░░   0%
Business Logic (Services):    ░░░░░░░░░░░░░░░░░░░░   0%
Background Workers (Celery):  ░░░░░░░░░░░░░░░░░░░░   0%
Testing:                      ░░░░░░░░░░░░░░░░░░░░   0%

Overall:                      ██████████░░░░░░░░░░  50%
```

The backend foundation is **production-ready**. Ready to implement business logic!
