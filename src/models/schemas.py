"""LanceDB Pydantic schemas for video search."""

from datetime import datetime
from typing import Optional

from lancedb.pydantic import LanceModel, Vector
from pydantic import Field


class VideoRecord(LanceModel):
    """Schema for video with blob storage."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    description: Optional[str] = Field(None, description="Video description")
    duration_seconds: float = Field(..., description="Video duration in seconds")
    upload_date: Optional[str] = Field(None, description="Upload date YYYYMMDD")
    playlist_index: int = Field(..., description="Position in playlist")
    channel: str = Field(..., description="Channel name")
    youtube_url: str = Field(..., description="Full YouTube URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    indexed_at: datetime = Field(default_factory=datetime.utcnow)
    # Video blob stored in LanceDB for lazy loading via Blob API
    video_blob: Optional[bytes] = Field(None, description="Video file bytes")


class TranscriptChunk(LanceModel):
    """Schema for transcript chunks with text embeddings."""

    chunk_id: str = Field(..., description="Unique chunk ID: {video_id}_{start_ms}")
    video_id: str = Field(..., description="Parent video ID")
    video_title: str = Field(..., description="Denormalized video title for display")
    start_seconds: float = Field(..., description="Chunk start time")
    end_seconds: float = Field(..., description="Chunk end time")
    text: str = Field(..., description="Transcript text (for FTS)")
    language: str = Field("en", description="Language code")
    vector: Vector(768) = Field(..., description="Text embedding (bge-base-en-v1.5)")
