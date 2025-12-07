# Leaf - Product Overview Document

## 1. Product Summary

**Leaf** is a conversational book recommendation system that provides personalized book suggestions by analyzing user preferences through natural language and their Goodreads reading history.

### Key Features
- Upload Goodreads library CSV (optional)
- Natural language preference input
- Smart follow-up questions for preference refinement
- 3 personalized recommendations with confidence scores and explanations
- User feedback collection (like/dislike)
- Full Langfuse observability integration

### Target Audience
Readers seeking personalized book recommendations based on their reading history and preferences.

---

### Key Architectural Decisions

**Simplified Data Architecture:**
- **PostgreSQL (2 tables):** Books with embeddings + Recommendations
- **Redis (sessions):** Temporary session data with 1-hour TTL
- **Langfuse:** All user feedback and observability

**Rationale:**
- ✅ **Simpler:** Fewer tables, faster development
- ✅ **Efficient:** No duplicate data between PostgreSQL and Langfuse
- ✅ **Scalable:** Redis handles high-frequency session reads/writes
- ✅ **Observable:** Langfuse as single source of truth for feedback and traces
- ⚠️ **Trade-off:** Session context lost after 1 hour (acceptable for standalone sessions)

---

## 2. User Flow

### Step 1: Initial Input Page
- **UI Elements:**
  - Text input box: "What kind of book are you looking for?"
  - CSV upload button (optional): "Upload Goodreads Library"
  - Submit button

- **User Actions:**
  - Enter initial preference (e.g., "I want a sci-fi book like The Martian but darker")
  - Optionally upload Goodreads CSV export
  - Click submit

### Step 2: Follow-up Questions Page
- **Display:** 3 pre-generated questions on a single page
- **Questions are:**
  - Generic, not dynamically generated
  - All optional (can be skipped)
  - Example: "What's your preferred book length?", "Do you prefer character-driven or plot-driven stories?"

### Step 3: Recommendations Page
- **Display:** 3 book recommendations, each showing:
  - Book cover (image)
  - Title and Author
  - Description
  - **Confidence Level:** Cosine similarity score (0-100%)
  - **Reason:** Personalized explanation of why this book matches user preferences
  - Like/Dislike buttons

- **User Actions:**
  - View recommendations
  - Provide feedback (thumbs up/down)
  - Start new search (standalone session)

### Background Processing
While user answers follow-up questions:
- Async worker processes uploaded CSV
- Checks if books exist in database (match by ISBN)
- For new books: fetch from Google Books API → add to PostgreSQL → generate embeddings

---

## 3. Technical Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│  - TypeScript + React                                        │
│  - Tailwind CSS + shadcn/ui                                  │
│  - Pages: Input → Questions → Recommendations                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ REST API
                 ↓
┌─────────────────────────────────────────────────────────────┐
│                 Backend (Python FastAPI)                     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Recommendation Engine                         │  │
│  │  - RAG Pipeline (Retrieval + Generation)             │  │
│  │  - Langfuse instrumentation on all steps             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         CSV Processing Worker (Celery)               │  │
│  │  - ISBN matching against PostgreSQL                  │  │
│  │  - Google Books API integration                       │  │
│  │  - Embedding generation (OpenAI)                      │  │
│  │  - Updates Redis session status                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└──┬────────────┬────────────────┬──────────────────┬─────────┘
   │            │                │                  │
   ↓            ↓                ↓                  ↓
┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐
│PostgreSQL│ │  Redis   │ │  Langfuse    │ │ Google Books │
│+pgvector │ │          │ │  Cloud       │ │     API      │
│          │ │Sessions: │ │              │ │              │
│Tables:   │ │- Query   │ │- Traces      │ │- Metadata    │
│- books   │ │- Answers │ │- Scores      │ │- Cover URLs  │
│  (300k+) │ │- Status  │ │- Sessions    │ │              │
│- recs    │ │          │ │- Feedback    │ │              │
│  (30d)   │ │TTL: 1h   │ │              │ │              │
└──────────┘ └──────────┘ └──────────────┘ └──────────────┘
```

### Data Flow: RAG Pipeline

```
1. User Input + Optional CSV Upload
   ↓
2. Create Redis Session (TTL: 1 hour)
   - Store: query, answers, csv_status
   ↓
