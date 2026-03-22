# Video Search Backend for CMU Database Course

## Context

Build a "chat with your video" search backend for the CMU Database Course YouTube playlist. The system extracts transcripts, generates text embeddings, and stores everything in LanceDB for semantic search. Video frames are extracted on-demand at query time using Lance's blob API.

**Playlist**: https://www.youtube.com/playlist?list=PLSE8ODhjZXjZEVnVTtgDWw6P3wA_gDwj4

---

## Architecture

```
User Query: "explain B+ tree insertion"
                    │
                    ▼
        ┌───────────────────────┐
        │  Embed query (local)  │
        │  bge-base-en-v1.5     │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Search transcripts   │
        │  (LanceDB vector)     │
        └───────────────────────┘
                    │
                    ▼
        Top-5 transcript chunks with timestamps
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────────────┐
│ Agent reasons │       │ Frontend: extract     │
│ over text     │       │ frames at timestamps  │
│ chunks        │       │ via Lance Blob API    │
└───────────────┘       └───────────────────────┘
```

**Key insight**: For lecture videos (mostly talking heads), the transcript contains the semantic content. Video frames are extracted on-demand at query time - no frame embeddings needed.

---

## Storage Schema

```python
# videos table - metadata + blob for video
class VideoRecord(LanceModel):
    video_id: str
    title: str
    duration_seconds: float
    youtube_url: str
    video_blob: bytes         # Blob-encoded video for lazy loading via take_blobs()

# transcripts table - text embeddings for search
class TranscriptChunk(LanceModel):
    chunk_id: str             # {video_id}_{start_ms}
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    text: str                 # For FTS
    vector: Vector(768)       # bge-base-en-v1.5 embedding
```

---

## Components

### 1. Embedding Model (Local, CPU)

- **Model**: `BAAI/bge-base-en-v1.5`
- **Dimensions**: 768
- **Runs locally** on EC2 CPU - no API calls needed
- **Library**: `sentence-transformers`

### 2. Transcript Chunking

- **Chunk duration**: 30 seconds
- **Why 30s**: Balances context (enough to understand a concept) with granularity (specific enough for search)

### 3. Video Streaming (Lazy Blob Loading)

Using Lance's blob API (reads directly from LanceDB Enterprise's S3 bucket):
```python
# At serving time, stream video bytes on demand via HTTP Range requests
ds = lance.dataset("s3://lancedb-bucket/database/videos.lance")
blobs = ds.take_blobs("video_blob", indices=[row_idx])

blob_file = blobs[0]
blob_file.seek(start)        # Seek to requested byte offset
data = blob_file.read(length) # Read only the requested range from S3
```

Row index mappings and blob sizes are cached (immutable after ingest), but `BlobFile` handles are created fresh per read to avoid stale seek/read state with S3-backed blobs.

---

## What We Eliminated

| Before | After |
|--------|-------|
| Frame extraction at ingest time | On-demand at query time |
| 20,000+ frame embeddings | 0 frame embeddings |
| HF Inference Endpoint ($50-100) | Local CPU embeddings ($0) |
| frames table | Not needed |
| Image embedding model | Not needed |

**Cost reduction**: ~$100 → ~$0 for embeddings

---

## Dependencies

```toml
dependencies = [
    "lancedb>=0.15.0",
    "pylance>=0.15.0",           # For blob API
    "boto3>=1.34.0",
    "yt-dlp>=2024.1.0",
    "av>=12.0.0",                # On-demand frame extraction
    "pillow>=10.0.0",
    "sentence-transformers>=2.5.0",  # Local embeddings
    "youtube-transcript-api>=0.6.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0.0",
    "typer[all]>=0.9.0",
]
```

---

## Implementation Steps

### Phase 1: Project Setup
1. ✅ Create `pyproject.toml` with dependencies
2. ✅ Create `config/settings.yaml`
3. ✅ Implement `config.py`

### Phase 2: Storage Layer
4. ✅ Implement `storage/lancedb_client.py`
5. ✅ Implement `storage/blob_utils.py` (on-demand frame extraction)

### Phase 3: Pipelines
7. ✅ Implement `pipelines/download.py`
8. ✅ Implement `pipelines/transcripts.py`
9. ✅ Implement `models/embeddings.py` (local sentence-transformers)
10. ✅ Implement `pipelines/ingest.py`

### Phase 4: Search & CLI
11. ✅ Implement `search/engine.py`
12. ✅ Implement `cli/main.py`

---

## Verification

1. **Local test**:
   ```bash
   uv run scripts/test_local.py --video-url "https://youtube.com/watch?v=..." --test full
   ```

2. **Search test**:
   ```bash
   uv run scripts/search.py "B+ tree" --local
   ```

3. **Frame extraction test**:
   ```bash
   uv run scripts/extract_frames.py VIDEO_ID "10.5,30.0,60.0"
   ```

---

## Future: Agent Integration

The search engine returns structured results for agent consumption:

```python
results = engine.search("explain B+ tree insertion", limit=5)
# Returns: [SearchResult(video_id, start_seconds, end_seconds, text, score), ...]

# Agent uses text for reasoning
# Frontend extracts frames at timestamps for display
```
