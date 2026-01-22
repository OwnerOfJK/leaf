"""Question generation service for conversational book recommendations."""

import logging
from typing import Optional

from langfuse import get_client, observe
from sqlalchemy.orm import Session

from app.constants import LLM_MODEL
from app.core.embeddings import openai_client
from app.models.database import Book

logger = logging.getLogger(__name__)
langfuse = get_client()

# Predefined fallback questions (used if LLM generation fails)
FALLBACK_QUESTIONS = {
    1: "What themes or subjects are you most drawn to in books?",
    2: "How do you prefer books to make you feel - challenged and thought-provoking, or comforted and entertained?",
    3: "Are there any specific writing styles, pacing, or narrative structures you particularly enjoy or want to avoid?",
}


@observe(as_type="generation")
def generate_question(
    question_number: int,
    initial_query: str,
    previous_questions: dict[int, str],
    previous_answers: dict[str, Optional[str]],
) -> str:
    """Generate a contextually relevant follow-up question using LLM.

    Uses context including initial query and all previous Q&As to generate
    intelligent follow-up questions like a librarian helping someone find
    their next book.

    Note: Does NOT use user's book library to allow questions to be generated
    while CSV is still processing in the background.

    Args:
        question_number: Which question to generate (1, 2, or 3)
        initial_query: User's initial book preference query
        previous_questions: Dict of previously generated questions {number: question}
        previous_answers: Dict of user's previous answers {question_1: answer, ...}

    Returns:
        Generated question text

    Raises:
        Exception: If LLM generation fails (caller should catch and use fallback)
    """
    try:
        # Build conversation history
        conversation_history = _build_conversation_history(
            previous_questions, previous_answers
        )

        # Build system prompt
        system_prompt = _build_system_prompt(question_number)

        # Build user prompt with context
        user_prompt = _build_user_prompt(
            question_number, initial_query, conversation_history
        )

        logger.info(f"Generating question {question_number} using {LLM_MODEL}")

        # Call OpenAI with Langfuse tracking
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=150,
        )

        generated_question = response.choices[0].message.content.strip()

        logger.info(
            f"Successfully generated question {question_number}: {generated_question[:100]}..."
        )

        return generated_question

    except Exception as e:
        logger.error(f"Failed to generate question {question_number}: {e}")
        raise


def _build_conversation_history(
    previous_questions: dict[int, str], previous_answers: dict[str, Optional[str]]
) -> str:
    """Build formatted conversation history from Q&As.

    Args:
        previous_questions: Dict of previously asked questions
        previous_answers: Dict of user's answers

    Returns:
        Formatted conversation history
    """
    if not previous_questions:
        return "This is the first question."

    history_parts = []
    for q_num in sorted(previous_questions.keys()):
        question = previous_questions[q_num]
        answer_key = f"question_{q_num}"
        answer = previous_answers.get(answer_key)

        if answer:
            history_parts.append(f"Q{q_num}: {question}\nA{q_num}: {answer}")
        else:
            history_parts.append(f"Q{q_num}: {question}\nA{q_num}: [skipped]")

    return "\n\n".join(history_parts)


def _build_system_prompt(question_number: int) -> str:
    """Build system prompt for the LLM.

    Args:
        question_number: Current question number

    Returns:
        System prompt string
    """
    return f"""You are a friendly, knowledgeable librarian helping someone find their next perfect book to read.

Your goal is to ask thoughtful, conversational questions that help you understand what book would delight this person. You're having a warm conversation, not conducting an interview.

Guidelines for question {question_number}:
- Ask ONE clear, open-ended question
- Be conversational and warm, like a helpful librarian
- Build naturally on the conversation so far
- Focus on understanding their reading preferences, mood, and what they're looking for
- Keep questions concise (1-2 sentences max)
- Avoid technical jargon - use plain, friendly language

Remember: You're helping them discover their next favorite book, not interrogating them. Make it feel like a pleasant conversation."""


def _build_user_prompt(
    question_number: int, initial_query: str, conversation_history: str
) -> str:
    """Build user prompt with full context.

    Args:
        question_number: Current question number
        initial_query: User's initial query
        conversation_history: Formatted previous Q&As

    Returns:
        User prompt string
    """
    return f"""Initial request: "{initial_query}"

{conversation_history}

Generate question {question_number} to help understand what book would be perfect for this person.

Return ONLY the question text, nothing else."""
