#!/usr/bin/env python3
"""Search indexed video transcripts.

Usage:
    uv run scripts/search.py "B+ tree insertion"
    uv run scripts/search.py "database indexing" --limit 5
    uv run scripts/search.py "query" --local  # Use local LanceDB
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import get_settings, reset_settings
from search.engine import VideoSearchEngine


def main():
    parser = argparse.ArgumentParser(description="Search video transcripts")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Number of results")
    parser.add_argument("--type", "-t", default="vector", choices=["vector", "fts", "hybrid"])
    parser.add_argument("--video", "-v", help="Filter by video ID")
    parser.add_argument("--local", "-l", action="store_true", help="Use local LanceDB")
    parser.add_argument("--db-path", default="./data/lancedb", help="Local LanceDB path")
    parser.add_argument("--config", "-c", default="config/settings.yaml", help="Config file")

    args = parser.parse_args()

    # Load settings
    reset_settings()
    get_settings(args.config)

    # Create search engine
    if args.local:
        engine = VideoSearchEngine(local_db_path=args.db_path)
    else:
        engine = VideoSearchEngine()

    print(f'Searching: "{args.query}"\n')

    # Search
    results = engine.search(
        args.query,
        limit=args.limit,
        search_type=args.type,
        video_id=args.video,
    )

    if not results:
        print("No results found")
        return

    # Display results
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r.timestamp_formatted}] Score: {r.score:.3f}")
        print(f"   Video: {r.video_title}")
        print(f"   Text: {r.text[:100]}...")
        print()


if __name__ == "__main__":
    main()
