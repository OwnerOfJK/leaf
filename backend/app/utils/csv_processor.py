"""CSV file processing utilities for Goodreads library exports."""

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.constants import CSV_UPLOAD_MAX_SIZE_MB

logger = logging.getLogger(__name__)

# Goodreads CSV column names
ISBN_COLUMN = "ISBN"
ISBN13_COLUMN = "ISBN13"
TITLE_COLUMN = "Title"
AUTHOR_COLUMN = "Author"
RATING_COLUMN = "My Rating"
EXCLUSIVE_SHELF_COLUMN = "Exclusive Shelf"


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
                'user_rating': int,  # 0-5
                'exclusive_shelf': str  # 'read', 'to-read', 'currently-reading', etc.
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
        required_columns = [ISBN_COLUMN, ISBN13_COLUMN, TITLE_COLUMN, AUTHOR_COLUMN, RATING_COLUMN, EXCLUSIVE_SHELF_COLUMN]
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

            # Extract exclusive shelf (read, to-read, currently-reading, etc.)
            exclusive_shelf = str(row[EXCLUSIVE_SHELF_COLUMN]).strip().lower() if pd.notna(row[EXCLUSIVE_SHELF_COLUMN]) else "read"

            books.append({
                "isbn": isbn,
                "isbn13": isbn13,
                "title": title,
                "author": author,
                "user_rating": user_rating,
                "exclusive_shelf": exclusive_shelf
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


def parse_goodbooks_10k_csv(file_path: Path) -> list[dict[str, Any]]:
    """Parse goodbooks-10k dataset CSV file.

    This is a different format than personal Goodreads library exports.
    Source: https://github.com/zygmuntz/goodbooks-10k

    Args:
        file_path: Path to the books.csv file

    Returns:
        List of book dictionaries with structure:
        [
            {
                'isbn': str | None,
                'isbn13': str | None,
                'title': str,
                'author': str
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

        # Validate required columns exist (goodbooks-10k format uses lowercase)
        required_columns = ["isbn", "isbn13", "title", "authors"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"CSV missing required columns: {missing_columns}")

        books = []
        skipped_count = 0

        for idx, row in df.iterrows():
            # Clean ISBN (can be numeric or contain 'X' for ISBN-10)
            isbn_raw = row["isbn"]
            isbn = None
            if pd.notna(isbn_raw):
                isbn_str = str(isbn_raw).strip().upper()

                # Check if it contains non-numeric characters (valid for ISBN-10 with X)
                if 'X' in isbn_str or not isbn_str.replace('.', '').replace('e', '').replace('+', '').replace('-', '').isdigit():
                    # It's likely a string ISBN (possibly with X)
                    # Remove any whitespace, hyphens
                    isbn_str = re.sub(r"[\s\-]", "", isbn_str)
                    if isbn_str and isbn_str != "0":
                        isbn = isbn_str
                else:
                    # It's numeric, convert from float/int format
                    try:
                        isbn_str = str(int(float(isbn_raw))).strip()
                        if isbn_str and isbn_str != "0":
                            isbn = isbn_str
                    except (ValueError, OverflowError):
                        logger.warning(f"Failed to parse ISBN for '{row['title']}': {isbn_raw}")

            # Clean ISBN13 (stored in scientific notation like 9.78043902348e+12)
            isbn13_raw = row["isbn13"]
            isbn13 = None
            if pd.notna(isbn13_raw):
                try:
                    # Convert scientific notation to integer, then to string
                    isbn13_int = int(float(isbn13_raw))
                    isbn13 = str(isbn13_int)
                except (ValueError, OverflowError):
                    logger.warning(f"Failed to parse ISBN13 for '{row['title']}': {isbn13_raw}")

            # Skip books with no valid ISBN at all
            if not isbn and not isbn13:
                skipped_count += 1
                logger.debug(f"Skipping row {idx}: No valid ISBN found for '{row['title']}'")
                continue

            # Extract title and author
            title = str(row["title"]).strip() if pd.notna(row["title"]) else "Unknown Title"
            author = str(row["authors"]).strip() if pd.notna(row["authors"]) else "Unknown Author"

            books.append({
                "isbn": isbn,
                "isbn13": isbn13,
                "title": title,
                "author": author
            })

        logger.info(
            f"Parsed {len(books)} books from goodbooks-10k CSV (skipped {skipped_count} books without ISBNs)"
        )
        return books

    except pd.errors.EmptyDataError:
        raise ValueError("CSV file is empty")
    except pd.errors.ParserError as e:
        raise ValueError(f"Failed to parse CSV: {e}")
    except Exception as e:
        logger.error(f"Unexpected error parsing goodbooks-10k CSV: {e}")
        raise


def validate_csv_file(file_path: Path, max_size_mb: int = CSV_UPLOAD_MAX_SIZE_MB) -> None:
    """Validate CSV file before processing.

    Args:
        file_path: Path to the CSV file
        max_size_mb: Maximum allowed file size in megabytes (defaults to CSV_UPLOAD_MAX_SIZE_MB)

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
