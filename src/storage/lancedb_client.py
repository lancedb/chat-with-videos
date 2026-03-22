"""LanceDB client for video search operations."""

import logging
from typing import Any, Dict, List, Optional, IO

import lance
import lancedb
import pyarrow as pa

from models.schemas import TranscriptChunk, VideoRecord

logger = logging.getLogger(__name__)


def _create_videos_schema() -> pa.Schema:
    """Create PyArrow schema for videos table with blob encoding on video_blob.

    The lance-encoding:blob metadata enables lazy blob loading via take_blobs().
    """
    return pa.schema([
        pa.field("video_id", pa.string(), nullable=False),
        pa.field("title", pa.string(), nullable=False),
        pa.field("description", pa.string(), nullable=True),
        pa.field("duration_seconds", pa.float64(), nullable=False),
        pa.field("upload_date", pa.string(), nullable=True),
        pa.field("playlist_index", pa.int64(), nullable=False),
        pa.field("channel", pa.string(), nullable=False),
        pa.field("youtube_url", pa.string(), nullable=False),
        pa.field("thumbnail_url", pa.string(), nullable=True),
        pa.field("indexed_at", pa.timestamp("us"), nullable=False),
        # Enable blob encoding for lazy loading via take_blobs()
        pa.field(
            "video_blob",
            pa.large_binary(),
            nullable=True,
            metadata={b"lance-encoding:blob": b"true"},
        ),
    ])


