"""Reset database schema and data.

Drops all tables and recreates them using Alembic migrations.
This is a complete reset - both schema and data are destroyed.

WARNING: This is VERY destructive! All data and schema changes will be lost.

Usage:
    python scripts/reset_db.py
"""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app.models.database import Base


def reset_database():
    """Drop all tables and recreate via Alembic."""
    print("=" * 70)
    print("DATABASE RESET")
    print("=" * 70)
    print("\n⚠️  WARNING: This will:")
    print("  1. Drop ALL tables (schema + data)")
    print("  2. Recreate tables from Alembic migrations")
    print("  3. Reset Alembic version history")
    response = input("\nAre you ABSOLUTELY sure? (type 'RESET' to confirm): ")

    if response != "RESET":
        print("\n❌ Aborted. No changes made.")
        return

    try:
        print("\n🗑️  Step 1: Dropping all tables...")

        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        print("  ✓ All tables dropped")

        # Also drop alembic_version table
        db = SessionLocal()
        try:
            db.execute(text("DROP TABLE IF EXISTS alembic_version"))
            db.commit()
            print("  ✓ Alembic version table dropped")
        finally:
            db.close()

        print("\n📝 Step 2: Running Alembic migrations...")

        # Run Alembic upgrade
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        if result.returncode != 0:
            print(f"\n❌ Alembic migration failed:")
            print(result.stderr)
            sys.exit(1)

        print("  ✓ Migrations applied")

        print("\n" + "=" * 70)
        print("DATABASE RESET COMPLETE")
        print("=" * 70)
        print("✅ Schema recreated from migrations")
        print("✅ Database is empty and ready for seeding")
        print("\nNext steps:")
        print("  python scripts/seed_books.py")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during reset: {e}")
        raise


if __name__ == "__main__":
    reset_database()
