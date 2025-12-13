# Leaf - AI-Native Book Recommender

![Version](https://img.shields.io/badge/version-1.0.0-blue) ![Python](https://img.shields.io/badge/python-3.13%2B-blue) ![Node.js](https://img.shields.io/badge/node.js-18%2B-brightgreen) ![FastAPI](https://img.shields.io/badge/FastAPI-0.124.0-009688) ![Next.js](https://img.shields.io/badge/Next.js-16.0.7-black)

---

Leaf is a conversational book recommendation system that provides personalized book suggestions by analyzing user preferences through natural language queries and Goodreads reading history.

## Features

- 💬 **Natural Language Queries**: Describe what you're looking for in plain English
- 📚 **Goodreads Integration**: Upload your Goodreads library CSV for personalized recommendations
- 🧠 **Advanced RAG Pipeline**: Combines semantic search, collaborative filtering, and quality scoring
- ✨ **Intelligent Recommendations**: Get 3 curated book suggestions with confidence scores and explanations
- 👁️ **Full Observability**: Complete request tracing and user feedback collection via Langfuse
- ⚡ **Async Processing**: Background workers handle CSV uploads for seamless UX

## Tech Stack

### 🎨 Frontend
- **Next.js 16.0.7** (App Router) with TypeScript and React 19
- **Tailwind CSS 4** + **shadcn/ui** components
- **Biome** for linting and formatting

### ⚙️ Backend
- **FastAPI** with Python 3.13
- **PostgreSQL 16** with pgvector extension for vector similarity search
- **Redis 7** for session management and Celery queue
- **Celery** for async CSV processing
- **OpenAI** (text-embedding-3-small + GPT-4o-mini)
- **Langfuse** for observability and feedback collection
- **SQLAlchemy 2.0** ORM with Alembic migrations

### 🗄️ Infrastructure
- **Docker Compose** for local development
- **Nginx** reverse proxy for production deployment
- **Let's Encrypt** SSL certificates

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.13+ (for backend development)
- Node.js 18+ (for frontend development)
- OpenAI API key
- Langfuse account (for observability)
- Google Books API key (for book metadata)

### 1️⃣ Clone and Setup

```bash
git clone <repository-url>
cd leaf
```

### 2️⃣ Start Infrastructure

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3️⃣ Backend Setup

See [backend/README.md](backend/README.md) for detailed instructions.

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Run migrations
alembic upgrade head

# Start backend server
uvicorn main:app --reload

# In a separate terminal, start Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

Backend will be available at http://localhost:8000

### 4️⃣ Frontend Setup

See [frontend/README.md](frontend/README.md) for detailed instructions.

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local if needed

# Start development server
npm run dev
```

Frontend will be available at http://localhost:3000

## Project Structure

```
leaf/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/routes/        # API endpoints (sessions, recommendations, feedback)
│   │   ├── core/              # Infrastructure (database, Redis, Langfuse, embeddings)
│   │   ├── services/          # Business logic (RAG engine, vector search, book service)
│   │   ├── workers/           # Celery tasks (async CSV processing)
│   │   ├── models/            # SQLAlchemy ORM + Pydantic schemas
│   │   └── utils/             # Utilities (CSV processor)
│   ├── alembic/               # Database migrations
│   ├── scripts/               # Data collection and seeding scripts
│   ├── tests/                 # Unit and integration tests
│   └── README.md              # Detailed backend documentation
│
├── frontend/                   # Next.js Frontend
│   ├── src/app/
│   │   ├── page.tsx           # Input page (query + CSV upload)
│   │   ├── questions/         # Follow-up questions page
│   │   ├── recommendations/   # Recommendations display
│   │   └── components/        # Reusable UI components
│   └── README.md              # Detailed frontend documentation
│
├── docker-compose.yml          # Local development infrastructure
├── docker-compose.prod.yml     # Production deployment configuration
├── PRODUCT.md                  # Complete product specification
├── DEPLOYMENT.md               # Production deployment guide
├── CLAUDE.md                   # Claude Code development guide
└── README.md                   # This file
```

## How It Works

### 📝 1. User Input
Users describe what they're looking for and optionally upload their Goodreads library CSV.

### 🧠 2. RAG Pipeline
The backend implements a sophisticated 4-stage pipeline:

1. **Query Understanding** - Combines user's query with follow-up answers
2. **Intelligent Retrieval** - Multi-stage enhancement:
   - Semantic filtering (query-relevant favorites only)
   - Dynamic collaborative weighting (adapts to signal strength)
   - Quality scoring (metadata-based ranking)
   - Dislike penalties (avoids books similar to low ratings)
3. **LLM Generation** - GPT-4o-mini selects top 3 books with personalized explanations
4. **Storage** - Saves recommendations with Langfuse trace linking

### ✨ 3. Personalized Results
Users receive 3 book recommendations with:
- Confidence scores (based on similarity + quality)
- Detailed explanations referencing their reading history
- Book metadata (cover, description, categories, ratings)
- Like/dislike feedback options

### 📊 4. Observability
All requests are fully traced in Langfuse with hierarchical spans showing:
- Query processing
- Vector search operations
- Quality scoring and filtering
- LLM generation
- User feedback as evaluation scores

---

## Development

### 🧪 Run Tests

```bash
# Backend tests
cd backend
pytest                          # All tests
pytest tests/unit/ -v           # Unit tests only
pytest tests/integration/ -v    # Integration tests
pytest --cov=app               # With coverage

# Frontend tests
cd frontend
npm test
```

### 🗄️ Database Utilities

```bash
cd backend

# Seed sample books for testing
python scripts/seed_books.py

# Load production datasets
python scripts/data_collection/seed_goodreads_10k.py
python scripts/data_collection/collect_nyt_bestsellers.py

# Clear all data (preserve schema)
python scripts/clear_db.py

# Drop and recreate schema (DESTRUCTIVE)
python scripts/reset_db.py
```

### 📚 API Documentation

When the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Documentation

- 📖 **[backend/README.md](backend/README.md)** - Comprehensive backend documentation including:
  - Advanced RAG pipeline details
  - Configuration parameters and tuning
  - Database schema and indexing
  - API endpoints and usage
  - Langfuse tracing architecture

- 🎨 **[frontend/README.md](frontend/README.md)** - Frontend setup and development

- 📋 **[PRODUCT.md](PRODUCT.md)** - Complete product specification including:
  - User flow and UX design
  - Technical architecture
  - Data models and API contracts
  - Implementation roadmap

- 💻 **[CLAUDE.md](CLAUDE.md)** - Development guide for Claude Code

---

## Environment Variables

### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql://leaf_user:leaf_password@localhost:5432/leaf

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_SESSION_TTL=3600

# OpenAI
OPENAI_API_KEY=sk-...

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Google Books API
GOOGLE_BOOKS_API_KEY=AIza...

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# CORS
ALLOWED_ORIGINS=http://localhost:3000
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Architecture Highlights

### 🔐 Session Management
- **Redis-based sessions** with 1-hour TTL
- Standalone sessions (no persistent user accounts in MVP)
- Automatic session extension during CSV processing

### 🔍 Vector Search
- **pgvector** with IVFFlat index for fast similarity search
- 1536-dimensional embeddings (OpenAI text-embedding-3-small)
- Cosine similarity for semantic matching

### 📊 Data Pipeline
- **Async CSV processing** via Celery workers
- **Google Books API** integration for metadata enrichment
- **Automatic embedding generation** for new books
- **Progress tracking** with real-time status updates

### 🎯 Recommendation Quality
- **Quality scoring** based on metadata completeness
- **Semantic filtering** to avoid irrelevant favorites
- **Dislike penalties** to avoid similar books
- **Dynamic weighting** that adapts to signal strength

---

## Current Status

**🚀 Production-Ready (v2.0.0)**

All core features implemented and tested:
- ✅ Advanced RAG pipeline with personalization
- ✅ Full Langfuse observability
- ✅ Async CSV processing
- ✅ Comprehensive test coverage (29 unit tests + integration tests)
- ✅ Production deployment configuration
- ✅ Complete documentation
