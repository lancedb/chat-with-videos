# chat-with-videos

Chat with your videos using natural language. This application combines semantic search over video transcripts in LanceDB with agent-powered question answering.
The UI also displays the relevant video frames inline with the conversation. This demonstrates Lance's Blob API's ability to load subsets of large blobs without materializing
the full blob into memory.

## Dataset

The dataset used is the "[PostgreSQL vs. the World Seminar Series](https://www.youtube.com/playlist?list=PLSE8ODhjZXjZEVnVTtgDWw6P3wA_gDwj4)" from the CMU database group on YouTube.
The YouTube videos and their transcripts are stored and indexed in LanceDB to be retrieved by the agent layer during question-answering. In the future, more videos on similar topics
can be added to enrich the database.

## Architecture

```
User Query: "explain B+ tree insertion"
                    │
                    ▼
        ┌───────────────────────┐
        │   Query Rewriter      │
        │   (PydanticAI Agent)  │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Hybrid Search       │
        │   0.8 vector + 0.2 FTS│
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Context Ranker      │
        │   (PydanticAI Agent)  │
        └───────────────────────┘
                    │
                    ▼
        Answer + Top 2 video snippets
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────────────┐
│ Chat UI shows │       │ Video players seek to │
│ AI response   │       │ exact timestamps      │
└───────────────┘       └───────────────────────┘
```

For lecture videos (mostly talking heads), the transcript contains the semantic content. Video frames are streamed on-demand using Lance's blob API with HTTP Range requests, so even 100MB+ videos never load fully into memory.

## Frontend Application

The frontend is a Next.js chat interface where users ask questions about their indexed videos. When a user sends a message, the system uses PydanticAI agents to rewrite the query for optimal search, retrieves relevant transcript chunks via hybrid search, and generates a natural language answer with references to specific video moments.

Each answer displays up to two video snippets inline. The HTML5 video players automatically seek to the relevant timestamp and pause at the end of the snippet, allowing users to watch exactly the portion of the video that answers their question.

### Running the Application

Start the backend API server (connects to remote LanceDB Enterprise by default):

```bash
uv run scripts/start_server.py
```

To use a local LanceDB instead:

```bash
uv run scripts/start_server.py --local
```

In a separate terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 to use the chat interface.

## Lazy Video Loading

Video files can be large (100MB+), but the application never loads an entire video into memory. This is achieved through Lance's blob encoding, which enables random access reads directly from S3 or disk.

During ingestion, videos are downloaded to a local `./tmp` directory, their raw bytes are stored in LanceDB as blobs with special metadata (`lance-encoding:blob`), and the local files are cleaned up. At serving time, the backend uses `take_blobs()` to obtain a `BlobFile` handle, which behaves like a standard Python file object with `seek()` and `read()` methods. When the browser requests a video with an HTTP Range header (e.g., bytes 50MB-51MB), the server seeks to that position and reads only the requested bytes. For remote deployments, `take_blobs()` reads directly from the S3-backed Lance dataset via `lance.dataset()` with the configured `LANCE_DATASET_S3_PATH`, which points to LanceDB Enterprise's managed S3 bucket.

Row index mappings and blob sizes are cached in memory (both are immutable after ingest), but `BlobFile` handles are never cached — each range read gets a fresh handle to avoid stale seek/read state with S3-backed blobs. A 114MB video serving 1MB chunks uses roughly 1MB of memory, not 114MB.

## Project Structure

```
chat-with-videos/
├── pyproject.toml              # Dependencies
├── .env.example                # Credentials template
├── config/settings.yaml        # Configuration
├── frontend/                   # Next.js chat UI
│   ├── src/
│   │   ├── app/                # Next.js app router
│   │   ├── components/         # React components
│   │   │   ├── chat/           # Chat UI components
│   │   │   └── video/          # Video player components
│   │   └── hooks/useChat.ts    # SSE streaming hook
│   └── package.json
├── scripts/
│   ├── ingest.py               # Ingest videos
│   ├── search.py               # Search transcripts
│   ├── list_videos.py          # List indexed videos
│   └── start_server.py         # Start the API server
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── main.py             # App entry point
│   │   ├── db_config.py        # Shared DB client (local/remote)
│   │   ├── routes/
│   │   │   ├── chat.py         # SSE chat endpoint
│   │   │   └── video.py        # Video streaming
│   │   └── services/
│   │       └── video_service.py # Lazy blob loading
│   ├── agents/                 # PydanticAI agents
│   │   ├── query_rewriter.py   # Query optimization
│   │   ├── context_ranker.py   # Answer generation
│   │   └── orchestrator.py     # Agent coordination
│   ├── models/
│   │   ├── embeddings.py       # Local embeddings (bge-base-en-v1.5)
│   │   └── schemas.py          # LanceDB schemas
│   ├── pipelines/
│   │   ├── download.py         # yt-dlp downloader
│   │   ├── transcripts.py      # Transcript extraction
│   │   └── ingest.py           # Main ingestion pipeline
│   ├── search/engine.py        # Hybrid search
│   └── storage/
│       ├── lancedb_client.py   # LanceDB operations
│       └── blob_utils.py       # On-demand frame extraction
├── tmp/                        # Temporary video downloads (auto-cleaned)
└── data/                       # Local data (gitignored)
```