3. [Optional] Background CSV Processing (Celery Worker)
   - Check ISBN in PostgreSQL
   - Fetch missing books from Google Books API
   - Generate embeddings (OpenAI)
   - Store in PostgreSQL books table
   - Update Redis session with user book IDs
   ↓
4. User Answers Follow-up Questions
   - Update Redis session with answers
   ↓
5. Generate Recommendations (RAG Pipeline - Langfuse Traced)
   │
   ├─► Retrieve Session from Redis
   │   (query + answers + user book IDs)
   │
   ├─► Embed Combined Query (OpenAI text-embedding-3-small)
   │
   ├─► Vector Search (pgvector in PostgreSQL)
   │   - User's books: top 10
   │   - Google Books 300k: top 10
   │   - Merge & deduplicate: top 20 candidates
   │
   └─► LLM Generation (GPT-4o-mini)
       - Context: query + candidates
       - Output: Top 3 with confidence + explanations
   ↓
6. Store in PostgreSQL
   - recommendations table (session_id, trace_id)
   ↓
7. Display to User
   ↓
8. User Feedback (Like/Dislike)
   - Fetch trace_id from PostgreSQL
   - Send to Langfuse as evaluation score
```

---

## 4. Database Schema

### Architecture Overview

**PostgreSQL:** Persistent storage for books and recommendations  
**Redis:** Temporary session storage (1-hour TTL)  
**Langfuse:** User feedback and observability

---

### PostgreSQL Tables

#### `books`
Primary book metadata storage (300k+ books from Google Books API + user uploads)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

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

CREATE INDEX idx_books_isbn ON books(isbn);
CREATE INDEX idx_books_embedding ON books USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Notes:**
- Combines book metadata + embeddings in single table
- User-uploaded books (from CSV) are added to this same table
- No differentiation between Google Books and user books needed (Redis session tracks user books)

---

#### `recommendations`
Store generated recommendations with Langfuse trace linking (30-day retention)

```sql
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,  -- Links to Redis session key
    book_id INTEGER REFERENCES books(id),
    confidence_score DECIMAL(5,2),  -- Cosine similarity (0-100)
    explanation TEXT,  -- LLM-generated reason
    rank INTEGER,  -- 1, 2, or 3
    trace_id VARCHAR(255),  -- Langfuse trace ID for linking to feedback
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_recommendations_session_id ON recommendations(session_id);
CREATE INDEX idx_recommendations_book_id ON recommendations(book_id);
CREATE INDEX idx_recommendations_created_at ON recommendations(created_at);
```

**Retention Policy:**
```sql
-- Auto-delete recommendations older than 30 days (run daily via cron/scheduled job)
DELETE FROM recommendations WHERE created_at < NOW() - INTERVAL '30 days';
```

**Notes:**
- `session_id` links to Redis (valid for 1 hour), then becomes historical reference
- `trace_id` links to Langfuse for full trace details and user feedback
- No feedback column here - all feedback stored in Langfuse via trace_id

---

### Redis Session Storage

#### Session Data Structure
```
Key: session:{session_id}
TTL: 3600 seconds (1 hour)

Value (JSON):
{
  "initial_query": "I want a sci-fi book like The Martian but darker",
  "follow_up_answers": {
    "question_1": "Medium length, 300-400 pages",
    "question_2": "Plot-driven",
    "question_3": "Recent publications preferred"
  },
  "csv_uploaded": true,
  "books_from_csv": [12345, 12346, 12347],  -- Book IDs after CSV processing
  "created_at": "2024-12-06T10:30:00Z"
}
```

#### CSV Processing Status
```
Key: session:{session_id}:csv_status
TTL: 3600 seconds (1 hour)

Value: "pending" | "processing" | "completed" | "failed"
```

#### Additional Session Metadata (Optional)
```
Key: session:{session_id}:metadata
TTL: 3600 seconds (1 hour)

