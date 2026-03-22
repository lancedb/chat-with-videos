"""Query rewriter agent for optimizing search queries."""

from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class RewrittenQueries(BaseModel):
    """Output of query rewriting."""

    primary_query: str = Field(
        description="Main search query optimized for semantic/vector search"
    )
    alternate_queries: list[str] = Field(
        description="2-3 alternate phrasings to improve recall",
        min_length=1,
        max_length=3,
    )
    key_concepts: list[str] = Field(
        description="Key concepts/keywords for full-text search boost",
        min_length=1,
        max_length=5,
    )


SYSTEM_PROMPT = """You are a query optimizer for video transcript search.
Given a user question about video content (typically educational/lecture videos),
rewrite it into optimized search queries.

Your output should include:
1. A primary search query optimized for semantic/vector search - this should capture
   the conceptual meaning of what the user is looking for
2. 2-3 alternate phrasings to improve recall - different ways to express the same concept
3. Key concepts/keywords for full-text search - specific terms that should appear in results

Focus on extracting the core information need and reformulating it for search.
Keep queries concise but meaningful."""


# Lazy initialization to avoid requiring API key at import time
_query_rewriter: Optional[Agent] = None


def _get_agent() -> Agent:
    """Get or create the query rewriter agent."""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = Agent(
            "openai:gpt-4.1-mini",
            output_type=RewrittenQueries,
            system_prompt=SYSTEM_PROMPT,
        )
    return _query_rewriter


async def rewrite_query(user_message: str) -> RewrittenQueries:
    """Rewrite a user message into optimized search queries.

    Args:
        user_message: The user's natural language question

    Returns:
        RewrittenQueries with primary query, alternates, and key concepts
    """
    agent = _get_agent()
    result = await agent.run(user_message)
    return result.output
