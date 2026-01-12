"""ISBN normalization and validation utilities.

Uses isbnlib for robust ISBN handling. All functions normalize ISBNs
to ISBN-13 format for consistent deduplication and database storage.
"""

import logging

import isbnlib

logger = logging.getLogger(__name__)


def normalize_isbn(isbn: str | None) -> str | None:
    """Normalize an ISBN to ISBN-13 format.

    Handles both ISBN-10 and ISBN-13 inputs, with or without hyphens/spaces.
    Returns None for invalid or empty ISBNs.

    Args:
        isbn: ISBN string (10 or 13 digits, with or without formatting)

    Returns:
        Normalized ISBN-13 string, or None if invalid/empty

    Examples:
        >>> normalize_isbn("0061809632")
        '9780061809637'
        >>> normalize_isbn("978-0-06-180963-7")
        '9780061809637'
        >>> normalize_isbn("invalid")
        None
    """
    if not isbn:
        return None

    # Clean the ISBN (remove hyphens, spaces, etc.)
    cleaned = isbnlib.canonical(isbn)

    if not cleaned:
        logger.debug(f"ISBN '{isbn}' could not be cleaned")
        return None

    # Check if it's a valid ISBN
    if not isbnlib.is_isbn10(cleaned) and not isbnlib.is_isbn13(cleaned):
        logger.debug(f"ISBN '{isbn}' is not a valid ISBN-10 or ISBN-13")
        return None

    # Convert to ISBN-13
    if isbnlib.is_isbn10(cleaned):
        isbn13 = isbnlib.to_isbn13(cleaned)
        if isbn13:
            return isbn13
        logger.debug(f"Failed to convert ISBN-10 '{cleaned}' to ISBN-13")
        return None

    # Already ISBN-13
    return cleaned


def isbn10_to_isbn13(isbn10: str | None) -> str | None:
    """Convert ISBN-10 to ISBN-13.

    Args:
        isbn10: ISBN-10 string

    Returns:
        ISBN-13 string, or None if conversion fails
    """
    if not isbn10:
        return None

    cleaned = isbnlib.canonical(isbn10)

    if not cleaned or not isbnlib.is_isbn10(cleaned):
        return None

    return isbnlib.to_isbn13(cleaned)


def isbn13_to_isbn10(isbn13: str | None) -> str | None:
    """Convert ISBN-13 to ISBN-10 (only works for 978-prefixed ISBNs).

    Args:
        isbn13: ISBN-13 string

    Returns:
        ISBN-10 string, or None if conversion fails (e.g., 979-prefix ISBNs)
    """
    if not isbn13:
        return None

    cleaned = isbnlib.canonical(isbn13)

    if not cleaned or not isbnlib.is_isbn13(cleaned):
        return None

    return isbnlib.to_isbn10(cleaned)


def is_valid_isbn(isbn: str | None) -> bool:
    """Check if a string is a valid ISBN (10 or 13).

    Args:
        isbn: ISBN string to validate

    Returns:
        True if valid ISBN-10 or ISBN-13, False otherwise
    """
    if not isbn:
        return False

    cleaned = isbnlib.canonical(isbn)
    return bool(cleaned and (isbnlib.is_isbn10(cleaned) or isbnlib.is_isbn13(cleaned)))


def get_canonical_isbn(isbn: str | None) -> str | None:
    """Get the canonical (cleaned) form of an ISBN without converting.

    Removes hyphens, spaces, and validates format.

    Args:
        isbn: ISBN string

    Returns:
        Cleaned ISBN string (preserving original length), or None if invalid
    """
    if not isbn:
        return None

    cleaned = isbnlib.canonical(isbn)

    if not cleaned:
        return None

    if isbnlib.is_isbn10(cleaned) or isbnlib.is_isbn13(cleaned):
        return cleaned

    return None
