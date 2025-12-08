"""CSV file processing utilities for Goodreads library exports."""

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Goodreads CSV column names
ISBN_COLUMN = "ISBN"
ISBN13_COLUMN = "ISBN13"
TITLE_COLUMN = "Title"
AUTHOR_COLUMN = "Author"
RATING_COLUMN = "My Rating"


def clean_isbn(isbn_value: Any) -> str | None:
    """Clean ISBN value from Goodreads CSV format.

    Goodreads exports ISBNs with Excel formula notation: ="0451490827"
    This function extracts the actual ISBN string.

    Args:
        isbn_value: Raw ISBN value from CSV (can be string, float, or None)

    Returns:
        Cleaned ISBN string or None if invalid/empty
    """
    if pd.isna(isbn_value):
        return None

    isbn_str = str(isbn_value).strip()

    # Handle Goodreads Excel formula format: ="0451490827"
    if isbn_str.startswith('="') and isbn_str.endswith('"'):
        isbn_str = isbn_str[2:-1]  # Remove =" prefix and " suffix

    # Remove any remaining quotes and whitespace
    isbn_str = isbn_str.strip().strip('"').strip("'")

    # Validate it's not empty
    if not isbn_str or isbn_str == "":
        return None

    # Remove hyphens and spaces (ISBNs can be formatted as 978-0-451-49082-7)
    isbn_str = re.sub(r"[\s\-]", "", isbn_str)

    # Validate it contains only digits (and possibly X for ISBN-10)
    if not re.match(r"^[\dX]+$", isbn_str, re.IGNORECASE):
        logger.warning(f"Invalid ISBN format: {isbn_str}")
        return None

    return isbn_str


def parse_goodreads_csv(file_path: Path) -> list[dict[str, Any]]:
    """Parse Goodreads library export CSV file.

    Args:
        file_path: Path to the CSV file

    Returns:
        List of book dictionaries with structure:
        [
            {
                'isbn': str | None,
                'isbn13': str | None,
                'title': str,
                'author': str,
                'user_rating': int  # 0-5
            },
            ...
        ]

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV is malformed or missing required columns
    """
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    try:
        # Read CSV with pandas
        df = pd.read_csv(file_path)

        # Validate required columns exist
        required_columns = [ISBN_COLUMN, ISBN13_COLUMN, TITLE_COLUMN, AUTHOR_COLUMN, RATING_COLUMN]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"CSV missing required columns: {missing_columns}")

        books = []
        skipped_count = 0

        for idx, row in df.iterrows():
            # Clean ISBNs
            isbn = clean_isbn(row[ISBN_COLUMN])
            isbn13 = clean_isbn(row[ISBN13_COLUMN])

            # Skip books with no valid ISBN at all
            if not isbn and not isbn13:
                skipped_count += 1
                logger.debug(f"Skipping row {idx}: No valid ISBN found for '{row[TITLE_COLUMN]}'")
                continue

            # Extract title and author
            title = str(row[TITLE_COLUMN]).strip() if pd.notna(row[TITLE_COLUMN]) else "Unknown Title"
            author = str(row[AUTHOR_COLUMN]).strip() if pd.notna(row[AUTHOR_COLUMN]) else "Unknown Author"

            # Parse user rating (0-5 scale)
            try:
                user_rating = int(row[RATING_COLUMN]) if pd.notna(row[RATING_COLUMN]) else 0
                # Clamp to valid range
                user_rating = max(0, min(5, user_rating))
            except (ValueError, TypeError):
                logger.warning(f"Invalid rating for '{title}': {row[RATING_COLUMN]}, defaulting to 0")
                user_rating = 0

            books.append({
                "isbn": isbn,
                "isbn13": isbn13,
                "title": title,
                "author": author,
                "user_rating": user_rating
            })

        logger.info(
            f"Parsed {len(books)} books from CSV (skipped {skipped_count} books without ISBNs)"
        )
        return books

    except pd.errors.EmptyDataError:
        raise ValueError("CSV file is empty")
    except pd.errors.ParserError as e:
        raise ValueError(f"Failed to parse CSV: {e}")
    except Exception as e:
        logger.error(f"Unexpected error parsing CSV: {e}")
        raise


def validate_csv_file(file_path: Path, max_size_mb: int = 10) -> None:
    """Validate CSV file before processing.

    Args:
        file_path: Path to the CSV file
        max_size_mb: Maximum allowed file size in megabytes

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is too large or has wrong extension
    """
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    # Check file extension
    if file_path.suffix.lower() != ".csv":
        raise ValueError(f"Invalid file extension: {file_path.suffix}. Expected .csv")

    # Check file size
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        raise ValueError(
            f"CSV file too large: {file_size_mb:.2f}MB. Maximum allowed: {max_size_mb}MB"
        )

    logger.info(f"CSV file validation passed: {file_path.name} ({file_size_mb:.2f}MB)")