## Getting Started

No cloud services needed for local development. The application uses a local embedding model (bge-base-en-v1.5) and local LanceDB storage.

### Prerequisites

ffmpeg is required for merging video and audio streams during download:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

Create a `.env` file with your OpenAI API key (used by the PydanticAI agents):

```bash
cp .env.example .env
# Edit .env and add OPENAI_API_KEY=your-key
```

### Install and Ingest

```bash
cd chat-with-videos

# Install dependencies
uv sync

# Ingest a video (downloads video, extracts transcript, generates embeddings)
uv run scripts/ingest.py --video "https://www.youtube.com/watch?v=VIDEO_ID" --local

# List indexed videos
uv run scripts/list_videos.py --local

# Test search from command line
uv run scripts/search.py "your query here" --local
```

After ingestion, local video files are deleted. The video bytes are stored directly in LanceDB and served via the lazy blob API.

## Deploy on EC2

### Prerequisites

| Service | What to do |
|---------|------------|
| **LanceDB Enterprise** | Get URI + API key from your LanceDB dashboard |
| **AWS credentials** | Get read access to the S3 bucket where LanceDB Enterprise stores its data (for blob API video streaming) |

### Setup

```bash
# Launch t3.large (CPU only - embeddings run locally)

# Clone and install
git clone <your-repo>
cd chat-with-videos
uv sync

# Configure
cp .env.example .env
vim .env
```

### .env Configuration

```bash
# AWS credentials (for accessing LanceDB Enterprise's S3 bucket via Lance blob API)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# LanceDB Enterprise
LANCEDB_URI=db://your-database
LANCEDB_API_KEY=your-api-key
LANCEDB_REGION=us-east-1
LANCEDB_HOST_OVERRIDE=your-host-override  # optional

# Lance dataset S3 path (for blob API — used by take_blobs() for video streaming)
# Points to LanceDB Enterprise's managed S3 bucket where the videos.lance table lives
LANCE_DATASET_S3_PATH=s3://your-lancedb-bucket/your-database/videos.lance
LANCE_DATASET_S3_REGION=us-east-2  # region of the LanceDB Enterprise S3 bucket
```

### Run

```bash
# First-time ingest (reset tables to a clean state)
uv run scripts/ingest.py --reset -V

# Ingest single video
uv run scripts/ingest.py --video "https://www.youtube.com/watch?v=VIDEO_ID" -V

# Ingest playlist
uv run scripts/ingest.py --max-videos 5 -V

# Re-ingest a failed video
uv run scripts/ingest.py --video "https://www.youtube.com/watch?v=VIDEO_ID" --force-update -V

# Search
uv run scripts/search.py "full text search"

# List videos
uv run scripts/list_videos.py
```

## Scripts Reference

```bash
# Start the API server
uv run scripts/start_server.py [OPTIONS]
  --local, -l       Use local LanceDB
  --remote, -r      Use remote LanceDB Enterprise (default)
  --db-path         Local LanceDB path (only used with --local)
  --port, -p        Server port (default: 8000)
  --reload          Enable auto-reload

# Ingest videos
uv run scripts/ingest.py [OPTIONS]
  --video, -v        Single video URL
  --playlist, -p     YouTube playlist URL
  --max-videos, -m   Limit number of videos
  --local, -l        Use local storage
  --force-update, -f Force re-ingest of existing videos (skips duplicate check)
  --reset            Reset tables before ingesting (overwrites all data)
  -V, --verbose      Verbose logging

# Search transcripts
uv run scripts/search.py QUERY [OPTIONS]
  --limit, -n       Number of results (default: 10)
  --type, -t        Search type: vector, fts, hybrid
  --video, -v       Filter by video ID
  --local, -l       Use local LanceDB

# List videos
uv run scripts/list_videos.py [OPTIONS]
  --local, -l       Use local LanceDB

# Test locally
uv run scripts/test_local.py --video-url URL [OPTIONS]
  --test            Test type: transcript, embeddings, full, search
```

## API Endpoints

The FastAPI backend exposes these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | SSE stream for chat (query rewrite → search → answer) |
| `/api/v1/video/{id}/info` | GET | Video metadata (title, duration, thumbnail) |
| `/api/v1/video/{id}/stream` | GET | Video streaming with HTTP Range support (lazy blob loading) |
| `/health` | GET | Health check |

## Cost Breakdown

| Component | Cost |
|-----------|------|
| Text embeddings | $0 (runs locally on CPU) |
| OpenAI API (gpt-4.1-mini) | ~$0.001 per query |
| EC2 t3.large | ~$0.08/hr |
| Local storage | Free |
| LanceDB Enterprise | Contact LanceDB |

For local development, the only cost is OpenAI API usage for the PydanticAI agents.
