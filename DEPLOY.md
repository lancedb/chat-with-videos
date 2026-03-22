# Deployment Guide

This document shows a basic (non-prod) guide to deploy the frontend to share with others.

## Architecture

```
Vercel (Next.js frontend, password-protected)
        ↓ fetch() calls
EC2 (FastAPI backend, exposed via ngrok HTTPS tunnel)
        ↓ take_blobs()
S3 (LanceDB Enterprise managed bucket)
```

## Prerequisites

| Service | What to do |
|---------|------------|
| **Vercel** | Account for frontend deployment + password protection |
| **EC2** | t3.large instance with ports 22 (SSH) open |
| **ngrok** | Free account at ngrok.com, claim a static subdomain |
| **LanceDB Enterprise** | URI + API key from your LanceDB dashboard |
| **AWS credentials** | Read access to LanceDB Enterprise's S3 bucket (for blob API video streaming) |
| **OpenAI API key** | For PydanticAI agents (gpt-4.1-mini) |

## EC2 Setup

### 1. Install dependencies

```bash
# Clone and install
git clone <your-repo>
cd chat-with-videos
uv sync

# Install ngrok
# https://ngrok.com/download
```

### 2. Configure environment

```bash
cp .env.example .env
vim .env
```

Required `.env` values:

```bash
# OpenAI (for PydanticAI agents)
OPENAI_API_KEY=your-key

# AWS credentials (for accessing LanceDB Enterprise's S3 bucket)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# LanceDB Enterprise
LANCEDB_URI=db://your-database
LANCEDB_API_KEY=your-api-key
LANCEDB_REGION=us-east-1
LANCEDB_HOST_OVERRIDE=your-host-override  # optional

# Lance dataset S3 path (for blob API video streaming)
LANCE_DATASET_S3_PATH=s3://your-lancedb-bucket/your-database/videos.lance
LANCE_DATASET_S3_REGION=us-east-2
```

### 3. Ingest videos

```bash
uv run scripts/ingest.py --reset -V
```

### 4. Start backend + ngrok in tmux

```bash
# Start backend
tmux new -s backend
uv run scripts/start_server.py
# Ctrl+B, D to detach

# Start ngrok tunnel
tmux new -s ngrok
ngrok http 8000 --url your-name.ngrok-free.app
# Ctrl+B, D to detach
```

To reconnect later:

```bash
tmux attach -t backend
tmux attach -t ngrok
```

To stop everything:

```bash
tmux kill-session -t backend
tmux kill-session -t ngrok
```

### 5. Update CORS

Add your Vercel frontend URL to `.env`:

```bash
CORS_ORIGIN=https://your-app.vercel.app
```

## Vercel Setup

### 1. Deploy frontend

Connect the `frontend/` directory to Vercel (via GitHub integration or `vercel` CLI).

### 2. Set environment variable

In Vercel dashboard → Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL=https://your-name.ngrok-free.app
```

### 3. Enable password protection

Vercel dashboard → Settings → General → Password Protection.

## Verify

1. Open your Vercel URL, enter the password
2. Ask a question in the chat
3. Confirm video snippets stream from EC2 via ngrok
