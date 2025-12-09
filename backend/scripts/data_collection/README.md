# Data Collection Documentation

This directory contains scripts for populating the Leaf database with book data from multiple sources. The goal is to build a diverse corpus of ~10,000-15,000 books with rich metadata and embeddings for the RAG recommendation engine.

## Data Sources Overview

We collect books from two primary sources:

1. **Goodreads 10k Dataset** (~10,000 books)
   - Source: https://github.com/zygmuntz/goodbooks-10k
   - Location: `backend/data/books.csv`
   - Contains: Popular books with ISBNs, titles, authors, Goodreads metadata
   - Priority: Process this first to establish base corpus

2. **New York Times Bestsellers** (~3,000-5,000 unique books)
   - Source: NYT Books API
   - Time range: Weekly bestseller lists from 2008-2025
   - Contains: Current and historically popular books across all categories
   - Rate limits: 5 requests/min, 500 requests/day

## Data Deduplication Strategy

**Primary Key: ISBN (not ISBN13)**
- All deduplication is based on the `isbn` field in the database
- Books are processed in source priority order (Goodreads 10k → NYT)
- If a book's ISBN already exists in the database, skip it entirely (no updates)
- Books without an ISBN are skipped entirely

**Why this approach:**
- Ensures first source's data is preserved
- Avoids unnecessary Google Books API calls for duplicates
- Simple and predictable behavior

## Data Enrichment Flow

For each book from any source:

1. **Check if ISBN exists** in PostgreSQL `books` table
   - If exists: skip (do not update)
   - If not exists: continue to step 2

2. **Fetch metadata from Google Books API** using ISBN
   - If found: use Google Books data for all fields
   - If not found: skip this book (do not add partial data)

3. **Generate embeddings in batches** using OpenAI text-embedding-3-small
   - Collect multiple books (batch size: 100-500 books recommended)
   - Format each: `{title} by {author}. {description}`
   - Send all texts in a single API call (OpenAI supports up to 2048 inputs per request)
   - Dimensions: 1536 per embedding

4. **Store in database** with:
   - All metadata from Google Books API
   - Embedding vector
   - `data_source` field indicating origin (e.g., "goodreads_10k", "nyt_bestseller")

## Metadata and Ratings Policy

**Google Books API as Single Source of Truth:**
- All metadata (title, author, description, categories, etc.) comes from Google Books API
- All ratings (`average_rating`, `ratings_count`) come from Google Books API only
- Goodreads ratings from `books.csv` are ignored entirely
- If Google Books doesn't provide a rating, leave as NULL (do not use Goodreads rating)

**Rationale:**
- Ensures consistency across all books in the database
- Avoids bias toward books with Goodreads data
- Makes all books equally comparable in the recommendation engine

## Rate Limiting and Quotas

### Google Books API
- **Current quota:** Free tier (exact limits not published by Google)
- **Estimated usage:** ~10,000 requests for initial load
- **Strategy:** Process in batches, monitor for 429 errors, implement exponential backoff (already in `google_books_api.py`)
- **Note:** Defer optimization until we hit limits. Current implementation handles rate limiting gracefully.

### NYT Books API
- **Rate limits:** 5 requests/min, 500 requests/day
- **Strategy:**
  - Sleep 12 seconds between requests (5 req/min = 1 req/12s)
  - Batch requests by category/year to minimize total calls (~360 requests estimated)
  - Track progress to resume if hitting daily limit
- **Estimated timeline:** ~2 days for complete historical data (500/day × 2)

## Implementation Scripts

### 1. `seed_goodreads_10k.py`
**Purpose:** Load the 10,000 books from `backend/data/books.csv`

**Process:**
1. Read CSV file
2. For each book:
   - Check if ISBN exists in database
   - If not exists: fetch from Google Books API
   - Accumulate in batch buffer (size: 100-500 books)
3. When batch is full:
   - Generate embeddings for entire batch in single OpenAI API call
   - Bulk insert books with embeddings into database with `data_source="goodreads_10k"`
4. Log progress and statistics

**Expected runtime:** ~1-2 hours (with batch embedding generation)

**Usage:**
```bash
cd backend
python scripts/data_collection/seed_goodreads_10k.py
```

### 2. `collect_nyt_bestsellers.py`
**Purpose:** Fetch NYT bestseller lists from 2008-2025

