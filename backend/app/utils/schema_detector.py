"""LLM-based CSV schema detection for flexible book imports."""

import json
import logging
from typing import Any

from langfuse import observe

from app.constants import LLM_MODEL
from app.core.embeddings import openai_client

logger = logging.getLogger(__name__)

# Fields we want to detect in the CSV
DETECTABLE_FIELDS = {
    "title": "Book title",
    "author": "Author name(s)",
    "isbn": "ISBN-10 (10 digit identifier)",
    "isbn13": "ISBN-13 (13 digit identifier)",
    "rating": "User's rating/score for the book",
    "shelf": "Reading status (read, to-read, currently-reading, etc.)",
}


@observe(as_type="generation")
def detect_csv_schema(
    headers: list[str],
    sample_rows: list[list[Any]],
) -> dict[str, str | None]:
    """Detect which CSV columns map to which book fields using LLM.

    Analyzes CSV headers and sample data to intelligently map columns
    to standardized book fields.

    Args:
        headers: List of column header names from the CSV
        sample_rows: List of sample rows (each row is a list of values)

    Returns:
        Dictionary mapping our field names to CSV column names:
        {
            "title": "Book Title",      # or None if not detected
            "author": "Writer",         # or None if not detected
            "isbn": "ISBN",             # or None if not detected
            "isbn13": "ISBN13",         # or None if not detected
            "rating": "My Rating",      # or None if not detected
            "shelf": "Shelf",           # or None if not detected
        }

    Raises:
        ValueError: If schema detection fails or required fields cannot be identified
    """
    # Build sample data preview for the LLM
    sample_preview = _build_sample_preview(headers, sample_rows)

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(headers, sample_preview)

    logger.info(f"Detecting CSV schema using {LLM_MODEL}")
    logger.debug(f"Headers: {headers}")

    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,  # Deterministic for consistent mapping
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content.strip()
        logger.debug(f"LLM response: {result_text}")

        # Parse JSON response
        detected = json.loads(result_text)

        # Validate the response structure
        schema_mapping = _validate_and_extract_mapping(detected, headers)

        logger.info(f"Detected schema mapping: {schema_mapping}")

        # Check if we have minimum required fields (title OR isbn/isbn13)
        has_title = schema_mapping.get("title") is not None
        has_isbn = schema_mapping.get("isbn") is not None or schema_mapping.get("isbn13") is not None

        if not has_title and not has_isbn:
            raise ValueError(
                "Could not detect required fields. CSV must have at least a title column "
                "or ISBN column to identify books."
            )

        return schema_mapping

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        raise ValueError(f"Schema detection failed: invalid response format")
    except Exception as e:
        logger.error(f"Schema detection failed: {e}")
        raise ValueError(f"Schema detection failed: {e}")


def _build_sample_preview(headers: list[str], sample_rows: list[list[Any]]) -> str:
    """Build a formatted preview of the CSV data for the LLM.

    Args:
        headers: Column headers
        sample_rows: Sample data rows

    Returns:
        Formatted string showing headers and sample data
    """
    lines = []

    # Header row
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    # Sample rows (up to 5)
    for row in sample_rows[:5]:
        # Truncate long values and convert to string
        formatted_values = []
        for val in row:
            str_val = str(val) if val is not None else ""
            if len(str_val) > 50:
                str_val = str_val[:47] + "..."
            formatted_values.append(str_val)
        lines.append("| " + " | ".join(formatted_values) + " |")

    return "\n".join(lines)


def _build_system_prompt() -> str:
    """Build the system prompt for schema detection."""
    return """You are a data analyst expert at identifying CSV column mappings for book data.

Your task is to analyze CSV headers and sample data to determine which columns contain which book information.

You must identify these fields if present:
- title: The book's title
- author: The author name(s)
- isbn: ISBN-10 (10 digit book identifier, may have format like ="0123456789")
- isbn13: ISBN-13 (13 digit book identifier, may have format like ="9780123456789")
- rating: User's personal rating or score for the book (numeric)
- shelf: Reading status (e.g., "read", "to-read", "currently-reading", "want to read")

Important:
- Column names may vary (e.g., "Book Title", "Title", "Name" could all be the title)
- Some fields may not be present in the CSV - set those to null
- ISBN columns often have Excel formula format like ="0123456789" - still identify them
- Rating might be called "My Rating", "Score", "Stars", etc.
- Shelf/status might be called "Shelf", "Exclusive Shelf", "Status", "Read Status", etc.

Respond with a JSON object mapping field names to the exact CSV column names (or null if not found)."""


def _build_user_prompt(headers: list[str], sample_preview: str) -> str:
    """Build the user prompt with CSV data."""
    return f"""Analyze this CSV and identify which columns contain book information.

CSV Headers: {headers}

Sample Data:
{sample_preview}

Return a JSON object with this exact structure:
{{
    "title": "<exact column name or null>",
    "author": "<exact column name or null>",
    "isbn": "<exact column name or null>",
    "isbn13": "<exact column name or null>",
    "rating": "<exact column name or null>",
    "shelf": "<exact column name or null>"
}}

Use the EXACT column names from the headers list. Set to null if a field is not present."""


def _validate_and_extract_mapping(
    detected: dict[str, Any],
    headers: list[str]
) -> dict[str, str | None]:
    """Validate LLM response and extract clean mapping.

    Args:
        detected: Raw LLM response dictionary
        headers: Original CSV headers for validation

    Returns:
        Validated schema mapping
    """
    schema_mapping = {}

    for field in DETECTABLE_FIELDS:
        column_name = detected.get(field)

        if column_name is None or column_name == "null":
            schema_mapping[field] = None
        elif column_name in headers:
            schema_mapping[field] = column_name
        else:
            # LLM might have returned a column name not in headers (hallucination)
            logger.warning(
                f"LLM suggested column '{column_name}' for {field}, "
                f"but it's not in headers. Setting to None."
            )
            schema_mapping[field] = None

    return schema_mapping
