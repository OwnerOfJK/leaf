"""Google Books API integration service."""

import logging
import time
from typing import Any

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Google Books API constants
GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"
MAX_RETRIES = 10
RETRY_BACKOFF = [1, 2, 5, 10, 20, 30, 60, 90, 120, 180]  # seconds for each retry


def fetch_from_google_books(isbn: str) -> dict[str, Any] | None:
    """Fetch book metadata from Google Books API using ISBN.

    Args:
        isbn: ISBN-10 or ISBN-13 identifier

    Returns:
        Dictionary containing book metadata, or None if not found or error occurred.
        Structure:
        {
            'isbn': str,
            'isbn13': str | None,
            'title': str,
            'author': str,
            'description': str | None,
            'categories': list[str] | None,
            'page_count': int | None,
            'publisher': str | None,
            'publication_year': int | None,
            'language': str | None,
            'average_rating': float | None,
            'ratings_count': int | None,
            'cover_url': str | None
        }
    """
    params = {
        "q": f"isbn:{isbn}",
        "key": settings.google_books_api_key,
        "maxResults": 1
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)

            # Handle rate limiting
            if response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF[attempt]
                    logger.warning(
                        f"Rate limited by Google Books API (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"QUOTA EXCEEDED: Rate limit for ISBN {isbn} after {MAX_RETRIES} attempts. "
                        f"Google Books quota likely exhausted."
                    )
                    # Return a special marker to indicate quota exhaustion (not just book not found)
                    return "QUOTA_EXCEEDED"

            # Handle other HTTP errors
            if response.status_code != 200:
                logger.error(f"Google Books API returned status {response.status_code} for ISBN {isbn}")
                return None

            # Log successful API call
            logger.info(f"✓ Google Books API call successful for ISBN {isbn} (status: {response.status_code})")

            data = response.json()

            # Check if any books were found
            if data.get("totalItems", 0) == 0:
                logger.info(f"No books found in Google Books for ISBN {isbn}")
                return None

            # Extract the first (and only) volume
            volume = data["items"][0]
            volume_info = volume.get("volumeInfo", {})

            # Extract authors (join multiple authors with ", ")
            authors = volume_info.get("authors", [])
            author = ", ".join(authors) if authors else "Unknown Author"

            # Extract both ISBN-10 and ISBN-13 from Google Books
            isbn10 = extract_isbn10(volume_info)
            isbn13 = extract_isbn13(volume_info)

            # Extract publication year
            publication_year = extract_year(volume_info.get("publishedDate"))

            # Extract cover URL (prefer large thumbnail)
            image_links = volume_info.get("imageLinks", {})
            cover_url = (
                image_links.get("large") or
                image_links.get("medium") or
                image_links.get("thumbnail")
            )

            # Build result dictionary
            result = {
                "isbn": isbn10,  # Use ISBN-10 from Google Books (may be None)
                "isbn13": isbn13,  # Use ISBN-13 from Google Books
                "title": volume_info.get("title", "Unknown Title"),
                "author": author,
                "description": volume_info.get("description"),
                "categories": volume_info.get("categories"),
                "page_count": volume_info.get("pageCount"),
                "publisher": volume_info.get("publisher"),
                "publication_year": publication_year,
                "language": volume_info.get("language"),
                "average_rating": volume_info.get("averageRating"),
                "ratings_count": volume_info.get("ratingsCount"),
                "cover_url": cover_url
            }

            logger.info(f"Successfully fetched metadata for ISBN {isbn}: {result['title']}")
            return result

        except requests.RequestException as e:
            logger.error(f"Network error fetching ISBN {isbn}: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_BACKOFF[attempt]
                logger.info(f"Retrying after network error in {wait_time}s...")
                time.sleep(wait_time)
                continue
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing Google Books response for ISBN {isbn}: {e}")
            return None

    return None


def search_by_title_author(title: str, author: str) -> dict[str, Any] | None:
    """Search Google Books API by title and author.

    Used when no ISBN is available. Returns the first matching result.

    Args:
        title: Book title to search for
        author: Author name to search for

    Returns:
        Dictionary containing book metadata (same structure as fetch_from_google_books),
        or None if not found or error occurred.
    """
    # Build search query using intitle and inauthor operators
    query = f'intitle:"{title}" inauthor:"{author}"'

    params = {
        "q": query,
        "key": settings.google_books_api_key,
        "maxResults": 1,
        "printType": "books",  # Only return books, not magazines
        "langRestrict": "en"   # Prefer English editions
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)

            # Handle rate limiting
            if response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF[attempt]
                    logger.warning(
                        f"Rate limited by Google Books API (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"QUOTA EXCEEDED: Rate limit for '{title}' by '{author}' after {MAX_RETRIES} attempts."
                    )
                    return "QUOTA_EXCEEDED"

            # Handle other HTTP errors
            if response.status_code != 200:
                logger.error(
                    f"Google Books API returned status {response.status_code} "
                    f"for '{title}' by '{author}'"
                )
                return None

            logger.info(
                f"✓ Google Books API search successful for '{title}' by '{author}' "
                f"(status: {response.status_code})"
            )

            data = response.json()

            # Check if any books were found
            if data.get("totalItems", 0) == 0:
                logger.info(f"No books found in Google Books for '{title}' by '{author}'")
                return None

            # Extract the first volume
            volume = data["items"][0]
            volume_info = volume.get("volumeInfo", {})

            # Extract authors (join multiple authors with ", ")
            authors = volume_info.get("authors", [])
            result_author = ", ".join(authors) if authors else "Unknown Author"

            # Extract both ISBN-10 and ISBN-13
            isbn10 = extract_isbn10(volume_info)
            isbn13 = extract_isbn13(volume_info)

            # If no ISBN found, skip this result (we need ISBN for our system)
            if not isbn10 and not isbn13:
                logger.warning(
                    f"Google Books result for '{title}' has no ISBN, skipping"
                )
                return None

            # Extract publication year
            publication_year = extract_year(volume_info.get("publishedDate"))

            # Extract cover URL (prefer large thumbnail)
            image_links = volume_info.get("imageLinks", {})
            cover_url = (
                image_links.get("large") or
                image_links.get("medium") or
                image_links.get("thumbnail")
            )

            # Build result dictionary
            result = {
                "isbn": isbn10,
                "isbn13": isbn13,
                "title": volume_info.get("title", "Unknown Title"),
                "author": result_author,
                "description": volume_info.get("description"),
                "categories": volume_info.get("categories"),
                "page_count": volume_info.get("pageCount"),
                "publisher": volume_info.get("publisher"),
                "publication_year": publication_year,
                "language": volume_info.get("language"),
                "average_rating": volume_info.get("averageRating"),
                "ratings_count": volume_info.get("ratingsCount"),
                "cover_url": cover_url
            }

            logger.info(
                f"Successfully found '{result['title']}' by '{result['author']}' "
                f"(ISBN: {isbn13 or isbn10})"
            )
            return result

        except requests.RequestException as e:
            logger.error(f"Network error searching for '{title}' by '{author}': {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_BACKOFF[attempt]
                logger.info(f"Retrying after network error in {wait_time}s...")
                time.sleep(wait_time)
                continue
            return None
        except (KeyError, ValueError) as e:
            logger.error(
                f"Error parsing Google Books response for '{title}' by '{author}': {e}"
            )
            return None

    return None


def extract_isbn10(volume_info: dict[str, Any]) -> str | None:
    """Extract ISBN-10 from Google Books volume info.

    Args:
        volume_info: The volumeInfo object from Google Books API response

    Returns:
        ISBN-10 string or None if not found
    """
    industry_identifiers = volume_info.get("industryIdentifiers", [])

    for identifier in industry_identifiers:
        if identifier.get("type") == "ISBN_10":
            return identifier.get("identifier")

    return None


def extract_isbn13(volume_info: dict[str, Any]) -> str | None:
    """Extract ISBN-13 from Google Books volume info.

    Args:
        volume_info: The volumeInfo object from Google Books API response

    Returns:
        ISBN-13 string or None if not found
    """
    industry_identifiers = volume_info.get("industryIdentifiers", [])

    for identifier in industry_identifiers:
        if identifier.get("type") == "ISBN_13":
            return identifier.get("identifier")

    return None


def extract_year(published_date: str | None) -> int | None:
    """Extract year from Google Books published date string.

    Google Books returns dates in various formats:
    - "2024"
    - "2024-01"
    - "2024-01-15"

    Args:
        published_date: Date string from Google Books API

    Returns:
        Year as integer or None if invalid/missing
    """
    if not published_date:
        return None

    try:
        # Split by "-" and take the first part (year)
        year_str = published_date.split("-")[0]
        year = int(year_str)

        # Validate reasonable year range (1000-2100)
        if 1000 <= year <= 2100:
            return year
        else:
            logger.warning(f"Invalid year extracted from date '{published_date}': {year}")
            return None

    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse year from date '{published_date}': {e}")
        return None
