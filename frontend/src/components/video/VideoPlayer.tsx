"use client";

import { useRef, useEffect, useState } from "react";

interface VideoPlayerProps {
  src: string;
  startSeconds: number;
  endSeconds: number;
  className?: string;
}

export function VideoPlayer({
  src,
  startSeconds,
  endSeconds,
  className = "",
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(startSeconds);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Seek to start position when loaded
    const handleLoadedMetadata = () => {
      video.currentTime = startSeconds;
    };

    // Stop at end position
    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      if (video.currentTime >= endSeconds) {
        video.pause();
        video.currentTime = startSeconds;
        setIsPlaying(false);
      }
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);

    // Initial seek if already loaded
    if (video.readyState >= 1) {
      video.currentTime = startSeconds;
    }

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
    };
  }, [startSeconds, endSeconds]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const progress =
    ((currentTime - startSeconds) / (endSeconds - startSeconds)) * 100;

  return (
    <div className={`relative ${className}`}>
      <video
        ref={videoRef}
        src={src}
        className="w-full rounded-lg"
        preload="metadata"
        controls
      />
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 rounded-b-lg pointer-events-none">
        <div className="flex items-center justify-between text-white text-xs">
          <span>
            {formatTime(currentTime)} / {formatTime(endSeconds)}
          </span>
          <span className="bg-[var(--coral)] px-2 py-0.5 rounded-full text-[10px]">
            {formatTime(startSeconds)} - {formatTime(endSeconds)}
          </span>
        </div>
        <div className="mt-1 h-1 bg-white/30 rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--coral)] transition-all duration-100"
            style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
          />
        </div>
      </div>
    </div>
  );
}
