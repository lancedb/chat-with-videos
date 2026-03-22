"""Video serving service with lazy blob loading via Lance Blob API.

Uses take_blobs() to lazily load only requested byte ranges from S3,
NOT the entire video into memory. Perfect for HTTP Range requests.
"""

import asyncio
import logging
from typing import Optional, AsyncGenerator, IO

logger = logging.getLogger(__name__)


class VideoService:
    """Service for streaming video from LanceDB with lazy blob loading.

    Caches blob sizes (immutable after ingest) but gets a fresh BlobFile
    handle per read to avoid stale seek/read state with S3-backed blobs.
    """

    def __init__(self, db_client=None):
        self.db_client = db_client
        self._size_cache: dict[str, int] = {}

    def _get_blob_file(self, video_id: str) -> Optional[IO[bytes]]:
        """Get a fresh BlobFile handle — never cached."""
        if not self.db_client:
            return None
        return self.db_client.get_video_blob_file(video_id)

    def _get_blob_size_sync(self, video_id: str) -> Optional[int]:
        """Get blob size, cached after first call (size is immutable)."""
        if video_id in self._size_cache:
            return self._size_cache[video_id]

        blob_file = self._get_blob_file(video_id)
        if blob_file is None:
            return None

        size = blob_file.size()
        self._size_cache[video_id] = size
        return size

    def _read_blob_range_sync(self, video_id: str, start: int, end: int) -> Optional[bytes]:
        """Synchronous blob range read (runs in thread pool)."""
        blob_file = self._get_blob_file(video_id)
        if blob_file is None:
            return None
        blob_file.seek(start)
        return blob_file.read(end - start + 1)

    async def get_blob_size(self, video_id: str) -> Optional[int]:
        """Get blob size — cached after first call."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_blob_size_sync, video_id)

    async def read_blob_range(self, video_id: str, start: int, end: int) -> Optional[bytes]:
        """Read a byte range from blob, offloaded to thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._read_blob_range_sync, video_id, start, end
        )

    async def iter_blob_chunks(
        self, video_id: str, total_size: int, chunk_size: int = 1024 * 1024
    ) -> AsyncGenerator[bytes, None]:
        """Async iterate over blob in chunks for streaming."""
        offset = 0
        while offset < total_size:
            end = min(offset + chunk_size - 1, total_size - 1)
            chunk = await self.read_blob_range(video_id, offset, end)
            if not chunk:
                break
            yield chunk
            offset += chunk_size
