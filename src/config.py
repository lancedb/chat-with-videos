"""Configuration management using pydantic-settings."""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlaylistConfig(BaseModel):
    url: str
    name: str


class EmbeddingConfig(BaseModel):
    model_name: str = "BAAI/bge-base-en-v1.5"
    batch_size: int = 64
    normalize: bool = True


class TranscriptConfig(BaseModel):
    languages: List[str] = Field(default_factory=lambda: ["en"])
    chunk_duration_seconds: float = 30.0


class VideoConfig(BaseModel):
    format: str = "bestvideo[height<=720]+bestaudio/best[height<=720]"


class SearchConfig(BaseModel):
    default_limit: int = 10


class YAMLConfig(BaseModel):
    """Configuration loaded from YAML file."""

    playlist: PlaylistConfig
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    transcripts: TranscriptConfig = Field(default_factory=TranscriptConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)


class Settings(BaseSettings):
    """Main settings combining env vars and YAML config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LanceDB
    lancedb_uri: Optional[str] = None
    lancedb_api_key: Optional[str] = None
    lancedb_region: str = "us-east-1"
    lancedb_host_override: Optional[str] = None

    # Lance dataset S3 path (for blob API access)
    lance_dataset_s3_path: Optional[str] = None
    lance_dataset_s3_region: str = "us-east-1"

    # YAML config (loaded separately)
    _yaml_config: Optional[YAMLConfig] = None

    @property
    def yaml(self) -> YAMLConfig:
        if self._yaml_config is None:
            raise ValueError("YAML config not loaded. Call load_yaml() first.")
        return self._yaml_config

    def load_yaml(self, path: str = "config/settings.yaml") -> "Settings":
        """Load YAML configuration file."""
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(yaml_path) as f:
            config_data = yaml.safe_load(f)

        self._yaml_config = YAMLConfig(**config_data)
        return self

    # Global settings instance
_settings: Optional[Settings] = None


def get_settings(config_path: str = "config/settings.yaml") -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings().load_yaml(config_path)
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global _settings
    _settings = None
