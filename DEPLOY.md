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
| **ngrok** | Free account at ngrok.com (free tier gives a random URL that changes on restart; paid plan $8/mo for a stable subdomain) |
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
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
  && echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list \
  && sudo apt update && sudo apt install ngrok

# Authenticate (get token from https://dashboard.ngrok.com/get-started/your-authtoken)
ngrok config add-authtoken your-token
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
# Free tier (random URL, changes on restart):
ngrok http 8000
# Paid tier (stable URL):
# ngrok http 8000 --url your-name.ngrok-free.app
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
NEXT_PUBLIC_API_URL=https://your-ngrok-url.ngrok-free.app
```

### 3. Enable password protection

Vercel dashboard → Settings → Deployment Protection → Password Protection (requires Vercel Pro, $20/mo). For the free tier, add a simple password page in the Next.js app instead.

## Verify

1. Open your Vercel URL, enter the password
2. Ask a question in the chat
3. Confirm video snippets stream from EC2 via ngrok

## Deploying in Production: Next Steps

The setup above uses ngrok as a quick tunnel for demos. For production, replace ngrok with Caddy on EC2 behind a real domain.

### What changes

| Demo (current) | Production |
|---------------|------------|
| ngrok tunnel (random/paid URL) | Caddy reverse proxy with auto-HTTPS |
| No domain needed | Requires a domain (e.g., `api.yourdomain.com`) |
| EC2 security group: SSH only | EC2 security group: SSH + ports 80/443 |
| Vercel `NEXT_PUBLIC_API_URL` → ngrok URL | Vercel `NEXT_PUBLIC_API_URL` → `https://api.yourdomain.com` |

### Caddy setup on EC2

1. Install Caddy: `sudo apt install caddy`
2. Point a subdomain (e.g., `api.yourdomain.com`) to the EC2 Elastic IP via DNS A record
3. Open ports 80 and 443 in the EC2 security group
4. Create `/etc/caddy/Caddyfile`:
   ```
   api.yourdomain.com {
       reverse_proxy localhost:8000
   }
   ```
5. Restart Caddy: `sudo systemctl restart caddy`

Caddy automatically provisions and renews Let's Encrypt TLS certificates. No certbot, no nginx config.

### Other production considerations

- **Process manager**: Use `systemd` services instead of tmux for FastAPI, so the server auto-restarts on crash/reboot
- **Vercel password protection**: Requires Pro plan ($20/mo). Alternatively, add a Next.js middleware password gate on the free tier
- **CORS**: Set `CORS_ORIGIN=https://your-vercel-app.vercel.app` in `.env`
- **EBS volume**: Size the root volume to at least 20GB (default 8GB fills up with Python deps + torch)