Value (JSON):
{
  "total_books_in_csv": 150,
  "books_processed": 150,
  "new_books_added": 12,
  "processing_started_at": "2024-12-06T10:30:05Z",
  "processing_completed_at": "2024-12-06T10:32:30Z"
}
```

**Notes:**
- Sessions auto-expire after 1 hour
- After expiration, session context is lost but recommendations persist in PostgreSQL
- For long-term session analysis, rely on Langfuse traces (which include session context)

---

### Data Persistence Strategy Summary

```
┌─────────────────────────────────────────────────────────┐
│ What Gets Stored Where                                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ PostgreSQL (Permanent):                                 │
│ ✓ All books (300k + user uploads)                      │
│ ✓ Book embeddings (vector search)                       │
│ ✓ Recommendations (30-day retention)                    │
│ ✓ Link to Langfuse via trace_id                         │
│                                                          │
│ Redis (1-hour TTL):                                     │
│ ✓ User query + follow-up answers                        │
│ ✓ CSV upload status                                     │
│ ✓ User book IDs (from CSV)                              │
│ ✓ Processing metadata                                   │
│                                                          │
│ Langfuse (Long-term):                                   │
│ ✓ Full RAG pipeline traces                              │
│ ✓ User feedback (like/dislike)                          │
│ ✓ Session context (query, answers)                      │
│ ✓ Performance metrics (latency, cost)                   │
│ ✓ Evaluation scores                                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 5. API Endpoints

### Base URL
```
Development: http://localhost:8000
Production: TBD
```

### Endpoints

#### `POST /api/sessions/create`
Create a new recommendation session

**Request Body:**
```json
{
  "initial_query": "I want a sci-fi book like The Martian but darker",
  "csv_file": "<multipart/form-data>" // optional
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing_csv" | "ready",
  "follow_up_questions": [
    "What's your preferred book length?",
    "Do you prefer character-driven or plot-driven stories?",
    "Are you open to older classics or prefer recent publications?"
  ]
}
```

**Processing:**
- Generate unique session_id
- Store in Redis: `session:{session_id}` (TTL: 1 hour)
- If CSV uploaded:
  - Set `session:{session_id}:csv_status` = "pending"
  - Trigger async Celery worker
- Return follow-up questions

---

#### `POST /api/sessions/{session_id}/answers`
Submit follow-up question answers

**Request Body:**
```json
{
  "answers": {
    "question_1": "Medium length, 300-400 pages",
    "question_2": "Plot-driven",
    "question_3": "Recent publications preferred"
  }
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ready" | "processing_csv",
  "csv_books_count": 150  // if CSV was uploaded
}
```

**Processing:**
- Update Redis session with answers
- Check CSV processing status
- Return current status

---

#### `GET /api/sessions/{session_id}/recommendations`
Get book recommendations

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "recommendations": [
    {
      "id": 123,
      "book": {
        "isbn": "9780553418026",
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "description": "A lone astronaut must save Earth...",
        "cover_url": "https://books.google.com/...",
        "categories": ["Science Fiction", "Thriller"]
      },
      "confidence_score": 87.5,
      "explanation": "This book matches your preference for recent sci-fi with survival themes. Like The Martian, it features a resourceful protagonist solving problems in space, but with higher stakes and darker themes.",
      "rank": 1
    },
    {
      "id": 124,
      "book": { ... },
      "confidence_score": 82.3,
      "explanation": "...",
      "rank": 2
    },
    {
      "id": 125,
      "book": { ... },
      "confidence_score": 78.1,
      "explanation": "...",
      "rank": 3
    }
  ],
  "trace_id": "trace_abc123",
  "trace_url": "https://cloud.langfuse.com/trace/trace_abc123"
}
```

**Processing:**
1. Retrieve session data from Redis (query + answers + user book IDs if CSV)
2. **Retrieval Step (Langfuse traced):**
   - Embed combined query (initial + answers)
   - Vector search in pgvector:
     - User's books (if CSV uploaded): top 10
     - Google Books 300k: top 10
   - Combine and re-rank: top 20 candidates
3. **Generation Step (Langfuse traced):**
   - Send to LLM with context
   - Extract top 3 with confidence scores + explanations
4. Store recommendations in PostgreSQL with session_id and trace_id
5. Return to frontend

---

#### `POST /api/recommendations/{recommendation_id}/feedback`
Submit user feedback (like/dislike)

**Request Body:**
```json
{
  "feedback_type": "like" | "dislike"
}
```

**Response:**
```json
{
  "success": true,
  "langfuse_score_id": "score_xyz789"
}
```

**Processing:**
- Fetch recommendation from PostgreSQL (get trace_id)
- Send feedback to Langfuse as evaluation score:
  ```python
  langfuse.score(
      trace_id=recommendation.trace_id,
      name="user_feedback",
      value=1 if feedback_type == "like" else 0,
      comment=f"User {feedback_type}d recommendation {recommendation_id}"
  )
  ```
- Return Langfuse score ID

**Note:** Feedback stored only in Langfuse, not in PostgreSQL

---

#### `GET /api/sessions/{session_id}/status`
Check CSV processing status

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "csv_status": "pending" | "processing" | "completed" | "failed",
  "books_processed": 87,
  "books_total": 150,
  "new_books_added": 12
}
```

