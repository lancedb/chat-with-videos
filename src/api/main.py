"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env file before importing routes (which import agents)
load_dotenv()

from api.routes import chat, video


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Chat with Your Videos",
    description="Ask questions about video content using AI-powered search",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
extra_origin = os.getenv("CORS_ORIGIN")
if extra_origin:
    cors_origins.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for local video serving
videos_path = Path(__file__).parent.parent.parent / "data" / "videos"
if videos_path.exists():
    app.mount("/static/videos", StaticFiles(directory=str(videos_path)), name="videos")

# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(video.router, prefix="/api/v1", tags=["video"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
