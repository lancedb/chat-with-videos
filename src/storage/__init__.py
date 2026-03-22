"""Storage module."""

from .lancedb_client import VideoSearchDB, create_db_client

__all__ = ["VideoSearchDB", "create_db_client"]