**Processing:**
- Read from Redis: `session:{session_id}:csv_status`
- Read from Redis: `session:{session_id}:metadata`
- Return current processing state

---

## 6. File Structure

```
leaf/
│
├── backend/                          # Python FastAPI Backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application entry
│   │   ├── config.py                # Environment variables, settings
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sessions.py      # Session endpoints
│   │   │   │   ├── recommendations.py
│   │   │   │   └── feedback.py
│   │   │   └── dependencies.py      # Shared dependencies
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── database.py          # PostgreSQL connection
│   │   │   ├── redis_client.py      # Redis connection & session management
│   │   │   ├── langfuse_client.py   # Langfuse initialization
│   │   │   └── embeddings.py        # OpenAI embedding utilities
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── recommendation_engine.py  # RAG pipeline
│   │   │   ├── vector_search.py          # pgvector queries
│   │   │   ├── book_service.py           # Book CRUD operations
│   │   │   ├── session_service.py        # Redis session operations
│   │   │   ├── csv_processor.py          # Goodreads CSV parsing
│   │   │   └── google_books_api.py       # Google Books integration
│   │   │
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py        # Celery configuration
│   │   │   └── tasks.py             # Async CSV processing tasks
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py          # SQLAlchemy ORM models (books, recommendations)
│   │   │   └── schemas.py           # Pydantic request/response models
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   │
│   ├── alembic/                     # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_api.py
│   │   └── test_services.py
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── README.md
│
├── frontend/                        # Next.js TypeScript Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx          # Root layout
│   │   │   ├── page.tsx            # Input page
│   │   │   ├── questions/
│   │   │   │   └── page.tsx        # Follow-up questions page
│   │   │   ├── recommendations/
│   │   │   │   └── page.tsx        # Recommendations display page
│   │   │   └── globals.css
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui components
│   │   │   │   ├── button.tsx
│   │   │   │   ├── input.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   └── ...
│   │   │   ├── InputForm.tsx       # Initial query + CSV upload
│   │   │   ├── QuestionForm.tsx    # Follow-up questions
│   │   │   ├── BookCard.tsx        # Recommendation card
│   │   │   ├── FeedbackButtons.tsx # Like/Dislike
│   │   │   └── LoadingSpinner.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts              # API client functions
│   │   │   └── utils.ts            # Helper functions
│   │   │
│   │   ├── types/
│   │   │   └── index.ts            # TypeScript interfaces
│   │   │
│   │   └── hooks/
│   │       └── useSession.ts       # Session state management
│   │
│   ├── public/
│   │   └── images/
│   │
│   ├── .env.local.example
│   ├── next.config.js
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── README.md
│
├── docker-compose.yml               # Local development setup
├── .gitignore
└── README.md                        # Project overview
```

---

## 7. Technology Stack

### Frontend
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **UI Components:** shadcn/ui
- **State Management:** React hooks + Context API
- **HTTP Client:** Native Fetch API

### Backend
- **Framework:** FastAPI
- **Language:** Python 3.11+
- **ORM:** SQLAlchemy
- **Validation:** Pydantic
- **Session Store:** Redis (redis-py)
- **Task Queue:** Celery + Redis broker
- **Embeddings:** OpenAI API (text-embedding-3-small)
- **LLM:** OpenAI API (gpt-4o-mini)
- **Vector DB:** pgvector (PostgreSQL extension)

**Key Dependencies:**
```
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pgvector
redis
celery
langfuse
openai
pydantic
alembic
```

### Database
- **Primary DB:** PostgreSQL 15+
- **Vector Extension:** pgvector
- **Session Store:** Redis 7+
- **Migration Tool:** Alembic

