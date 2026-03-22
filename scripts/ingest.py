#!/usr/bin/env python3
"""Ingest videos from YouTube playlist or single video URL.

Usage:
    uv run scripts/ingest.py --video "https://www.youtube.com/watch?v=VIDEO_ID"
    uv run scripts/ingest.py --playlist "https://www.youtube.com/playlist?list=..." --max-videos 5
    uv run scripts/ingest.py --local  # Use local storage instead of S3/LanceDB Enterprise
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import get_settings, reset_settings
from pipelines.ingest import IngestPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest videos into the search database")
    parser.add_argument("--video", "-v", help="Single video URL to ingest")
    parser.add_argument("--playlist", "-p", help="YouTube playlist URL")
    parser.add_argument("--max-videos", "-m", type=int, default=10, help="Maximum videos to process")
    parser.add_argument("--local", "-l", action="store_true", help="Use local storage")
    parser.add_argument("--db-path", default="./data/lancedb", help="Local LanceDB path")
    parser.add_argument("--config", "-c", default="config/settings.yaml", help="Config file")
    parser.add_argument("--force-update", "-f", action="store_true", help="Force re-ingest (overwrites existing data)")
    parser.add_argument("--reset", action="store_true", help="Reset tables before ingesting (overwrites all data)")
    parser.add_argument("--verbose", "-V", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load settings
    reset_settings()
    settings = get_settings(args.config)

    logger.info("yt-agents ingestion")
    logger.info(f"Embedding model: {settings.yaml.embedding.model_name}")

    # Create pipeline
    if args.local:
        logger.info(f"Local mode: using {args.db_path}")
        pipeline = IngestPipeline(
            settings=settings,
            local_mode=True,
            local_db_path=args.db_path,
            reset=args.reset,
        )
    else:
        logger.info("Cloud mode: using S3 + LanceDB Enterprise")
        pipeline = IngestPipeline(settings=settings, reset=args.reset)

    # Run ingestion
    if args.video:
        logger.info(f"Ingesting single video: {args.video}")
        result = pipeline.ingest_single_video_url(
            args.video,
            skip_existing=not args.force_update,
            force_update=args.force_update,
        )

        if result.success:
            logger.info(f"Success! Indexed {result.transcript_chunk_count} transcript chunks")
        else:
            logger.error(f"Failed: {result.error}")
            sys.exit(1)
    else:
        playlist_url = args.playlist or settings.yaml.playlist.url
        logger.info(f"Ingesting playlist: {playlist_url}")

        results = pipeline.ingest_playlist(
            playlist_url=playlist_url,
            max_videos=args.max_videos,
            skip_existing=not args.force_update,
            force_update=args.force_update,
        )

        # Summary
        successful = sum(1 for r in results if r.success)
        total_chunks = sum(r.transcript_chunk_count for r in results if r.success)

        logger.info(f"Completed: {successful}/{len(results)} videos")
        logger.info(f"Total transcript chunks: {total_chunks}")

        if successful < len(results):
            sys.exit(1)


if __name__ == "__main__":
    main()
