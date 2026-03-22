"""Shared database configuration for the API layer.

Reads DB_LOCAL_PATH env var to decide local vs remote LanceDB.
When DB_LOCAL_PATH is set, uses local LanceDB at that path.
When unset, connects to LanceDB Enterprise using LANCEDB_* env vars.
"""

import os
from typing import Optional

from storage.lancedb_client import VideoSearchDB, create_db_client

_db_client: Optional[VideoSearchDB] = None


def get_db_client() -> VideoSearchDB:
    """Get or create the shared DB client singleton."""
    global _db_client
    if _db_client is None:
        local_path = os.environ.get("DB_LOCAL_PATH")
        _db_client = create_db_client(local_path=local_path)
        _db_client.initialize()
    return _db_client
