"""Main ingestion pipeline for videos and transcripts."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from config import Settings, get_settings
from models.embeddings import LocalEmbedder, create_embedder
from models.schemas import TranscriptChunk as TranscriptChunkSchema
from models.schemas import VideoRecord
from storage.lancedb_client import VideoSearchDB, create_db_client

from .download import PlaylistDownloader, VideoInfo
from .transcripts import TranscriptExtractor

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Result of ingesting a single video."""

    video_id: str
    title: str
    transcript_chunk_count: int
    success: bool
    error: Optional[str] = None


class IngestPipeline:
    """Main pipeline for ingesting videos into the search database."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        db_client: Optional[VideoSearchDB] = None,
        embedder: Optional[LocalEmbedder] = None,
        local_mode: bool = False,
        local_db_path: str = "./data/lancedb",
        reset: bool = False,
    ):
        """Initialize the ingest pipeline.

        Args:
            settings: Configuration settings
            db_client: LanceDB client (created from settings if not provided)
            embedder: Text embedding model (created from settings if not provided)
            local_mode: If True, use local LanceDB instead of LanceDB Enterprise
            local_db_path: Path for local LanceDB (only used in local_mode)
            reset: If True, overwrite tables before ingesting
        """
        self.settings = settings or get_settings()
        self.local_mode = local_mode
        self.tmp_dir = Path("./tmp")

        # Initialize clients
        if local_mode:
            self.db = create_db_client(local_path=local_db_path).initialize(reset=reset)
        else:
            self.db = (db_client or create_db_client()).initialize(reset=reset)

        # Initialize embedder (local model, runs on CPU)
        self.embedder = embedder or create_embedder()

        # Initialize sub-pipelines
        self.downloader = PlaylistDownloader(
            format_spec=self.settings.yaml.video.format,
            temp_dir=self.tmp_dir,
        )

        self.transcript_extractor = TranscriptExtractor(
            languages=self.settings.yaml.transcripts.languages,
            chunk_duration_seconds=self.settings.yaml.transcripts.chunk_duration_seconds,
        )

    def ingest_video(
        self,
        video: VideoInfo,
        skip_download: bool = False,
        force_update: bool = False,
    ) -> IngestResult:
        """Ingest a single video through the full pipeline.

        Args:
            video: Video metadata
            skip_download: If True, assume video is already downloaded/in S3
        """
        try:
            logger.info(f"Ingesting: {video.title}")

            # Step 1: Download video locally (if not already downloaded)
            if not skip_download and not video.local_path:
                video = self.downloader.download_locally(video)

            # Step 2: Extract and chunk transcript
            logger.info("Extracting transcript...")
            chunks = self.transcript_extractor.extract_and_chunk(video.video_id)

            # Step 3: Read video blob from local file
            video_blob = None
            if video.local_path and video.local_path.exists():
                logger.info(f"Reading video blob ({video.local_path.stat().st_size / 1024 / 1024:.1f} MB)...")
                video_blob = video.local_path.read_bytes()

            if not chunks:
                logger.warning(f"No transcript available for {video.video_id}")
                # Still save video metadata even if no transcript
                video_record = VideoRecord(
                    video_id=video.video_id,
                    title=video.title,
                    description=video.description,
                    duration_seconds=video.duration,
                    upload_date=video.upload_date,
                    playlist_index=video.playlist_index,
                    channel=video.channel,
                    youtube_url=video.url,
                    thumbnail_url=video.thumbnail,
                    video_blob=video_blob,
                )
                self.db.add_video(video_record, force_update=force_update)
                self._cleanup_local_file(video)

                return IngestResult(
                    video_id=video.video_id,
                    title=video.title,
                    transcript_chunk_count=0,
                    success=True,
                )

            # Step 4: Generate embeddings for transcript chunks
            logger.info(f"Generating embeddings for {len(chunks)} transcript chunks...")
            chunk_texts = [c.text for c in chunks]
            embeddings = self.embedder.embed_texts(
                chunk_texts,
                batch_size=self.settings.yaml.embedding.batch_size,
            )

            # Step 5: Create database records
            logger.info("Creating database records...")

            video_record = VideoRecord(
                video_id=video.video_id,
                title=video.title,
                description=video.description,
                duration_seconds=video.duration,
                upload_date=video.upload_date,
                playlist_index=video.playlist_index,
                channel=video.channel,
                youtube_url=video.url,
                thumbnail_url=video.thumbnail,
                video_blob=video_blob,
            )

            transcript_records = []
            for chunk, embedding in zip(chunks, embeddings):
                transcript_records.append(
                    TranscriptChunkSchema(
                        chunk_id=f"{video.video_id}_{int(chunk.start_seconds * 1000)}",
                        video_id=video.video_id,
                        video_title=video.title,
                        start_seconds=chunk.start_seconds,
                        end_seconds=chunk.end_seconds,
                        text=chunk.text,
                        language="en",
                        vector=embedding,
                    )
                )

            # Step 6: Save to database
            logger.info("Saving to database...")
            self.db.add_video(video_record, force_update=force_update)
            self.db.add_transcripts(transcript_records, force_update=force_update)

            # Step 7: Clean up local video file
            self._cleanup_local_file(video)

            return IngestResult(
                video_id=video.video_id,
                title=video.title,
                transcript_chunk_count=len(transcript_records),
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to ingest {video.video_id}: {e}")
            self._cleanup_local_file(video)
            return IngestResult(
                video_id=video.video_id,
                title=video.title,
                transcript_chunk_count=0,
                success=False,
                error=str(e),
            )

    def _cleanup_local_file(self, video: VideoInfo) -> None:
        """Clean up local video file after ingestion."""
        if video.local_path and video.local_path.exists():
            video.local_path.unlink()
            logger.debug(f"Cleaned up local file: {video.local_path}")

    def ingest_playlist(
        self,
        playlist_url: Optional[str] = None,
        max_videos: Optional[int] = None,
        skip_existing: bool = True,
        force_update: bool = False,
    ) -> List[IngestResult]:
        """Ingest all videos from a playlist.

        Args:
            playlist_url: YouTube playlist URL (uses settings if not provided)
            max_videos: Maximum number of videos to process
            skip_existing: Skip videos already in the database
            force_update: Use merge_insert to overwrite existing data
        """
        url = playlist_url or self.settings.yaml.playlist.url
        logger.info(f"Fetching playlist info: {url}")

        # Get playlist videos
        videos = self.downloader.get_playlist_info(url)

        if max_videos:
            videos = videos[:max_videos]

        # Filter existing videos
        if skip_existing:
            existing_ids = {v["video_id"] for v in self.db.list_videos()}
            videos = [v for v in videos if v.video_id not in existing_ids]
            logger.info(f"Skipping {len(existing_ids)} existing videos")

        logger.info(f"Processing {len(videos)} videos")

        results = []
        for i, video in enumerate(videos, 1):
            logger.info(f"[{i}/{len(videos)}] Processing: {video.title}")
            result = self.ingest_video(video, force_update=force_update)
            results.append(result)

            if result.success:
                logger.info(f"  Indexed {result.transcript_chunk_count} transcript chunks")
            else:
                logger.error(f"  Failed: {result.error}")

        # Optimize indices after adding new data
        if results:
            logger.info("Optimizing indices...")
            self.db.optimize_indices()

        # Clean up tmp directory
        self._cleanup_tmp_dir()

        # Summary
        successful = sum(1 for r in results if r.success)
        logger.info(f"Completed: {successful}/{len(results)} videos ingested successfully")

        return results

    def ingest_single_video_url(self, video_url: str, skip_existing: bool = True, force_update: bool = False) -> IngestResult:
        """Ingest a single video by URL."""
        # Extract video ID
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        else:
            video_id = video_url.split("/")[-1]

        # Check if already indexed
        if skip_existing and self.db.video_exists(video_id):
            logger.info(f"Video {video_id} already indexed, skipping")
            return IngestResult(
                video_id=video_id,
                title=f"Video {video_id}",
                transcript_chunk_count=self.db.get_transcript_count(video_id),
                success=True,
            )

        # Fetch video metadata
        video = self.downloader.get_video_info(video_url)
        if not video:
            return IngestResult(
                video_id=video_id,
                title=f"Video {video_id}",
                transcript_chunk_count=0,
                success=False,
                error="Failed to fetch video metadata",
            )

        result = self.ingest_video(video, force_update=force_update)

        # Optimize indices after adding new data
        if result.success:
            logger.info("Optimizing indices...")
            self.db.optimize_indices()

        # Clean up tmp directory
        self._cleanup_tmp_dir()

        return result

    def _cleanup_tmp_dir(self) -> None:
        """Remove the tmp directory if it exists."""
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
            logger.info(f"Cleaned up tmp directory: {self.tmp_dir}")
