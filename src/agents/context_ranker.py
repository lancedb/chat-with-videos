"""Context ranker agent for identifying most relevant chunks and generating answers."""

from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class RankedAnswer(BaseModel):
    """Output of context ranking and answer generation."""

    answer: str = Field(
        description="Natural language answer to the user's question based on the context"
    )
    best_chunk_id: str = Field(
        description="chunk_id of the most relevant transcript chunk"
    )
    second_chunk_id: Optional[str] = Field(
        default=None,
        description="chunk_id of the second most relevant chunk (if applicable)",
    )
    reasoning: str = Field(
        description="Brief explanation of why these chunks were selected"
    )


SYSTEM_PROMPT = """You are an expert at answering questions using video transcript context.

Given a user question and a list of transcript chunks (each with a chunk_id, video title,
timestamp, and text), you must:

1. Answer the question using ONLY the provided context - do not make up information
2. Identify the chunk_id of the BEST chunk that answers the question
3. Identify a second-best chunk_id if another chunk provides useful supplementary info
4. Briefly explain why you selected these chunks

Be concise but accurate. If the context doesn't contain enough information to fully
answer the question, say so and provide what you can from the available context.

Format chunk references using timestamps when helpful (e.g., "As explained at 5:30...")."""


# Lazy initialization to avoid requiring API key at import time
_context_ranker: Optional[Agent] = None


def _get_agent() -> Agent:
    """Get or create the context ranker agent."""
    global _context_ranker
    if _context_ranker is None:
        _context_ranker = Agent(
            "openai:gpt-4.1-mini",
            output_type=RankedAnswer,
            system_prompt=SYSTEM_PROMPT,
        )
    return _context_ranker


def format_chunks_for_llm(chunks: list) -> str:
    """Format search result chunks for LLM context.

    Args:
        chunks: List of SearchResult objects or dicts

    Returns:
        Formatted string with chunk information
    """
    formatted = []
    for i, chunk in enumerate(chunks, 1):
        if hasattr(chunk, "to_dict"):
            c = chunk.to_dict()
        else:
            c = chunk

        formatted.append(
            f"[Chunk {i}]\n"
            f"chunk_id: {c['chunk_id']}\n"
            f"video: {c['video_title']}\n"
            f"timestamp: {c['timestamp_formatted']}\n"
            f"text: {c['text']}\n"
        )
    return "\n".join(formatted)


async def rank_and_answer(user_question: str, chunks: list) -> RankedAnswer:
    """Rank chunks and generate an answer to the user's question.

    Args:
        user_question: The user's original question
        chunks: List of SearchResult objects from the search engine

    Returns:
        RankedAnswer with the answer and top chunk IDs
    """
    context = format_chunks_for_llm(chunks)
    prompt = f"Question: {user_question}\n\nContext:\n{context}"

    agent = _get_agent()
    result = await agent.run(prompt)
    return result.output