class VideoSearchDB:
    """LanceDB client for video search operations."""

    TABLE_VIDEOS = "videos"
    TABLE_TRANSCRIPTS = "transcripts"

    def __init__(
        self,
        uri: str,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        host_override: Optional[str] = None,
        lance_dataset_s3_path: Optional[str] = None,
        lance_dataset_s3_region: str = "us-east-2",
    ):
        """Initialize LanceDB connection.

        Args:
            uri: LanceDB URI (e.g., "db://your-database" for enterprise,
                 or "./data/lancedb" for local)
            api_key: API key for LanceDB Enterprise (optional for local)
            region: AWS region for LanceDB Enterprise (default: us-east-1)
            host_override: Optional host override for LanceDB Enterprise
            lance_dataset_s3_path: S3 path to Lance dataset for blob access
                (e.g., "s3://bucket/path/videos.lance")
            lance_dataset_s3_region: AWS region for the S3 dataset bucket
        """
        self.uri = uri
        self.is_local = not uri.startswith("db://")
        self.lance_dataset_s3_path = lance_dataset_s3_path
        self.lance_dataset_s3_region = lance_dataset_s3_region

        # Connect to LanceDB
        if uri.startswith("db://"):
            # Enterprise connection
            if not api_key:
                raise ValueError("API key required for LanceDB Enterprise")

            connect_kwargs = {"api_key": api_key}
            if region:
                connect_kwargs["region"] = region
            if host_override:
                connect_kwargs["host_override"] = host_override

            self.db = lancedb.connect(uri, **connect_kwargs)
            logger.info(f"Connected to LanceDB Enterprise: {uri} (region={region})")
        else:
            # Local connection
            self.db = lancedb.connect(uri)
            logger.info(f"Connected to local LanceDB: {uri}")

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        try:
            self.db.create_table(self.TABLE_VIDEOS, schema=_create_videos_schema())
            logger.info(f"Created table: {self.TABLE_VIDEOS}")
        except ValueError:
            pass  # Table already exists

        try:
            table = self.db.create_table(self.TABLE_TRANSCRIPTS, schema=TranscriptChunk)
            # Create FTS index on text field for hybrid search
            try:
                table.create_fts_index("text")
                logger.info(f"Created FTS index on {self.TABLE_TRANSCRIPTS}.text")
            except Exception as e:
                logger.warning(f"Could not create FTS index: {e}")
            logger.info(f"Created table: {self.TABLE_TRANSCRIPTS}")
        except ValueError:
            pass  # Table already exists

    def reset_tables(self) -> None:
        """Overwrite tables to a clean state."""
        self.db.create_table(
            self.TABLE_VIDEOS, schema=_create_videos_schema(), mode="overwrite"
        )
        logger.info(f"Reset table: {self.TABLE_VIDEOS}")

        table = self.db.create_table(
            self.TABLE_TRANSCRIPTS, schema=TranscriptChunk, mode="overwrite"
        )
        try:
            table.create_fts_index("text")
            logger.info(f"Created FTS index on {self.TABLE_TRANSCRIPTS}.text")
        except Exception as e:
            logger.warning(f"Could not create FTS index: {e}")
        logger.info(f"Reset table: {self.TABLE_TRANSCRIPTS}")

    def initialize(self, reset: bool = False) -> "VideoSearchDB":
        """Initialize tables and indices."""
        if reset:
            self.reset_tables()
        else:
            self._ensure_tables()
        return self

    def create_vector_index(self) -> None:
        """Create vector index on transcripts table."""
        table = self.db.open_table(self.TABLE_TRANSCRIPTS)
        try:
            table.create_index(
                metric="cosine",
                index_type="IVF_PQ",
                num_partitions=256,
                num_sub_vectors=48,  # 768 dims / 48 = 16 dims per subvector
            )
            logger.info(f"Created vector index on {self.TABLE_TRANSCRIPTS}")
        except Exception as e:
            logger.warning(f"Could not create vector index: {e}")

    def add_video(self, video: VideoRecord, force_update: bool = False) -> None:
        """Add video metadata to the database (upserts if exists)."""
        # Delete existing record if present to avoid duplicates
        self._delete_from_table(self.TABLE_VIDEOS, video.video_id)
        logger.debug(f"Opening table {self.TABLE_VIDEOS} for add...")
        table = self.db.open_table(self.TABLE_VIDEOS)
        logger.debug(f"Table opened, adding video {video.video_id}...")
        table.add([video])
        logger.debug(f"Added video: {video.video_id}")

    def add_videos(self, videos: List[VideoRecord]) -> None:
        """Add multiple video metadata records."""
        if not videos:
            return
        table = self.db.open_table(self.TABLE_VIDEOS)
        table.add(videos)
        logger.info(f"Added {len(videos)} videos")

    def add_transcripts(self, transcripts: List[TranscriptChunk], force_update: bool = False) -> None:
        """Add transcript chunks to the database (upserts if exists)."""
        if not transcripts:
            return
        # Delete existing transcripts for this video to avoid duplicates
        video_id = transcripts[0].video_id
        self._delete_from_table(self.TABLE_TRANSCRIPTS, video_id)
        table = self.db.open_table(self.TABLE_TRANSCRIPTS)
        table.add(transcripts)
        logger.info(f"Added {len(transcripts)} transcript chunks")

    def _delete_from_table(self, table_name: str, video_id: str) -> None:
        """Delete all records for a video from a table."""
        try:
            table = self.db.open_table(table_name)
            table.delete(f"video_id = '{video_id}'")
        except Exception as e:
            logger.debug(f"Delete from {table_name} failed: {e}")

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve video metadata by ID (without loading blob)."""
        table = self.db.open_table(self.TABLE_VIDEOS)
        results = table.search().where(f"video_id = '{video_id}'").limit(1).to_list()
        return results[0] if results else None

    def _get_lance_dataset(self) -> lance.LanceDataset:
        """Get the underlying Lance dataset for blob access.

        For remote (Enterprise): opens directly from S3 via lance.dataset().
        For local: uses table.to_lance().
        """
        if self.lance_dataset_s3_path:
            return lance.dataset(
                self.lance_dataset_s3_path,
                storage_options={"region": self.lance_dataset_s3_region},
            )
        else:
            table = self.db.open_table(self.TABLE_VIDEOS)
            return table.to_lance()

    def _get_row_index(self, video_id: str) -> Optional[int]:
        """Get row index for a video, with caching.

        Caches the video_id -> row_idx mapping to avoid repeated full scans.
        """
        if not hasattr(self, "_row_index_cache"):
            self._row_index_cache: Dict[str, int] = {}

        if video_id in self._row_index_cache:
            return self._row_index_cache[video_id]

        lance_ds = self._get_lance_dataset()
        full_scan = lance_ds.scanner(columns=["video_id"]).to_table()
        video_ids = full_scan.column("video_id").to_pylist()

        # Cache all video_ids at once
        self._row_index_cache = {vid: idx for idx, vid in enumerate(video_ids)}

        return self._row_index_cache.get(video_id)

    def get_video_blob_file(self, video_id: str) -> Optional[IO[bytes]]:
        """Get a fresh lazy BlobFile for video using Lance take_blobs().

        Returns a NEW handle each time — do not cache BlobFile handles,
        as seek/read state gets corrupted across requests with S3-backed blobs.
        """
        row_idx = self._get_row_index(video_id)
        if row_idx is None:
            return None

        lance_ds = self._get_lance_dataset()
        blob_files = lance_ds.take_blobs(blob_column="video_blob", indices=[row_idx])
        if not blob_files:
            return None

        return blob_files[0]

    def list_videos(self) -> List[Dict[str, Any]]:
        """List all indexed videos."""
        table = self.db.open_table(self.TABLE_VIDEOS)
        return table.search().limit(None).to_list()

    def video_exists(self, video_id: str) -> bool:
        """Check if a video is already indexed."""
        return self.get_video(video_id) is not None

    def get_transcript_count(self, video_id: str) -> int:
        """Get the number of transcript chunks indexed for a video."""
        table = self.db.open_table(self.TABLE_TRANSCRIPTS)
        results = table.search().where(f"video_id = '{video_id}'").limit(10000).to_list()
        return len(results)

    def delete_video_data(self, video_id: str) -> None:
        """Delete all data for a video (for re-indexing)."""
        self._delete_from_table(self.TABLE_VIDEOS, video_id)
        self._delete_from_table(self.TABLE_TRANSCRIPTS, video_id)
        logger.debug(f"Deleted all data for {video_id}")

    def optimize_indices(self) -> None:
        """Optimize tables and rebuild indices after adding new data.

        Only runs on local LanceDB. Enterprise optimizes automatically.
        """
        if not self.is_local:
            logger.debug("Skipping optimize — LanceDB Cloud optimizes automatically")
            return
        for table_name in [self.TABLE_VIDEOS, self.TABLE_TRANSCRIPTS]:
            try:
                table = self.db.open_table(table_name)
                table.optimize()
                logger.info(f"Optimized table: {table_name}")
            except Exception as e:
                logger.warning(f"Could not optimize {table_name}: {e}")


def create_db_client(
    uri: Optional[str] = None,
    api_key: Optional[str] = None,
    region: Optional[str] = None,
    host_override: Optional[str] = None,
    local_path: Optional[str] = None,
) -> VideoSearchDB:
    """Factory function to create DB client from settings or params.

    Args:
        uri: LanceDB URI (overrides settings)
        api_key: API key (overrides settings)
        region: AWS region (overrides settings)
        host_override: Host override (overrides settings)
        local_path: If set, use local LanceDB at this path instead of enterprise
    """
    from config import get_settings

    settings = get_settings()

    if local_path:
        # Use local LanceDB
        return VideoSearchDB(uri=local_path)

    db_uri = uri or settings.lancedb_uri
    db_key = api_key or settings.lancedb_api_key
    db_region = region or settings.lancedb_region
    db_host_override = host_override or settings.lancedb_host_override

    if not db_uri:
        raise ValueError("LANCEDB_URI not set. Please set it in .env or pass explicitly.")

    return VideoSearchDB(
        uri=db_uri,
        api_key=db_key,
        region=db_region,
        host_override=db_host_override,
        lance_dataset_s3_path=settings.lance_dataset_s3_path,
        lance_dataset_s3_region=settings.lance_dataset_s3_region,
    )
