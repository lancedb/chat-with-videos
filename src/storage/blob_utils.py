"""Utilities for on-demand video frame extraction using Lance Blob API."""

import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import av
import lance
from PIL import Image

logger = logging.getLogger(__name__)


def extract_frames_from_lance(
    lance_dataset_path: str,
    video_id: str,
    timestamps: List[float],
    frame_size: Optional[int] = 512,
) -> List[Tuple[float, Image.Image]]:
    """Extract frames from a video stored as a Lance blob.

    Uses Lance's blob API for efficient access to large video files.

    Args:
        lance_dataset_path: Path to Lance dataset (local or S3)
        video_id: Video ID to look up in the dataset
        timestamps: List of timestamps in seconds
        frame_size: Resize frames to this size (square). None to keep original.

    Returns:
        List of (timestamp, PIL.Image) tuples
    """
    # Open Lance dataset
    ds = lance.dataset(lance_dataset_path)

    # Find the row with this video_id
    # Note: This is a simple approach; for production, you'd want an index
    table = ds.to_table(filter=f"video_id = '{video_id}'", columns=["video_id"])
    if len(table) == 0:
        raise ValueError(f"Video not found: {video_id}")

    row_ids = ds.to_table(
        filter=f"video_id = '{video_id}'",
        columns=[],
        with_row_id=True,
    ).column("_rowid").to_pylist()

    if not row_ids:
        raise ValueError(f"Video not found: {video_id}")

    row_id = row_ids[0]

    # Get video blob
    blobs = ds.take_blobs("video_blob", ids=[row_id])

    frames = []
    with blobs[0] as video_file:
        # Write to temp file for PyAV (it needs a seekable file)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_file.read())
            tmp_path = Path(tmp.name)

        try:
            frames = _extract_frames_from_file(tmp_path, timestamps, frame_size)
        finally:
            tmp_path.unlink(missing_ok=True)

    return frames


def _extract_frames_from_file(
    video_path: Path,
    timestamps: List[float],
    frame_size: Optional[int] = 512,
) -> List[Tuple[float, Image.Image]]:
    """Extract frames from a video file at specific timestamps.

    Args:
        video_path: Path to video file
        timestamps: List of timestamps in seconds
        frame_size: Resize frames to this size (square). None to keep original.

    Returns:
        List of (timestamp, PIL.Image) tuples
    """
    frames = []

    try:
        container = av.open(str(video_path))
        stream = container.streams.video[0]
        time_base = float(stream.time_base) if stream.time_base else 1 / 30.0

        for target_ts in sorted(timestamps):
            # Seek to timestamp
            target_pts = int(target_ts / time_base)
            container.seek(target_pts, stream=stream)

            # Decode until we get a frame at or after target
            for frame in container.decode(video=0):
                frame_ts = frame.pts * time_base if frame.pts else 0
                if frame_ts >= target_ts - 0.5:  # Allow 0.5s tolerance
                    img = frame.to_image()

                    # Resize if specified
                    if frame_size:
                        img = _resize_square(img, frame_size)

                    frames.append((target_ts, img))
                    break

        container.close()

    except Exception as e:
        logger.error(f"Error extracting frames from {video_path}: {e}")
        raise

    return frames


def _resize_square(img: Image.Image, size: int) -> Image.Image:
    """Resize image to square while maintaining aspect ratio with padding."""
    # Calculate dimensions to maintain aspect ratio
    ratio = min(size / img.width, size / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    img = img.resize(new_size, Image.Resampling.LANCZOS)

    # Create square image with black padding
    square_img = Image.new("RGB", (size, size), (0, 0, 0))
    offset = ((size - new_size[0]) // 2, (size - new_size[1]) // 2)
    square_img.paste(img, offset)

    return square_img


def get_video_duration(video_path: Path) -> float:
    """Get the duration of a video in seconds."""
    try:
        container = av.open(str(video_path))
        duration = container.duration / av.time_base if container.duration else 0
        container.close()
        return duration
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return 0