### Observability
- **Platform:** Langfuse Cloud
- **SDK:** langfuse-python
- **Features Used:**
  - Tracing (full RAG pipeline)
  - Evaluations (user feedback scores)
  - Prompt Management (system prompts versioning)
  - Sessions (multi-step user journey tracking)
  - Datasets (test cases for recommendations)

### External APIs
- **Google Books API:** Book metadata fetching
- **OpenAI API:** Embeddings + LLM generation

### Infrastructure
- **Development:** Docker Compose
- **Production:** TBD (Vercel for frontend, Railway/Render for backend)

---

## 8. Langfuse Integration

### Tracing Strategy

Every recommendation request creates a Langfuse trace with the following structure:

```
Trace: get_recommendations (session_id: xxx)
├─ Span: csv_processing (if CSV uploaded)
│  ├─ isbn_matching
│  ├─ google_books_fetch
│  └─ embedding_generation
│
├─ Span: query_understanding
│  └─ LLM: clarify_intent (gpt-4o-mini)
│
├─ Span: retrieval
│  ├─ embedding_creation (OpenAI)
│  ├─ vector_search_user_books
│  ├─ vector_search_google_books
│  └─ candidate_reranking
│
├─ Span: generation
│  └─ LLM: generate_recommendations (gpt-4o-mini)
│     Input tokens: ~3000
│     Output tokens: ~800
│     Cost: $0.015
│
└─ Span: feedback_collection
   └─ Score: user_feedback (like/dislike)
```

### Implementation

```python
# backend/app/services/recommendation_engine.py
from langfuse.decorators import observe, langfuse_context

@observe()
async def get_recommendations(
    session_id: str,
    initial_query: str,
    follow_up_answers: dict,
    user_books: list = None
):
    """Main RAG pipeline with Langfuse tracing"""
    
    # Set session-level metadata
    langfuse_context.update_current_trace(
        session_id=session_id,
        user_id=None,  # Anonymous
        metadata={
            "has_csv": user_books is not None,
            "query_length": len(initial_query)
        }
    )
    
    # Step 1: Retrieval
    candidates = await retrieve_books(initial_query, follow_up_answers, user_books)
    
    # Step 2: Generation
    recommendations = await generate_recommendations(initial_query, candidates)
    
    return recommendations

@observe()
async def retrieve_books(query: str, answers: dict, user_books: list):
    """Vector search with Langfuse tracing"""
    # Implementation...
    pass

@observe()
async def generate_recommendations(query: str, candidates: list):
    """LLM generation with Langfuse tracing"""
    # Implementation...
    pass
```

### Evaluation Scores

**User Feedback (Primary):**
User feedback (like/dislike) is stored **only in Langfuse**, not in PostgreSQL.

```python
# When user clicks like/dislike
from app.core.langfuse_client import langfuse

# Fetch recommendation from PostgreSQL to get trace_id
recommendation = db.query(Recommendation).filter_by(id=recommendation_id).first()

# Send feedback to Langfuse
langfuse.score(
    trace_id=recommendation.trace_id,
    name="user_feedback",
    value=1 if feedback_type == "like" else 0,
    comment=f"User {feedback_type}d recommendation {recommendation_id}"
)
```

**Automatic Evaluations:**
```python
# Confidence score evaluation (logged during recommendation generation)
langfuse.score(
    trace_id=trace_id,
    name="recommendation_confidence",
    value=confidence_score,
    comment=f"Cosine similarity: {confidence_score}%"
)

# Retrieval quality evaluation
langfuse.score(
    trace_id=trace_id,
    name="retrieval_quality",
    value=average_similarity_of_top_10,
    comment=f"Average similarity of top 10 candidates"
)
```

**Why Langfuse-only for feedback:**
- Centralizes all observability data in one platform
- Enables rich analytics and dashboards in Langfuse UI
- Avoids data duplication between PostgreSQL and Langfuse
- PostgreSQL recommendations table maintains link via `trace_id` for lookups

### Prompt Management

Store system prompts in Langfuse for versioning:

```python
# Fetch prompt from Langfuse
prompt = langfuse.get_prompt("book_recommendation_v2")

# Use in LLM call
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": prompt.compile()},
        {"role": "user", "content": user_query}
    ]
)
```

### Datasets

Create test datasets for regression testing:

