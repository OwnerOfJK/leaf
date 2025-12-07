"""Clear all data from the database while preserving schema.

Deletes all records from books and recommendations tables.
Use this to start fresh without running migrations again.

WARNING: This is destructive! All data will be lost.

Usage:
    python scripts/clear_db.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.database import SessionLocal


def clear_database():
    """Clear all data from database tables."""
    db = SessionLocal()

    try:
        print("=" * 70)
        print("CLEARING DATABASE")
        print("=" * 70)
        print("\n⚠️  WARNING: This will delete ALL data from the database!")
        response = input("Are you sure you want to continue? (yes/no): ")

        if response.lower() != "yes":
            print("\n❌ Aborted. No changes made.")
            return

        print("\n🗑️  Deleting data...")

        # Delete in correct order (recommendations reference books)
        result = db.execute(text("DELETE FROM recommendations"))
        recommendations_deleted = result.rowcount
        print(f"  ✓ Deleted {recommendations_deleted} recommendations")

        result = db.execute(text("DELETE FROM books"))
        books_deleted = result.rowcount
        print(f"  ✓ Deleted {books_deleted} books")

        db.commit()

        print("\n" + "=" * 70)
        print("DATABASE CLEARED")
        print("=" * 70)
        print(f"Total records deleted: {books_deleted + recommendations_deleted}")
        print("Schema preserved. Tables still exist.")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during clearing: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    clear_database()
