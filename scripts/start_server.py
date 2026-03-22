#!/usr/bin/env python3
"""Start the API server with local or remote LanceDB.

Usage:
    uv run scripts/serve.py                          # Remote DB (default)
    uv run scripts/serve.py --local                  # Local DB at ./data/lancedb
    uv run scripts/serve.py --local --db-path /tmp/db # Local DB at custom path
    uv run scripts/serve.py --remote                 # Explicit remote DB
"""

import argparse
import os
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start the yt-agents API server")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--local", "-l", action="store_true", help="Use local LanceDB")
    group.add_argument("--remote", "-r", action="store_true", default=True, help="Use remote LanceDB Enterprise (default)")
    parser.add_argument("--db-path", default="./data/lancedb", help="Local LanceDB path (only used with --local)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    if args.local:
        os.environ["DB_LOCAL_PATH"] = args.db_path
        print(f"Starting server with local DB: {args.db_path}")
    else:
        os.environ.pop("DB_LOCAL_PATH", None)
        print("Starting server with remote LanceDB Enterprise")

    # Add src to path for imports
    src_path = str(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    os.environ["PYTHONPATH"] = src_path

    uvicorn.run("api.main:app", host="0.0.0.0", port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