```python
# Dataset: golden_recommendations
# Items: Known user preferences → Expected book recommendations
# Run batch evaluations on prompt changes
```

---

## 9. CSV Processing Workflow

### Goodreads CSV Format (Expected Columns)
```
ISBN, Title, Author, My Rating, Date Read, ...
```

### Processing Steps

**1. User Uploads CSV**
```python
# API receives CSV file
session_id = str(uuid4())

# Store initial session in Redis
redis_client.setex(
    f"session:{session_id}",
    3600,  # 1 hour TTL
    json.dumps({
        "initial_query": user_query,
        "csv_uploaded": True,
        "created_at": datetime.utcnow().isoformat()
    })
)

# Set CSV status
redis_client.setex(f"session:{session_id}:csv_status", 3600, "pending")

# Trigger async Celery task
process_csv_task.delay(session_id, csv_file_path)
```

**2. Async Worker Processing**

```python
# Celery task
@celery.task
def process_csv_task(session_id: str, csv_path: str):
    # Update status
    redis_client.set(f"session:{session_id}:csv_status", "processing")
    
    # Parse CSV
    df = pd.read_csv(csv_path)
    user_book_ids = []
    new_books_added = 0
    
    for idx, row in df.iterrows():
        isbn = row['ISBN']
        
        # Step 1: Check if book exists in PostgreSQL
        existing_book = db.query(Book).filter_by(isbn=isbn).first()
        
        if existing_book:
            user_book_ids.append(existing_book.id)
            continue
        
        # Step 2: Fetch from Google Books API
        book_data = fetch_from_google_books(isbn)
        
        if not book_data:
            logger.warning(f"ISBN {isbn} not found in Google Books")
            continue
        
        # Step 3: Insert into PostgreSQL
        new_book = Book(
            isbn=isbn,
            title=book_data['title'],
            author=book_data['author'],
            description=book_data['description'],
            categories=book_data['categories'],
            cover_url=book_data['cover_url']
        )
        db.add(new_book)
        db.commit()
        
        # Step 4: Generate embedding
        text = f"{new_book.title} by {new_book.author}. {new_book.description}"
        embedding = create_embedding(text)
        
        # Step 5: Update book with embedding
        new_book.embedding = embedding
        db.commit()
        
        user_book_ids.append(new_book.id)
        new_books_added += 1
        
        # Update progress
        redis_client.setex(
            f"session:{session_id}:metadata",
            3600,
            json.dumps({
                "total_books_in_csv": len(df),
                "books_processed": idx + 1,
                "new_books_added": new_books_added
            })
        )
    
    # Update session with user book IDs
    session_data = json.loads(redis_client.get(f"session:{session_id}"))
    session_data["books_from_csv"] = user_book_ids
    redis_client.setex(f"session:{session_id}", 3600, json.dumps(session_data))
    
    # Mark as completed
    redis_client.setex(f"session:{session_id}:csv_status", 3600, "completed")
```

**3. Google Books API Fetch**
```python
def fetch_from_google_books(isbn: str) -> dict:
    response = requests.get(
        f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}",
        params={"key": GOOGLE_BOOKS_API_KEY}
    )
    
    if response.status_code != 200 or not response.json().get('items'):
        return None
    
    book = response.json()['items'][0]['volumeInfo']
    
    return {
        "title": book.get('title'),
        "author": ", ".join(book.get('authors', [])),
        "description": book.get('description', ''),
        "categories": book.get('categories', []),
        "cover_url": book.get('imageLinks', {}).get('thumbnail')
    }
```

**4. Embedding Generation**
```python
def create_embedding(text: str) -> list:
    from openai import OpenAI
    client = OpenAI()
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    
    return response.data[0].embedding
```

### Error Handling
- **ISBN not found in Google Books:** Log warning, skip book, continue processing
- **API rate limit:** Implement exponential backoff with retry logic
- **Invalid CSV format:** Return error immediately, set status to "failed"
- **Redis session expired during processing:** Worker logs error, gracefully exits

### Session Expiration Considerations
- **Scenario:** CSV processing takes 5 minutes, but session TTL is 1 hour
- **Approach:** Worker extends TTL if processing is still active
  ```python
  # Every 30 seconds during processing
  redis_client.expire(f"session:{session_id}", 3600)
  redis_client.expire(f"session:{session_id}:csv_status", 3600)
  ```

