"use client";

import { VideoPlayer } from "./VideoPlayer";
import { ChunkData } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface VideoSnippetCardProps {
  chunk: ChunkData;
  rank: 1 | 2;
}

export function VideoSnippetCard({ chunk, rank }: VideoSnippetCardProps) {
  const videoUrl = `${API_URL}/api/v1/video/${chunk.video_id}/stream`;

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-[var(--coral)]/20">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 bg-gradient-to-r from-[var(--coral)]/10 to-[var(--dusty-rose)]/10">
        <span className="bg-gradient-to-r from-[var(--coral)] to-[var(--dusty-rose)] text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium">
          {rank}
        </span>
        <h3 className="font-medium text-gray-800 truncate flex-1">
          {chunk.video_title}
        </h3>
        <span className="text-xs bg-gray-100 px-2 py-1 rounded-full text-gray-600">
          {chunk.timestamp_formatted}
        </span>
      </div>

      {/* Video Player */}
      <div className="aspect-video bg-gray-100">
        <VideoPlayer
          src={videoUrl}
          startSeconds={chunk.start_seconds}
          endSeconds={chunk.end_seconds}
        />
      </div>

      {/* Transcript excerpt */}
      <div className="p-3 border-t border-gray-100">
        <p className="text-sm text-gray-600">{chunk.text}</p>
      </div>
    </div>
  );
}
