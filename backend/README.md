# Leaf Backend

FastAPI backend for the Leaf book recommendation system.

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update with your actual credentials:

```bash
cp .env.example .env
# Edit .env with your API keys and database credentials
```

### 4. Start Infrastructure (Docker)

```bash
# From project root
cd ..
docker-compose up -d postgres redis
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start Development Server

```bash
uvicorn main:app --reload
```

The API will be available at:
- http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── routes/          # API endpoint handlers
│   ├── core/                # Core infrastructure
│   │   ├── database.py      # PostgreSQL connection
│   │   ├── redis_client.py  # Redis session management
│   │   ├── langfuse_client.py # Langfuse observability
│   │   └── embeddings.py    # OpenAI embedding utilities
│   ├── models/
│   │   ├── database.py      # SQLAlchemy ORM models
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── services/            # Business logic (to be implemented)
│   ├── workers/             # Celery tasks (to be implemented)
│   ├── utils/
│   └── config.py            # Settings management
├── alembic/                 # Database migrations
│   └── versions/
│       └── 001_initial_migration.py
├── tests/
├── main.py                  # FastAPI application entry
├── requirements.txt
└── .env                     # Environment variables (not in git)
```

## Current Status

### ✅ Completed
- [x] Project structure
- [x] Configuration management (app/config.py)
- [x] Database models (Book, Recommendation)
- [x] Pydantic schemas for all API requests/responses
- [x] Core infrastructure:
  - [x] Database connection with SQLAlchemy
  - [x] Redis client with session management
  - [x] Langfuse client for observability
  - [x] OpenAI embedding utilities
- [x] Alembic migrations setup
- [x] Initial migration (books + recommendations tables)
- [x] FastAPI app with CORS

### 🚧 To Be Implemented
- [ ] API Routes (sessions, recommendations, feedback)
- [ ] Services layer (recommendation engine, vector search, CSV processor)
- [ ] Celery workers for async CSV processing
- [ ] RAG pipeline with Langfuse tracing
- [ ] Google Books API integration
- [ ] Tests

## Database Schema

### books
- Stores 300k+ books from Google Books API + user uploads
- Includes pgvector embeddings (1536 dimensions)
- IVFFlat index for fast cosine similarity search

### recommendations
- Generated recommendations with confidence scores
- Links to Langfuse traces via trace_id
- 30-day retention (auto-cleanup via scheduled job)

## Development Commands

```bash
# Start dev server
uvicorn main:app --reload

# Run migrations
alembic upgrade head

# Generate new migration
alembic revision --autogenerate -m "description"

# Start Celery worker (when implemented)
celery -A app.workers.celery_app worker --loglevel=info

# Run tests (when implemented)
pytest
```

## Environment Variables

See `.env.example` for all required environment variables.

## Next Steps

1. Implement API routes in `app/api/routes/`:
   - `sessions.py` - Session creation and management
   - `recommendations.py` - Get recommendations
   - `feedback.py` - Submit user feedback

2. Implement services in `app/services/`:
   - `recommendation_engine.py` - RAG pipeline
   - `vector_search.py` - pgvector queries
   - `book_service.py` - Book CRUD
   - `session_service.py` - Redis session operations
   - `csv_processor.py` - Goodreads CSV parsing
   - `google_books_api.py` - Google Books integration

3. Implement Celery workers in `app/workers/`:
   - `tasks.py` - Async CSV processing

4. Add Langfuse `@observe()` decorators to RAG pipeline functions

5. Implement tests