---

## 10. Recommendation Algorithm

### Input
- Session ID (from Redis: user query + answers + user book IDs if CSV uploaded)
- 300k Google Books database in PostgreSQL

### Process

**Step 1: Retrieve Session Data from Redis**
```python
# Fetch session from Redis
session_data = json.loads(redis_client.get(f"session:{session_id}"))

initial_query = session_data["initial_query"]
follow_up_answers = session_data.get("follow_up_answers", {})
user_book_ids = session_data.get("books_from_csv", [])
```

**Step 2: Query Embedding**
```python
# Combine user input into rich query
combined_query = f"""
User wants: {initial_query}
Preferences: {format_answers(follow_up_answers)}
"""

# Create embedding using OpenAI
query_embedding = create_embedding(combined_query)
```

**Step 3: Vector Search**
```sql
-- Search user's books (if CSV uploaded)
SELECT 
    b.*, 
    1 - (b.embedding <=> :query_embedding::vector) as similarity
FROM books b
WHERE b.id = ANY(:user_book_ids)
ORDER BY b.embedding <=> :query_embedding::vector
LIMIT 10;

-- Search Google Books database (all books)
SELECT 
    b.*, 
    1 - (b.embedding <=> :query_embedding::vector) as similarity
FROM books b
ORDER BY b.embedding <=> :query_embedding::vector
LIMIT 10;
```

**Step 4: Combine & Re-rank**
```python
# Merge results from both sources
all_candidates = user_books + google_books

# Remove duplicates (if user's CSV book also in top Google results)
unique_candidates = deduplicate_by_isbn(all_candidates)

# Sort by similarity score
unique_candidates.sort(key=lambda x: x['similarity'], reverse=True)

# Keep top 20
top_candidates = unique_candidates[:20]
```

**Step 5: LLM Ranking & Generation**
```python
# Format candidates for LLM
books_context = format_books_for_llm(top_candidates)

prompt = f"""
You are a book recommendation expert.

User's request: {initial_query}
User's preferences: {format_answers(follow_up_answers)}

Retrieved books (top 20 by semantic similarity):
{books_context}

Task:
1. Select the TOP 3 books that best match the user's preferences
2. For each book, provide:
   - Use the provided cosine similarity as confidence score (0-100)
   - Write a personalized explanation (2-3 sentences) of why this book matches their request

Format your response as JSON:
{{
  "recommendations": [
    {{
      "isbn": "...",
      "confidence_score": 87.5,
      "explanation": "...",
      "rank": 1
    }},
    ...
  ]
}}
"""

# Call LLM with Langfuse tracing
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT}, 
        {"role": "user", "content": prompt}
    ]
)

# Parse LLM response
recommendations = parse_llm_response(response.choices[0].message.content)
```

**Step 6: Store & Return**
```python
# Store in PostgreSQL with trace_id
for rec in recommendations:
    db_rec = Recommendation(
        session_id=session_id,
        book_id=rec['book_id'],
        confidence_score=rec['confidence_score'],
        explanation=rec['explanation'],
        rank=rec['rank'],
        trace_id=langfuse_trace_id
    )
    db.add(db_rec)

db.commit()

return recommendations
```

### Performance Optimizations

**Vector Index:**
```sql
-- Use IVFFlat index for fast approximate nearest neighbor search
CREATE INDEX idx_books_embedding ON books 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- For 300k books, this reduces search time from ~5s to ~100ms
```

**Batch Embedding:**
```python
# When processing CSV, batch embeddings to reduce API calls
texts = [format_book_text(book) for book in books_batch]

# Create embeddings in batch (up to 2048 inputs per request)
embeddings = openai.embeddings.create(
    model="text-embedding-3-small",
    input=texts
)
```

---

## 11. Success Criteria

### MVP Success Metrics

**User Experience:**
- [ ] User can submit query and get recommendations in <10 seconds (without CSV)
- [ ] User can upload CSV and get recommendations in <60 seconds (for 100 books)
- [ ] Recommendations display with confidence scores and explanations
- [ ] User can provide feedback (like/dislike)

