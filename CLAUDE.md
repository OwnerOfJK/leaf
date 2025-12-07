# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Leaf** is a conversational book recommendation system that provides personalized book suggestions by analyzing user preferences through natural language and Goodreads reading history.

- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind CSS + Biome
- **Backend:** FastAPI + Python 3.13
- **Infrastructure:** PostgreSQL + pgvector, Redis, Celery, Langfuse
- **AI:** OpenAI (embeddings + LLM), RAG pipeline with vector search

## Development Commands

### Frontend (Next.js)
```bash
cd frontend
npm install              # Install dependencies
npm run dev             # Start dev server (http://localhost:3000)
npm run build           # Production build
npm run start           # Start production server
npm run lint            # Run Biome linter
npm run format          # Format with Biome
```

### Backend (FastAPI)
```bash
cd backend
python -m venv .venv                        # Create virtual environment
source .venv/bin/activate                   # Activate venv (Linux/Mac)
pip install -r requirements.txt             # Install dependencies
uvicorn main:app --reload                   # Start dev server (http://localhost:8000)
uvicorn main:app --reload --host 0.0.0.0    # Expose on all interfaces
```

**Database migrations:**
```bash
alembic upgrade head                        # Run migrations
alembic revision --autogenerate -m "msg"    # Generate migration
```

**Celery worker (CSV processing):**
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

### Docker Compose
```bash
docker-compose up -d postgres redis         # Start databases only
docker-compose up -d                        # Start all services
docker-compose down                         # Stop all services
docker-compose logs -f backend              # View backend logs
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Architecture Overview

### High-Level Data Flow

```
User Input → Redis Session → RAG Pipeline → PostgreSQL → Langfuse
     ↓           ↓              ↓              ↓            ↓
  CSV Upload  Session TTL   Vector Search  Recommendations  Feedback
                1 hour      (pgvector)     (30-day TTL)   (scores)
```

### Key Architectural Patterns

**Session Management:**
- Redis stores temporary session data (query, answers, CSV status) with 1-hour TTL
- Sessions are standalone - no persistent user accounts in MVP
- After expiration, recommendations persist in PostgreSQL but context is lost

**RAG Pipeline (Retrieval-Augmented Generation):**
1. **Retrieval:** pgvector cosine similarity search on 300k+ books
2. **Ranking:** Combine user's books (if CSV) + Google Books top results
3. **Generation:** GPT-4o-mini selects top 3 with explanations
4. **Observability:** Full Langfuse tracing on all steps

**Data Architecture:**
- **PostgreSQL:** Permanent storage (books + embeddings, recommendations)
- **Redis:** Temporary session data (1-hour TTL)
- **Langfuse:** Observability + user feedback (single source of truth)

### Database Schema

**PostgreSQL Tables:**
```sql
-- books: 300k+ books from Google Books API + user uploads
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(20) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    description TEXT,
    categories TEXT[],
    cover_url TEXT,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_books_embedding ON books USING ivfflat (embedding vector_cosine_ops);

-- recommendations: Generated recommendations with Langfuse linkage (30-day retention)
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    book_id INTEGER REFERENCES books(id),
    confidence_score DECIMAL(5,2),
    explanation TEXT,
    rank INTEGER,
    trace_id VARCHAR(255),  -- Links to Langfuse for feedback
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Redis Session Structure:**
```json
Key: session:{session_id}
TTL: 3600 seconds
Value: {
  "initial_query": "...",
  "follow_up_answers": {...},
  "csv_uploaded": true,
  "books_from_csv": [12345, 12346]
}
```

## Project Structure

```
leaf/
├── backend/                    # FastAPI Backend
│   ├── main.py                # FastAPI app entry point
│   ├── app/
│   │   ├── api/routes/        # API endpoints (sessions, recommendations, feedback)
│   │   ├── core/              # Database, Redis, Langfuse, embeddings
│   │   ├── services/          # Business logic (RAG engine, vector search, CSV)
│   │   ├── workers/           # Celery tasks (async CSV processing)
│   │   ├── models/            # SQLAlchemy ORM + Pydantic schemas
│   │   └── utils/
│   ├── alembic/               # Database migrations
│   └── requirements.txt
│
├── frontend/                  # Next.js Frontend
│   ├── src/app/
│   │   ├── page.tsx          # Input page (query + CSV upload)
│   │   ├── questions/        # Follow-up questions page
│   │   ├── recommendations/  # Recommendations display
│   │   ├── components/       # UI components
│   │   └── globals.css
│   ├── package.json
│   └── biome.json            # Biome config (linter + formatter)
│
├── docker-compose.yml         # Local dev infrastructure
├── PRODUCT.md                 # Complete product specification
└── README.md
```

## Core Workflows

### 1. CSV Processing (Async Worker)
When user uploads Goodreads CSV:
1. API stores file, creates session in Redis, sets CSV status to "pending"
2. Celery worker processes each book:
   - Check if ISBN exists in PostgreSQL
   - If not: fetch from Google Books API → generate embedding → insert into PostgreSQL
   - Update Redis session with user book IDs
3. CSV status updated to "completed"
4. Frontend polls status endpoint until ready