**Process:**
1. Fetch all available category lists from NYT API
2. For each category and week from 2008-2025:
   - Fetch bestseller list (with 12s sleep between requests)
   - Extract ISBN, title, author
   - Check if ISBN exists in database
   - If not exists: fetch from Google Books API and accumulate in batch buffer
3. When batch is full (100-500 books):
   - Generate embeddings for entire batch in single OpenAI API call
   - Bulk insert books with embeddings into database with `data_source="nyt_bestseller"`
4. Track progress to handle 500/day limit
5. Support resume from last processed date

**Expected runtime:** ~2 days (rate limited by NYT API)

**Usage:**
```bash
cd backend
python scripts/data_collection/collect_nyt_bestsellers.py

# Resume from checkpoint
python scripts/data_collection/collect_nyt_bestsellers.py --resume
```

## Database Schema

Books are stored in the `books` table with the following key fields:

```python
class Book(Base):
    __tablename__ = "books"

    # Identity
    id: int                          # Auto-increment primary key
    isbn: str                        # Primary deduplication key
    isbn13: str | None              # Secondary identifier

    # Core Metadata (from Google Books)
    title: str
    author: str
    description: str | None
    categories: List[str] | None
    page_count: int | None
    publisher: str | None
    publication_year: int | None
    language: str | None

    # Ratings (from Google Books ONLY)
    average_rating: float | None    # Google Books rating (1-5)
    ratings_count: int | None       # Number of ratings

    # Media
    cover_url: str | None

    # AI/ML
    embedding: Vector(1536) | None  # OpenAI text-embedding-3-small

    # Metadata
    data_source: str | None         # "goodreads_10k" | "nyt_bestseller"
    created_at: datetime
    updated_at: datetime
```

## Processing Order and Priority

1. **Phase 1: Goodreads 10k** (PRIORITY)
   - Establish base corpus of popular books
   - Most complete metadata in source CSV
   - Run first to avoid deduplication issues

2. **Phase 2: NYT Bestsellers**
   - Add contemporary bestsellers
   - Fills gaps in recent publications (2008-2025)
   - Run over 2 days respecting rate limits

## Error Handling

**For all scripts:**
- Log all errors with context (ISBN, title, source)
- Continue processing remaining books on individual failures
- Generate summary report at completion:
  - Total books processed
  - Books added to database
  - Books skipped (already exist)
  - Books failed (no ISBN, not in Google Books, etc.)

**Specific error cases:**
- **No ISBN in source:** Skip book, log warning
- **Google Books API returns no results:** Skip book, log warning
- **Google Books API rate limit (429):** Exponential backoff, retry
- **Database constraint violation:** Log error, continue
- **Network timeout:** Retry with exponential backoff (max 3 attempts)

## Progress Tracking

Each script should:
1. Log progress every N books (e.g., every 100 books)
2. Store checkpoint data for resume capability
3. Generate final statistics report

**Example output:**
```
Processing Goodreads 10k dataset...
[100/10000] Added: 95, Existed: 5, Failed: 0
[200/10000] Added: 187, Existed: 13, Failed: 0
...
[10000/10000] Added: 8234, Existed: 1566, Failed: 200

Summary:
- Total processed: 10,000
- Successfully added: 8,234
- Already existed: 1,566
- Failed (no ISBN): 120
- Failed (not in Google Books): 80
- Processing time: 2h 34m
```

## Testing Strategy

Before running production data collection:

1. **Test with small dataset:** Run script with `--limit 10` flag to verify:
   - Google Books API calls work
   - Embeddings generate correctly
   - Database inserts succeed
   - Error handling works

2. **Verify deduplication:**
   - Run script twice on same small dataset
   - Confirm second run skips all books (0 added)

3. **Check data quality:**
   - Manually inspect 10-20 random books in database
   - Verify metadata completeness
   - Check embedding dimensions (should be 1536)

## References

- **Google Books API:** https://developers.google.com/books/docs/v1/using
- **NYT Books API:** https://developer.nytimes.com/docs/books-product/1/overview
- **Goodreads 10k Dataset:** https://github.com/zygmuntz/goodbooks-10k
- **OpenAI Embeddings:** https://platform.openai.com/docs/guides/embeddings