**Technical:**
- [ ] All API endpoints functional and documented
- [ ] PostgreSQL schema implemented with 2 tables (books, recommendations)
- [ ] Redis session management working with 1-hour TTL
- [ ] pgvector index optimized for 300k+ books
- [ ] Vector search returns relevant results (cosine similarity >0.7)
- [ ] Langfuse tracing captures full RAG pipeline
- [ ] CSV processing handles 1000+ books without failure
- [ ] User feedback flows to Langfuse via trace_id

**Langfuse Observability:**
- [ ] Traces show retrieval + generation steps
- [ ] User feedback flows into Langfuse scores
- [ ] Cost tracking per recommendation visible
- [ ] Sessions properly tracked

### Performance Targets
- **API Response Time:** <3s for recommendations (excluding CSV processing)
- **Vector Search:** <500ms for 300k books
- **CSV Processing:** ~100 books/minute
- **Embedding Generation:** Batch processing for efficiency

---

## 12. Out of Scope (Post-MVP)

- User authentication
- Persistent user accounts
- Recommendation history
- Multi-session refinement
- Social features (sharing, comparing)
- Mobile app
- Recommendation explanations beyond LLM output
- Advanced filters (publication date, page count, etc.)
- Integration with library systems
- Reading progress tracking

---

## 13. Assumptions

1. **Pre-embedded 300k Books:** Google Books database is already embedded and stored in PostgreSQL with pgvector
2. **ISBN Availability:** All books have valid ISBN identifiers (ISBN-10 or ISBN-13)
3. **Google Books API Access:** Sufficient quota for fetching book metadata (~100 requests/day for typical usage)
4. **OpenAI API Access:** Active API key with sufficient credits for embeddings and LLM generation
5. **Langfuse Account:** Active Langfuse Cloud account with API keys configured
6. **Anonymous Usage:** No user authentication required for MVP - sessions tracked via Redis
7. **Session Lifecycle:** Sessions expire after 1 hour - users must complete recommendation flow within this window
8. **Feedback Stored in Langfuse Only:** No duplicate feedback storage in PostgreSQL
9. **Redis Availability:** Redis must be running for session management and Celery task queue
10. **Recommendations Persist 30 Days:** PostgreSQL recommendations are auto-deleted after 30 days

---

## 14. Environment Variables

### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/leaf

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_SESSION_TTL=3600  # 1 hour in seconds

# OpenAI
OPENAI_API_KEY=sk-...

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Google Books API
GOOGLE_BOOKS_API_KEY=AIza...

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Application
ENVIRONMENT=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3000
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 15. Development Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector extension

### Quick Start

**1. Clone repository**
```bash
git clone <repo>
cd leaf
```

**2. Start databases**
```bash
docker-compose up -d postgres redis
```

**3. Setup backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

**4. Start Celery worker**
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

**5. Setup frontend**
```bash
cd frontend
npm install
npm run dev
```

**6. Access application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 16. Next Steps for Implementation

1. **Infrastructure Setup**
   - Install PostgreSQL 15+ with pgvector extension
   - Install Redis 7+
   - Verify 300k books are embedded in PostgreSQL

2. **Database Setup**
   - Run Alembic migrations for books + recommendations tables
   - Verify pgvector index on books.embedding
   - Test vector search performance (should be <200ms for 300k books)

3. **Backend Core**
   - Implement Redis session service (create, read, update with TTL)
   - Build FastAPI routes (sessions, recommendations, feedback)
   - Integrate Langfuse tracing on RAG pipeline
   - Build CSV processing Celery worker

4. **RAG Pipeline**
   - Implement vector search service (pgvector queries)
   - Build recommendation engine with LLM generation
   - Add Langfuse decorators (@observe) on all steps
   - Test end-to-end with sample queries

5. **Frontend**
   - Build three pages: Input → Questions → Recommendations
   - API integration with error handling
   - UI polish with shadcn/ui components
   - Add loading states for CSV processing

6. **Testing**
   - Unit tests for recommendation engine
   - Integration tests for API endpoints
   - Test CSV processing with 100+ books
   - Verify Langfuse traces capture full pipeline

7. **Deployment**
   - Dockerize services (backend, Redis, PostgreSQL, Celery worker)
   - Deploy to staging environment
   - Configure production Langfuse project
   - Set up 30-day retention cleanup job for recommendations

---

**Document Version:** 1.0  
**Last Updated:** December 6, 2024  
**Created for:** Claude Code Implementation