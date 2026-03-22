"""Search engine for video transcripts using LanceDB."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from lancedb.rerankers import LinearCombinationReranker

from models.embeddings import LocalEmbedder, create_embedder
from storage.lancedb_client import VideoSearchDB, create_db_client

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from transcript search."""

    score: float
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    timestamp_formatted: str
    text: str
    chunk_id: str = field(default="")

    def __post_init__(self):
        """Generate chunk_id if not provided."""
        if not self.chunk_id:
            self.chunk_id = f"{self.video_id}_{int(self.start_seconds * 1000)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "video_id": self.video_id,
            "video_title": self.video_title,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "timestamp_formatted": self.timestamp_formatted,
            "text": self.text,
        }


class VideoSearchEngine:
    """Search engine for video transcripts using LanceDB."""

    def __init__(
        self,
        db: Optional[VideoSearchDB] = None,
        embedder: Optional[LocalEmbedder] = None,
        local_db_path: Optional[str] = None,
    ):
        """Initialize search engine.

        Args:
            db: LanceDB client
            embedder: Embedding model for query encoding
            local_db_path: If provided, use local LanceDB at this path
        """
        if local_db_path:
            self.db = create_db_client(local_path=local_db_path)
        else:
            self.db = db or create_db_client()

        self.embedder = embedder or create_embedder()

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert seconds to HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def search(
        self,
        query: str,
        limit: int = 10,
        search_type: Literal["vector", "fts", "hybrid"] = "vector",
        video_id: Optional[str] = None,
        vector_weight: float = 0.8,
    ) -> List[SearchResult]:
        """Search transcripts using vector, FTS, or hybrid search.

        Args:
            query: Search query
            limit: Maximum number of results
            search_type: Type of search (vector, fts, hybrid)
            video_id: Filter by video ID
            vector_weight: Weight for vector search in hybrid mode (0-1, default 0.8)
                          FTS weight will be (1 - vector_weight)

        Returns:
            List of search results with timestamps and text
        """
        table = self.db.db.open_table("transcripts")

        if search_type == "fts":
            # Full-text search only
            search = table.search(query, query_type="fts")
        elif search_type == "hybrid":
            # Hybrid search (vector + FTS) with configurable reranker
            query_embedding = self.embedder.embed_query(query)
            try:
                reranker = LinearCombinationReranker(weight=vector_weight)
                # Use explicit vector and text for hybrid search
                search = (
                    table.search(query_type="hybrid")
                    .vector(query_embedding)
                    .text(query)
                    .rerank(reranker)
                )
            except Exception as e:
                # Fallback to vector if hybrid not supported
                logger.warning(f"Hybrid search not available ({e}), falling back to vector")
                search = table.search(query_embedding).metric("cosine")
        else:
            # Vector search (default)
            query_embedding = self.embedder.embed_query(query)
            search = table.search(query_embedding).metric("cosine")

        if video_id:
            search = search.where(f"video_id = '{video_id}'")

        results = search.limit(limit).to_list()

        return [
            SearchResult(
                score=r.get("_relevance_score", 1 - r.get("_distance", 0)),
                video_id=r["video_id"],
                video_title=r["video_title"],
                start_seconds=r["start_seconds"],
                end_seconds=r["end_seconds"],
                timestamp_formatted=self._format_timestamp(r["start_seconds"]),
                text=r["text"],
                chunk_id=r.get("chunk_id", ""),
            )
            for r in results
        ]

    async def search_async(
        self,
        query: str,
        limit: int = 10,
        search_type: Literal["vector", "fts", "hybrid"] = "hybrid",
        video_id: Optional[str] = None,
        vector_weight: float = 0.8,
    ) -> List[SearchResult]:
        """Async wrapper for search to enable parallel execution.

        Args:
            query: Search query
            limit: Maximum number of results
            search_type: Type of search (vector, fts, hybrid)
            video_id: Filter by video ID
            vector_weight: Weight for vector search in hybrid mode

        Returns:
            List of search results with timestamps and text
        """
        # Run sync search in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.search(
                query=query,
                limit=limit,
                search_type=search_type,
                video_id=video_id,
                vector_weight=vector_weight,
            ),
        )

    def search_with_context(
        self,
        query: str,
        limit: int = 5,
        context_chunks: int = 1,
        video_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search and return results with surrounding context.

        Args:
            query: Search query
            limit: Maximum number of results
            context_chunks: Number of chunks before/after to include
            video_id: Filter by video ID

        Returns:
            List of results with context
        """
        results = self.search(query, limit=limit, video_id=video_id)

        enriched_results = []
        for result in results:
            # Get surrounding chunks
            table = self.db.db.open_table("transcripts")

            # Get chunks in time window around this result
            window_start = max(0, result.start_seconds - context_chunks * 30)
            window_end = result.end_seconds + context_chunks * 30

            context_results = (
                table.search()
                .where(
                    f"video_id = '{result.video_id}' AND "
                    f"start_seconds >= {window_start} AND "
                    f"end_seconds <= {window_end}"
                )
                .limit(context_chunks * 2 + 1)
                .to_list()
            )

            # Sort by timestamp and combine text
            context_results.sort(key=lambda x: x["start_seconds"])
            context_text = " ".join(c["text"] for c in context_results)

            enriched_results.append({
                "result": result.to_dict(),
                "context_text": context_text,
                "context_start": window_start,
                "context_end": window_end,
            })

        return enriched_results

    def get_video_transcript(
        self,
        video_id: str,
        start_seconds: Optional[float] = None,
        end_seconds: Optional[float] = None,
    ) -> List[SearchResult]:
        """Get all transcript chunks for a video, optionally filtered by time range.

        Args:
            video_id: Video ID
            start_seconds: Start of time range (optional)
            end_seconds: End of time range (optional)

        Returns:
            List of transcript chunks sorted by timestamp
        """
        table = self.db.db.open_table("transcripts")

        where_clause = f"video_id = '{video_id}'"
        if start_seconds is not None:
            where_clause += f" AND start_seconds >= {start_seconds}"
        if end_seconds is not None:
            where_clause += f" AND end_seconds <= {end_seconds}"

        results = table.search().where(where_clause).limit(10000).to_list()

        # Sort by timestamp
        results.sort(key=lambda x: x["start_seconds"])

        return [
            SearchResult(
                score=1.0,
                video_id=r["video_id"],
                video_title=r["video_title"],
                start_seconds=r["start_seconds"],
                end_seconds=r["end_seconds"],
                timestamp_formatted=self._format_timestamp(r["start_seconds"]),
                text=r["text"],
            )
            for r in results
        ]
