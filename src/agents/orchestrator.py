"""Agent orchestrator for coordinating query rewriting, search, and ranking."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from agents.context_ranker import RankedAnswer, rank_and_answer
from agents.query_rewriter import RewrittenQueries, rewrite_query
from search.engine import SearchResult, VideoSearchEngine

logger = logging.getLogger(__name__)


@dataclass
class ChatEvent:
    """Event emitted during chat processing."""

    event_type: str  # "status", "chunks", "answer", "error", "done"
    data: dict

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        import json

        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"


class AgentOrchestrator:
    """Orchestrates the query → rewrite → search → rank → answer flow."""

    def __init__(
        self,
        search_engine: Optional[VideoSearchEngine] = None,
        local_db_path: Optional[str] = None,
    ):
        """Initialize orchestrator.

        Args:
            search_engine: Optional pre-configured search engine
            local_db_path: Path to local LanceDB (if None, uses remote via env vars)
        """
        self.search_engine = search_engine or VideoSearchEngine(local_db_path=local_db_path)

    async def process_chat(
        self,
        message: str,
        limit: int = 5,
        vector_weight: float = 0.8,
    ) -> AsyncIterator[ChatEvent]:
        """Process a chat message through the full agent pipeline.

        Args:
            message: User's question
            limit: Number of chunks to retrieve per query
            vector_weight: Weight for vector vs FTS in hybrid search

        Yields:
            ChatEvent objects for SSE streaming
        """
        try:
            # Stage 1: Rewrite query
            yield ChatEvent(
                event_type="status",
                data={"stage": "rewriting", "message": "Analyzing your question..."},
            )

            rewritten = await rewrite_query(message)
            logger.info(f"Rewritten query: {rewritten.primary_query}")

            # Stage 2: Search with multiple query variants in parallel
            yield ChatEvent(
                event_type="status",
                data={"stage": "searching", "message": "Searching transcripts..."},
            )

            chunks = await self._search_with_rewrites(rewritten, limit, vector_weight)

            if not chunks:
                yield ChatEvent(
                    event_type="error",
                    data={"message": "No relevant content found for your question."},
                )
                yield ChatEvent(event_type="done", data={})
                return

            # Emit found chunks
            yield ChatEvent(
                event_type="chunks",
                data={"chunks": [c.to_dict() for c in chunks]},
            )

            # Stage 3: Rank and generate answer
            yield ChatEvent(
                event_type="status",
                data={"stage": "ranking", "message": "Finding best matches..."},
            )

            ranked = await rank_and_answer(message, chunks)

            # Get top 2 chunks by ID
            top_chunks = self._get_chunks_by_ids(
                chunks, [ranked.best_chunk_id, ranked.second_chunk_id]
            )

            # Stage 4: Return final answer
            yield ChatEvent(
                event_type="answer",
                data={
                    "text": ranked.answer,
                    "reasoning": ranked.reasoning,
                    "top_chunks": [c.to_dict() for c in top_chunks],
                },
            )

            yield ChatEvent(event_type="done", data={})

        except Exception as e:
            logger.exception(f"Error processing chat: {e}")
            yield ChatEvent(
                event_type="error",
                data={"message": f"An error occurred: {str(e)}"},
            )
            yield ChatEvent(event_type="done", data={})

    async def _search_with_rewrites(
        self,
        queries: RewrittenQueries,
        limit: int,
        vector_weight: float,
    ) -> list[SearchResult]:
        """Execute hybrid search with multiple query variants.

        Args:
            queries: Rewritten query variants
            limit: Results per query
            vector_weight: Weight for vector search

        Returns:
            Deduplicated, re-ranked list of top results
        """
        # Run searches in parallel
        tasks = [
            self.search_engine.search_async(
                queries.primary_query,
                limit=limit,
                search_type="hybrid",
                vector_weight=vector_weight,
            )
        ]

        # Add alternate queries (limit to 2)
        for alt_query in queries.alternate_queries[:2]:
            tasks.append(
                self.search_engine.search_async(
                    alt_query,
                    limit=3,  # Fewer results for alternates
                    search_type="hybrid",
                    vector_weight=vector_weight,
                )
            )

        results = await asyncio.gather(*tasks)

        # Deduplicate by chunk_id, keeping highest score
        seen_chunks: dict[str, SearchResult] = {}
        for result_list in results:
            for r in result_list:
                if r.chunk_id not in seen_chunks or r.score > seen_chunks[r.chunk_id].score:
                    seen_chunks[r.chunk_id] = r

        # Return top results sorted by score
        sorted_results = sorted(seen_chunks.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:limit]

    def _get_chunks_by_ids(
        self,
        chunks: list[SearchResult],
        chunk_ids: list[Optional[str]],
    ) -> list[SearchResult]:
        """Get chunks matching the given IDs.

        Args:
            chunks: List of search results
            chunk_ids: List of chunk IDs to find

        Returns:
            Matching chunks in order
        """
        chunk_map = {c.chunk_id: c for c in chunks}
        result = []
        for cid in chunk_ids:
            if cid and cid in chunk_map:
                result.append(chunk_map[cid])
        return result


# Singleton instance for reuse
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator(local_db_path: Optional[str] = None) -> AgentOrchestrator:
    """Get or create the agent orchestrator singleton.

    Args:
        local_db_path: Path to local LanceDB (if None, uses remote via env vars)

    Returns:
        AgentOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(local_db_path=local_db_path)
    return _orchestrator