### 2. Recommendation Generation
1. Fetch session from Redis (query + answers + user book IDs)
2. Embed combined query with OpenAI text-embedding-3-small
3. Vector search (pgvector):
   - User's books: top 10 by cosine similarity
   - Google Books 300k: top 10
   - Merge, deduplicate, re-rank: top 20 candidates
4. LLM generation (GPT-4o-mini): Select top 3 with confidence scores + explanations
5. Store in PostgreSQL with trace_id
6. Return to frontend

### 3. User Feedback Flow
1. User clicks like/dislike on recommendation
2. Frontend calls `/api/recommendations/{id}/feedback`
3. Backend fetches trace_id from PostgreSQL
4. Send feedback to Langfuse as evaluation score (NOT stored in PostgreSQL)
5. Langfuse becomes single source of truth for all feedback

## Langfuse Integration

**All recommendation requests are fully traced:**
```
Trace: get_recommendations
├─ Span: csv_processing (if uploaded)
├─ Span: query_understanding
├─ Span: retrieval
│  ├─ embedding_creation
│  ├─ vector_search_user_books
│  ├─ vector_search_google_books
│  └─ candidate_reranking
├─ Span: generation
│  └─ LLM: generate_recommendations (gpt-4o-mini)
└─ Span: feedback_collection
   └─ Score: user_feedback (like=1/dislike=0)
```

Use `@observe()` decorator on all RAG pipeline functions.

## API Endpoints

- `POST /api/sessions/create` - Create session + upload CSV (optional)
- `POST /api/sessions/{session_id}/answers` - Submit follow-up answers
- `GET /api/sessions/{session_id}/recommendations` - Get 3 recommendations
- `POST /api/recommendations/{id}/feedback` - Submit like/dislike
- `GET /api/sessions/{session_id}/status` - Check CSV processing status

## Environment Variables

**Backend (.env):**
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/leaf
REDIS_URL=redis://localhost:6379/0
REDIS_SESSION_TTL=3600
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
GOOGLE_BOOKS_API_KEY=AIza...
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
ALLOWED_ORIGINS=http://localhost:3000
```

**Frontend (.env.local):**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Important Implementation Notes

**Session Lifecycle:**
- Sessions expire after 1 hour (Redis TTL)
- Users must complete recommendation flow within this window
- After expiration, recommendations persist in PostgreSQL for 30 days but context is lost

**Feedback Storage:**
- User feedback (like/dislike) stored ONLY in Langfuse, NOT in PostgreSQL
- PostgreSQL recommendations table maintains trace_id link for lookups
- This avoids data duplication and centralizes observability

**Vector Search Performance:**
- Use IVFFlat index on embeddings (reduces search from ~5s to ~100ms for 300k books)
- Batch embedding generation during CSV processing (up to 2048 inputs per OpenAI request)

**CSV Processing:**
- Worker extends session TTL every 30 seconds during processing
- Error handling: skip books not found in Google Books API, continue processing
- Implement exponential backoff for API rate limits

## Technology Stack

**Frontend:**
- Next.js 16 (App Router), TypeScript, React 19
- Tailwind CSS 4, shadcn/ui components
- Biome (linter + formatter, replaces ESLint + Prettier)

**Backend:**
- FastAPI, Python 3.13, SQLAlchemy, Pydantic
- pgvector for vector search
- Redis for sessions + Celery broker
- Celery for async CSV processing

**AI/ML:**
- OpenAI text-embedding-3-small (embeddings)
- OpenAI gpt-4o-mini (LLM generation)
- Langfuse for observability + feedback

## Pre-Implementation Assumptions

The product specification (PRODUCT.md) assumes:
1. **300k Google Books database is pre-embedded** and stored in PostgreSQL with pgvector
2. **pgvector extension is installed** on PostgreSQL
3. **OpenAI API access** with sufficient credits
4. **Langfuse Cloud account** with API keys configured
5. **Google Books API quota** (~100 requests/day for typical usage)
6. **Redis is running** for session management and Celery queue

## Development Workflow

1. Start databases: `docker-compose up -d postgres redis`
2. Run backend migrations: `cd backend && alembic upgrade head`
3. Start backend: `uvicorn main:app --reload`
4. Start Celery worker: `celery -A app.workers.celery_app worker --loglevel=info`
5. Start frontend: `cd frontend && npm run dev`
6. Access: Frontend at http://localhost:3000, API at http://localhost:8000

## Key Files to Check

- `PRODUCT.md` - Complete product specification (architecture, data flow, API contracts)
- `docker-compose.yml` - Infrastructure setup
- `backend/main.py` - FastAPI application entry point
- `frontend/package.json` - Frontend dependencies and scripts
- `backend/app/services/recommendation_engine.py` - Core RAG pipeline (to be implemented)
- `backend/app/workers/tasks.py` - CSV processing worker (to be implemented)

## Current State

This is a greenfield project. Core infrastructure is set up:
- Frontend: Basic Next.js app with TypeScript + Tailwind
- Backend: Minimal FastAPI app with example endpoints
- Database/Redis: Configured in docker-compose.yml
- Dependencies: Installed and ready

**Next implementation steps:** See section 16 in PRODUCT.md for detailed implementation roadmap.
