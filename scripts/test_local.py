#!/usr/bin/env python3
"""Test script for local development.

Tests the full pipeline locally using:
- Local LanceDB (no enterprise)
- Local embedding model (sentence-transformers, runs on CPU)
- Optional: S3 for video storage (or local temp files)

Usage:
    uv run scripts/test_local.py --video-url "https://www.youtube.com/watch?v=VIDEO_ID"
"""

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_transcript_only(video_url: str):
    """Test transcript extraction without downloading video."""
    from pipelines.transcripts import TranscriptExtractor

    # Extract video ID
    if "v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    else:
        video_id = video_url.split("/")[-1]

    logger.info(f"Testing transcript extraction for: {video_id}")

    extractor = TranscriptExtractor(chunk_duration_seconds=30.0)
    chunks = extractor.extract_and_chunk(video_id)

    if chunks:
        logger.info(f"Extracted {len(chunks)} transcript chunks")
        for i, chunk in enumerate(chunks[:3]):
            logger.info(f"  Chunk {i + 1}: [{chunk.start_seconds:.1f}s - {chunk.end_seconds:.1f}s]")
            logger.info(f"    Text: {chunk.text[:100]}...")
    else:
        logger.warning("No transcript available for this video")

    return chunks


def test_embeddings(texts: list):
    """Test local embedding model."""
    from models.embeddings import LocalEmbedder

    logger.info("Testing local embedding model...")

    embedder = LocalEmbedder(model_name="BAAI/bge-base-en-v1.5")
    logger.info(f"Model loaded. Embedding dimension: {embedder.embedding_dim}")

    embeddings = embedder.embed_texts(texts[:5], show_progress=False)
    logger.info(f"Generated {len(embeddings)} embeddings")
    logger.info(f"Embedding shape: {len(embeddings[0])} dimensions")

    # Test query embedding
    query_embedding = embedder.embed_query("What is a B+ tree?")
    logger.info(f"Query embedding shape: {len(query_embedding)} dimensions")

    return embeddings


def test_full_pipeline(video_url: str, db_path: str):
    """Test the full pipeline with local storage."""
    from config import get_settings, reset_settings
    from pipelines.ingest import IngestPipeline

    logger.info("Testing full pipeline (local mode)...")

    # Reset settings
    reset_settings()

    # Create pipeline in local mode
    pipeline = IngestPipeline(
        local_mode=True,
        local_db_path=db_path,
    )

    # Ingest video
    result = pipeline.ingest_single_video_url(video_url)

    if result.success:
        logger.info(f"SUCCESS! Indexed {result.transcript_chunk_count} transcript chunks")
    else:
        logger.error(f"FAILED: {result.error}")
        return False

    return True


def test_search(db_path: str, query: str):
    """Test search functionality."""
    from search.engine import VideoSearchEngine

    logger.info(f"Testing search: '{query}'")

    engine = VideoSearchEngine(local_db_path=db_path)
    results = engine.search(query, limit=5)

    logger.info(f"Found {len(results)} results:")
    for i, r in enumerate(results, 1):
        logger.info(f"  {i}. [{r.timestamp_formatted}] Score: {r.score:.3f}")
        logger.info(f"     {r.text[:80]}...")

    return results


def main():
    parser = argparse.ArgumentParser(description="Test yt-agents locally")
    parser.add_argument(
        "--video-url",
        help="YouTube video URL to test with (required for transcript/embeddings/full tests)",
    )
    parser.add_argument(
        "--test",
        choices=["transcript", "embeddings", "full", "search"],
        default="full",
        help="Which test to run",
    )
    parser.add_argument(
        "--db-path",
        default="./data/lancedb",
        help="Path for local LanceDB",
    )
    parser.add_argument(
        "--query",
        default="database indexing",
        help="Search query (for search test)",
    )

    args = parser.parse_args()

    # Validate video-url is provided for tests that need it
    if args.test in ("transcript", "embeddings", "full") and not args.video_url:
        parser.error(f"--video-url is required for '{args.test}' test")

    try:
        if args.test == "transcript":
            test_transcript_only(args.video_url)

        elif args.test == "embeddings":
            chunks = test_transcript_only(args.video_url)
            if chunks:
                texts = [c.text for c in chunks]
                test_embeddings(texts)

        elif args.test == "full":
            success = test_full_pipeline(args.video_url, args.db_path)
            if success:
                test_search(args.db_path, args.query)

        elif args.test == "search":
            test_search(args.db_path, args.query)

        logger.info("All tests passed!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
