"""Video-related API routes with lazy blob loading."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from api.db_config import get_db_client
from api.services.video_service import VideoService

router = APIRouter()


_video_service: VideoService | None = None


def _get_video_service() -> VideoService:
    global _video_service
    if _video_service is None:
        _video_service = VideoService(db_client=get_db_client())
    return _video_service


class VideoInfo(BaseModel):
    """Video metadata response."""
    video_id: str
    title: str
    duration_seconds: float
    youtube_url: str
    thumbnail_url: Optional[str] = None
    has_blob: bool = False


@router.get("/video/{video_id}/info", response_model=VideoInfo)
async def get_video_info(video_id: str):
    """Get video metadata."""
    db = get_db_client()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    return VideoInfo(
        video_id=video["video_id"],
        title=video["title"],
        duration_seconds=video["duration_seconds"],
        youtube_url=video["youtube_url"],
        thumbnail_url=video.get("thumbnail_url"),
        has_blob=video.get("video_blob") is not None,
    )


@router.get("/video/{video_id}/stream")
async def stream_video(
    video_id: str,
    range: Optional[str] = Header(None),
):
    """Stream video using Lance Blob API with HTTP Range support.

    Uses take_blobs() for lazy loading - only reads the requested
    byte range from disk, NOT the entire video into memory.
    """
    video_service = _get_video_service()
    # Get blob size without loading content
    total_size = await video_service.get_blob_size(video_id)
    if total_size is None:
        raise HTTPException(status_code=404, detail=f"Video blob not found: {video_id}")

    # Parse Range header if present
    if range and range.startswith("bytes="):
        range_spec = range[6:]
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else total_size - 1
        end = min(end, total_size - 1)

        # Read only the requested byte range (async, offloaded to thread pool)
        content = await video_service.read_blob_range(video_id, start, end)
        if content is None:
            raise HTTPException(status_code=500, detail="Failed to read blob range")

        return Response(
            content=content,
            status_code=206,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(len(content)),
            },
        )

    # No range - stream in async chunks to avoid loading full video
    return StreamingResponse(
        video_service.iter_blob_chunks(video_id, total_size),
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(total_size),
        },
    )
