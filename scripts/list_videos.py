#!/usr/bin/env python3
"""List all indexed videos.

Usage:
    uv run scripts/list_videos.py
    uv run scripts/list_videos.py --local
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import get_settings, reset_settings
from storage.lancedb_client import create_db_client


def main():
    parser = argparse.ArgumentParser(description="List indexed videos")
    parser.add_argument("--local", "-l", action="store_true", help="Use local LanceDB")
    parser.add_argument("--db-path", default="./data/lancedb", help="Local LanceDB path")
    parser.add_argument("--config", "-c", default="config/settings.yaml", help="Config file")

    args = parser.parse_args()

    # Load settings
    reset_settings()
    get_settings(args.config)

    # Create DB client
    if args.local:
        db = create_db_client(local_path=args.db_path)
    else:
        db = create_db_client()

    videos = db.list_videos()

    if not videos:
        print("No videos indexed yet")
        return

    print(f"Indexed Videos ({len(videos)})")
    print("-" * 80)

    for v in videos:
        duration_min = v.get("duration_seconds", 0) / 60
        chunks = db.get_transcript_count(v["video_id"])
        print(f"  {v['video_id']}: {v['title'][:50]}")
        print(f"    Duration: {duration_min:.2f} min | Chunks: {chunks}")
        print()


if __name__ == "__main__":
    main()
