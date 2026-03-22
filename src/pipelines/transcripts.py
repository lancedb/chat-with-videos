"""Transcript extraction pipeline using yt-dlp."""

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yt_dlp

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A raw segment of transcript from YouTube."""

    text: str
    start_seconds: float
    duration_seconds: float

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds


@dataclass
class TranscriptChunk:
    """A chunk of transcript segments grouped for embedding."""

    text: str
    start_seconds: float
    end_seconds: float
    video_id: str
    segment_count: int


class TranscriptExtractor:
    """Extract and chunk transcripts from YouTube videos."""

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        chunk_duration_seconds: float = 30.0,
    ):
        self.languages = languages or ["en"]
        self.chunk_duration_seconds = chunk_duration_seconds

    def get_raw_transcript(self, video_id: str) -> List[TranscriptSegment]:
        """Fetch raw transcript segments using yt-dlp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_template = str(temp_path / "%(id)s.%(ext)s")

            # Try manual subtitles first, then auto-generated
            for sub_type in ["subtitles", "automatic_captions"]:
                opts = {
                    "skip_download": True,
                    "writesubtitles": sub_type == "subtitles",
                    "writeautomaticsub": sub_type == "automatic_captions",
                    "subtitleslangs": self.languages,
                    "subtitlesformat": "json3",
                    "outtmpl": output_template,
                    "quiet": True,
                    "no_warnings": True,
                }

                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

                    # Look for the downloaded subtitle file
                    for lang in self.languages:
                        sub_file = temp_path / f"{video_id}.{lang}.json3"
                        if sub_file.exists():
                            segments = self._parse_json3(sub_file)
                            if segments:
                                logger.info(
                                    f"Extracted {len(segments)} transcript segments "
                                    f"for {video_id} ({sub_type}, {lang})"
                                )
                                return segments

                except Exception as e:
                    logger.debug(f"Failed to get {sub_type} for {video_id}: {e}")
                    continue

            logger.warning(f"No transcript found for {video_id}")
            return []

    def _parse_json3(self, filepath: Path) -> List[TranscriptSegment]:
        """Parse yt-dlp's json3 subtitle format."""
        try:
            with open(filepath) as f:
                data = json.load(f)

            segments = []
            for event in data.get("events", []):
                # Skip events without text segments
                segs = event.get("segs")
                if not segs:
                    continue

                # Combine all text segments in this event
                text = "".join(s.get("utf8", "") for s in segs).strip()
                if not text:
                    continue

                # Times are in milliseconds
                start_ms = event.get("tStartMs", 0)
                duration_ms = event.get("dDurationMs", 0)

                segments.append(
                    TranscriptSegment(
                        text=text,
                        start_seconds=start_ms / 1000.0,
                        duration_seconds=duration_ms / 1000.0,
                    )
                )

            return segments

        except Exception as e:
            logger.error(f"Failed to parse subtitle file {filepath}: {e}")
            return []

    def chunk_transcript(
        self,
        segments: List[TranscriptSegment],
        video_id: str,
    ) -> List[TranscriptChunk]:
        """Group transcript segments into fixed-duration chunks for embedding.

        Args:
            segments: Raw transcript segments
            video_id: Video ID for the chunks

        Returns:
            List of transcript chunks
        """
        if not segments:
            return []

        chunks = []
        current_text = []
        current_start = segments[0].start_seconds
        current_end = segments[0].start_seconds
        segment_count = 0

        for seg in segments:
            # Check if this segment fits in current chunk
            if seg.start_seconds - current_start < self.chunk_duration_seconds:
                current_text.append(seg.text)
                current_end = seg.end_seconds
                segment_count += 1
            else:
                # Save current chunk and start new one
                if current_text:
                    chunks.append(
                        TranscriptChunk(
                            text=" ".join(current_text),
                            start_seconds=current_start,
                            end_seconds=current_end,
                            video_id=video_id,
                            segment_count=segment_count,
                        )
                    )

                # Start new chunk
                current_text = [seg.text]
                current_start = seg.start_seconds
                current_end = seg.end_seconds
                segment_count = 1

        # Don't forget the last chunk
        if current_text:
            chunks.append(
                TranscriptChunk(
                    text=" ".join(current_text),
                    start_seconds=current_start,
                    end_seconds=current_end,
                    video_id=video_id,
                    segment_count=segment_count,
                )
            )

        logger.info(f"Created {len(chunks)} transcript chunks from {len(segments)} segments")
        return chunks

    def extract_and_chunk(self, video_id: str) -> List[TranscriptChunk]:
        """Extract transcript and chunk it in one step."""
        segments = self.get_raw_transcript(video_id)
        return self.chunk_transcript(segments, video_id)

    def get_text_at_timestamp(
        self,
        chunks: List[TranscriptChunk],
        timestamp_seconds: float,
    ) -> Optional[str]:
        """Get the transcript text at a specific timestamp."""
        for chunk in chunks:
            if chunk.start_seconds <= timestamp_seconds <= chunk.end_seconds:
                return chunk.text
        return None
