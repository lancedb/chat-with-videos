# Chat with Your Videos - Implementation Plan

## Context

The chat-with-videos project has a working backend for ingesting YouTube videos into LanceDB with transcript chunking and embeddings, but lacks a user-facing interface. This plan adds a chat UI where users can ask natural language questions about video content, with the system retrieving relevant transcript chunks and displaying the corresponding video snippets inline.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│              FRONTEND (Next.js 14 + TailwindCSS)               │
│   Chat UI with pastel coral→dusty-rose gradient theme         │
│   Inline HTML5 video players with timestamp seeking           │
└──────────────────────────┬─────────────────────────────────────┘
                           │ SSE streaming
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                           │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │QueryRewriter │→ │ Hybrid Search │→ │ ContextRanker     │   │
│  │   Agent      │  │ (0.8v/0.2fts) │  │   Agent           │   │
│  └──────────────┘  └───────────────┘  └───────────────────┘   │
│                           │                                    │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ LanceDB (transcripts + videos) │ PyAV frame extraction   │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## Implementation Tasks

### Phase 1: Backend API & Search Updates

**1.1 Add dependencies to `pyproject.toml`:**
- `fastapi>=0.109.0`
- `uvicorn[standard]>=0.27.0`
- `sse-starlette>=2.0.0`
- `pydantic-ai>=0.0.12`
- `anthropic>=0.40.0`
- `httpx>=0.27.0`

**1.2 Update hybrid search with configurable reranker** (`src/search/engine.py`):
```python
from lancedb.rerankers import LinearCombinationReranker

def search(self, query, limit=10, search_type="hybrid",
           vector_weight=0.8, fts_weight=0.2):
    if search_type == "hybrid":
        reranker = LinearCombinationReranker(weight=vector_weight)
        search = (
            table.search(query_type="hybrid")
            .vector(query_embedding)
            .text(query)
            .rerank(reranker)
        )
```

**1.3 Add async search support** (`src/search/engine.py`):
- Add `async def search_async()` method for parallel query execution

**1.4 Create FastAPI application:**
- `src/api/main.py` - App entry, CORS, routes
- `src/api/routes/chat.py` - `POST /api/v1/chat` with SSE streaming
- `src/api/routes/video.py` - `GET /api/v1/video/{id}/info` and `/stream`

### Phase 2: PydanticAI Agents

**2.1 Query Rewriter Agent** (`src/agents/query_rewriter.py`):
```python
class RewrittenQueries(BaseModel):
    primary_query: str
    alternate_queries: list[str]  # 2-3 variants
    key_concepts: list[str]       # Keywords for FTS boost
```
- Rewrites user question for optimal hybrid search
- Outputs multiple query variants for parallel async retrieval

**2.2 Context Ranker Agent** (`src/agents/context_ranker.py`):
```python
class RankedAnswer(BaseModel):
    answer: str           # Natural language response
    best_chunk_id: str    # Most relevant chunk
    second_chunk_id: str | None
    reasoning: str
```
- Receives top-5 retrieved chunks
- Identifies the 2 most relevant chunks for video display
- Generates answer using only retrieved context

**2.3 Orchestrator** (`src/agents/orchestrator.py`):
- Coordinates agent flow with SSE status updates
- Flow: rewrite → parallel search → rank → extract video info

### Phase 3: Video Serving

**3.1 Video service** (`src/api/services/video_service.py`):
- Uses Lance blob API (`take_blobs()`) for all modes (local and Enterprise)
- Caches row index mappings and blob sizes (immutable after ingest) but NOT `BlobFile` handles
- Each range read gets a fresh `BlobFile` handle to avoid stale seek/read state with S3-backed blobs
- Supports `seek()` + `read()` for HTTP Range requests — only reads requested bytes

**3.2 Video streaming endpoint** (`src/api/routes/video.py`):
- `GET /api/v1/video/{id}/stream` with HTTP 206 Range support
- Streams in 1MB chunks for non-range requests
- For Enterprise: `take_blobs()` reads from S3 via `lance.dataset()` with `LANCE_DATASET_S3_PATH`

### Phase 4: Next.js Frontend

