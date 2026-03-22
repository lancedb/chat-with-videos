"""YouTube video download pipeline using yt-dlp."""

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yt_dlp

logger = logging.getLogger(__name__)


def _check_ffmpeg() -> None:
    """Check that ffmpeg is installed and available."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found. Install it with:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg"
        )


@dataclass
class VideoInfo:
    """Parsed video metadata from yt-dlp."""

    video_id: str
    title: str
    description: str
    duration: float
    upload_date: str
    playlist_index: int
    channel: str
    url: str
    thumbnail: str
    local_path: Optional[Path] = None


class PlaylistDownloader:
    """Download videos and extract metadata from YouTube playlists."""

    def __init__(
        self,
        format_spec: str = "bestvideo[height<=720]+bestaudio/best[height<=720]",
        temp_dir: Optional[Path] = None,
    ):
        self.format_spec = format_spec
        self.temp_dir = temp_dir or Path("./tmp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_ydl_opts(self, download: bool = True, output_dir: Optional[Path] = None) -> dict:
        """Configure yt-dlp options."""
        out_dir = output_dir or self.temp_dir
        opts = {
            "format": self.format_spec,
            "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
            "writeinfojson": False,
            "writedescription": False,
            "writethumbnail": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "ignoreerrors": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "merge_output_format": "mp4",
        }
        if not download:
            opts["skip_download"] = True
        return opts

    def get_video_info(self, video_url: str) -> Optional[VideoInfo]:
        """Extract metadata for a single video without downloading."""
        # Extract video ID from URL
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        else:
            video_id = video_url.split("/")[-1]

        opts = self._get_ydl_opts(download=False)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if info:
                    return VideoInfo(
                        video_id=video_id,
                        title=info.get("title", ""),
                        description=(info.get("description", "") or "")[:500],
                        duration=info.get("duration", 0) or 0,
                        upload_date=info.get("upload_date", ""),
                        playlist_index=0,
                        channel=info.get("channel", "") or info.get("uploader", ""),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        thumbnail=info.get("thumbnail", ""),
                    )
        except Exception as e:
            logger.error(f"Failed to get video info for {video_url}: {e}")

        return None

    def get_playlist_info(self, playlist_url: str) -> List[VideoInfo]:
        """Extract metadata for all videos in playlist without downloading."""
        opts = self._get_ydl_opts(download=False)
        opts["extract_flat"] = "in_playlist"

        videos = []

        with yt_dlp.YoutubeDL(opts) as ydl:
            # First get playlist entries (flat extraction)
            playlist_info = ydl.extract_info(playlist_url, download=False)

            if playlist_info is None:
                logger.error("Could not extract playlist info")
                return []

            entries = playlist_info.get("entries", [])
            logger.info(f"Found {len(entries)} videos in playlist")

            # Now get full info for each video
            for idx, entry in enumerate(entries):
                if entry is None:
                    continue

                video_id = entry.get("id") or entry.get("url", "").split("=")[-1]
                if not video_id:
                    continue

                # Get full video info
                try:
                    full_opts = self._get_ydl_opts(download=False)
                    with yt_dlp.YoutubeDL(full_opts) as ydl2:
                        video_info = ydl2.extract_info(
                            f"https://www.youtube.com/watch?v={video_id}",
                            download=False,
                        )
                        if video_info:
                            videos.append(
                                VideoInfo(
                                    video_id=video_id,
                                    title=video_info.get("title", ""),
                                    description=(video_info.get("description", "") or "")[:500],
                                    duration=video_info.get("duration", 0) or 0,
                                    upload_date=video_info.get("upload_date", ""),
                                    playlist_index=idx,
                                    channel=video_info.get("channel", "")
                                    or video_info.get("uploader", ""),
                                    url=f"https://www.youtube.com/watch?v={video_id}",
                                    thumbnail=video_info.get("thumbnail", ""),
                                )
                            )
                            logger.debug(f"Got info for: {videos[-1].title}")
                except Exception as e:
                    logger.warning(f"Could not get info for {video_id}: {e}")

        logger.info(f"Extracted info for {len(videos)} videos")
        return videos

    def download_video(self, video_url: str, video_id: str) -> Path:
        """Download a single video and return local path."""
        _check_ffmpeg()
        opts = self._get_ydl_opts(download=True, output_dir=self.temp_dir)

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url])

        # Find the downloaded file
        for ext in ["mp4", "mkv", "webm"]:
            path = self.temp_dir / f"{video_id}.{ext}"
            if path.exists():
                return path

        raise FileNotFoundError(f"Downloaded video not found for {video_id}")

    def download_locally(self, video: VideoInfo) -> VideoInfo:
        """Download video to local temp directory."""
        logger.info(f"Downloading: {video.title}")

        local_path = self.download_video(video.url, video.video_id)
        video.local_path = local_path

        return video

    def download_playlist(
        self,
        playlist_url: str,
        max_videos: Optional[int] = None,
        skip_existing: Optional[List[str]] = None,
    ) -> List[VideoInfo]:
        """Download all videos in playlist with metadata."""
        videos = self.get_playlist_info(playlist_url)
        skip_ids = set(skip_existing or [])

        if max_videos:
            videos = videos[:max_videos]

        downloaded = []
        for video in videos:
            if video.video_id in skip_ids:
                logger.info(f"Skipping existing: {video.title}")
                continue

            try:
                video = self.download_locally(video)
                downloaded.append(video)
            except Exception as e:
                logger.error(f"Failed to download {video.title}: {e}")

        return downloaded
