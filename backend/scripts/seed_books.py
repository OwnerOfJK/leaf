"""Seed sample books for development and testing.

Adds a curated set of books with embeddings to test the recommendation system.
Safe to run multiple times - skips books that already exist.

Usage:
    python scripts/seed_books.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.core.embeddings import create_embedding, format_book_text
from app.services.book_service import create_book, get_book_by_isbn

# Sample books for testing
SAMPLE_BOOKS = [
    {
        "isbn": "9780451524935",
        "title": "1984",
        "author": "George Orwell",
        "description": "A dystopian social science fiction novel and cautionary tale about the dangers of totalitarianism.",
        "categories": ["Fiction", "Dystopian", "Science Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg",
    },
    {
        "isbn": "9780061120084",
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "description": "A novel about racial injustice and childhood innocence in the American South.",
        "categories": ["Fiction", "Classic", "Historical"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780061120084-L.jpg",
    },
    {
        "isbn": "9780547928227",
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "description": "A fantasy novel about a hobbit's unexpected adventure to reclaim a treasure guarded by a dragon.",
        "categories": ["Fantasy", "Adventure", "Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780547928227-L.jpg",
    },
    {
        "isbn": "9780316769488",
        "title": "The Catcher in the Rye",
        "author": "J.D. Salinger",
        "description": "A story about teenage rebellion and alienation narrated by Holden Caulfield.",
        "categories": ["Fiction", "Classic", "Coming of Age"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780316769488-L.jpg",
    },
    {
        "isbn": "9780142437239",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "description": "A romantic novel about manners, marriage, and morality in Georgian England.",
        "categories": ["Romance", "Classic", "Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780142437239-L.jpg",
    },
    {
        "isbn": "9780553418026",
        "title": "A Brief History of Time",
        "author": "Stephen Hawking",
        "description": "A landmark volume in science writing that explores cosmology and the universe.",
        "categories": ["Science", "Physics", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780553418026-L.jpg",
    },
    {
        "isbn": "9780062316097",
        "title": "Sapiens: A Brief History of Humankind",
        "author": "Yuval Noah Harari",
        "description": "An exploration of the history of the human species from the Stone Age to the modern age.",
        "categories": ["History", "Non-Fiction", "Anthropology"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg",
    },
    {
        "isbn": "9780062073488",
        "title": "The Alchemist",
        "author": "Paulo Coelho",
        "description": "A philosophical novel about a shepherd's journey to find treasure and discover his destiny.",
        "categories": ["Fiction", "Philosophy", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062073488-L.jpg",
    },
    {
        "isbn": "9780441172719",
        "title": "Dune",
        "author": "Frank Herbert",
        "description": "A science fiction epic about politics, religion, and ecology on the desert planet Arrakis.",
        "categories": ["Science Fiction", "Fantasy", "Epic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780441172719-L.jpg",
    },
    {
        "isbn": "9780345391803",
        "title": "The Hitchhiker's Guide to the Galaxy",
        "author": "Douglas Adams",
        "description": "A comedic science fiction series following Arthur Dent's intergalactic adventures.",
        "categories": ["Science Fiction", "Comedy", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780345391803-L.jpg",
    },
]


def seed_books():
    """Seed sample books into the database."""
    db = SessionLocal()
    books_added = 0
    books_skipped = 0

    try:
        print("=" * 70)
        print("SEEDING SAMPLE BOOKS")
        print("=" * 70)
        print(f"\nProcessing {len(SAMPLE_BOOKS)} books...\n")

        for i, book_data in enumerate(SAMPLE_BOOKS, 1):
            # Check if book already exists
            existing = get_book_by_isbn(db, book_data["isbn"])
            if existing:
                print(f"[{i}/{len(SAMPLE_BOOKS)}] ⏭️  {book_data['title']} (already exists)")
                books_skipped += 1
                continue

            # Create embedding from book text
            book_text = format_book_text(
                title=book_data["title"],
                author=book_data["author"],
                description=book_data["description"],
            )
            embedding = create_embedding(book_text)

            # Create book
            create_book(
                db=db,
                isbn=book_data["isbn"],
                title=book_data["title"],
                author=book_data["author"],
                description=book_data["description"],
                categories=book_data["categories"],
                cover_url=book_data["cover_url"],
                embedding=embedding,
            )

            print(f"[{i}/{len(SAMPLE_BOOKS)}] ✅ {book_data['title']} by {book_data['author']}")
            books_added += 1

        db.commit()

        print("\n" + "=" * 70)
        print("SEEDING COMPLETE")
        print("=" * 70)
        print(f"✅ Added: {books_added} books")
        print(f"⏭️  Skipped: {books_skipped} books (already exist)")
        print(f"📚 Total: {books_added + books_skipped} books in database")
        print("=" * 70)

        return books_added

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_books()
