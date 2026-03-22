"""Chat API route with SSE streaming."""

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from agents.orchestrator import get_orchestrator

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request body."""

    message: str = Field(description="User's question about video content")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID for multi-turn (not yet implemented)",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    vector_weight: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Weight for vector search (0-1, rest goes to FTS)",
    )


async def chat_event_generator(request: ChatRequest):
    """Generate SSE events from agent orchestrator.

    Args:
        request: Chat request with message and options

    Yields:
        SSE event dicts for sse-starlette
    """
    local_path = os.environ.get("DB_LOCAL_PATH")
    orchestrator = get_orchestrator(local_db_path=local_path)

    async for event in orchestrator.process_chat(
        message=request.message,
        limit=request.limit,
        vector_weight=request.vector_weight,
    ):
        # sse-starlette expects dict with 'event' and 'data' keys
        # data must be JSON string for proper parsing on frontend
        yield {"event": event.event_type, "data": json.dumps(event.data)}


@router.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint with Server-Sent Events streaming.

    Streams events as the agent processes the query:
    - status: Progress updates (rewriting, searching, ranking)
    - chunks: Retrieved transcript chunks
    - answer: Final answer with top relevant chunks
    - error: Error messages
    - done: Processing complete

    Example:
        ```
        event: status
        data: {"stage": "rewriting", "message": "Analyzing your question..."}

        event: answer
        data: {"text": "...", "top_chunks": [...]}

        event: done
        data: {}
        ```
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    return EventSourceResponse(
        chat_event_generator(request),
        media_type="text/event-stream",
    )