**4.1 Initialize project** (`frontend/`):
```bash
npx create-next-app@latest frontend --typescript --tailwind --app
```

**4.2 Color scheme** (`frontend/app/globals.css`):
```css
:root {
  --coral: #F4A693;
  --dusty-rose: #C4A5A0;
  --bg-light: #FDF8F6;
}
```

**4.3 Components:**
| Component | Purpose |
|-----------|---------|
| `ChatContainer.tsx` | Main layout with gradient header |
| `MessageList.tsx` | Scrollable chat messages |
| `MessageBubble.tsx` | User/AI message styling |
| `ChatInput.tsx` | Text input + send button |
| `VideoSnippetCard.tsx` | Video player card with metadata (constructs stream URL directly from chunk data) |
| `VideoPlayer.tsx` | HTML5 player with auto-seek to timestamps |
| `LoadingSpinner.tsx` | Animated progress during agent work |
| `ProgressSteps.tsx` | Shows "Rewriting..." → "Searching..." → "Ranking..." |

**4.4 SSE hook** (`frontend/hooks/useChat.ts`):
- Connect to `/api/v1/chat` SSE endpoint
- Parse events: `status`, `chunks`, `answer`, `done`
- Manage loading states per stage

**4.5 Video player logic** (`frontend/components/video/VideoPlayer.tsx`):
```tsx
useEffect(() => {
  video.currentTime = startSeconds;
  video.addEventListener('timeupdate', () => {
    if (video.currentTime >= endSeconds) video.pause();
  });
}, [startSeconds, endSeconds]);
```

---

## Files to Create

```
src/
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── db_config.py          # Shared DB client singleton (local vs remote)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   └── video.py
│   └── services/
│       ├── __init__.py
│       └── video_service.py
├── agents/
│   ├── __init__.py
│   ├── query_rewriter.py
│   ├── context_ranker.py
│   └── orchestrator.py

frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── globals.css
│   └── api/chat/route.ts  (optional proxy)
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageBubble.tsx
│   │   └── ChatInput.tsx
│   └── video/
│       ├── VideoSnippetCard.tsx
│       └── VideoPlayer.tsx
├── hooks/
│   └── useChat.ts
├── lib/
│   └── types.ts
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

## Files to Modify

| File | Change |
|------|--------|
| `src/search/engine.py` | Add `LinearCombinationReranker`, async search, chunk_id to SearchResult |
| `pyproject.toml` | Add FastAPI, pydantic-ai, sse-starlette deps |
| `scripts/start_server.py` | CLI entry point for `uv run scripts/start_server.py [--local]` |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | SSE stream: query → rewrite → search → rank → answer |
| `/api/v1/video/{id}/info` | GET | Video metadata (title, duration, youtube_url) |
| `/api/v1/video/{id}/stream` | GET | Video streaming with HTTP Range support (lazy blob loading) |
| `/health` | GET | Health check |

### SSE Events for `/api/v1/chat`

```
event: status
data: {"stage": "rewriting", "message": "Analyzing your question..."}

event: status
data: {"stage": "searching", "message": "Searching transcripts..."}

event: chunks
data: {"chunks": [...]}

event: status
data: {"stage": "ranking", "message": "Finding best matches..."}

event: answer
data: {"text": "...", "top_chunks": [{chunk_id, video_id, start_seconds, end_seconds, text}, ...]}

event: done
data: {}
```

---

## Verification Plan

1. **Search engine tests:**
   - Verify hybrid search returns expected results
   - Test reranker weight configuration (0.8/0.2)
   - Confirm FTS index is working

2. **Agent tests:**
   - Test query rewriter with sample questions
   - Test context ranker with mock chunks
   - Verify orchestrator SSE streaming

3. **API tests:**
   - `curl` POST to `/api/v1/chat` and verify SSE stream
   - Test video info/stream endpoints

4. **E2E tests:**
   - Ask question in UI, verify answer appears
   - Verify video players show and seek to correct timestamps
   - Test loading states display correctly

5. **Manual testing:**
   - Run FastAPI: `uvicorn src.api.main:app --reload`
   - Run Next.js: `cd frontend && npm run dev`
   - Test full flow with real questions against indexed videos
