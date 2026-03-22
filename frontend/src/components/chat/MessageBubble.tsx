"use client";

import { ChatMessage } from "@/lib/types";
import { VideoSnippetCard } from "@/components/video/VideoSnippetCard";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] ${
          isUser
            ? "bg-gradient-to-r from-[var(--coral)] to-[var(--dusty-rose)] text-white rounded-2xl rounded-br-md"
            : "bg-white text-gray-800 rounded-2xl rounded-bl-md shadow-sm"
        } px-4 py-3`}
      >
        {/* Message content */}
        <div className="whitespace-pre-wrap">{message.content}</div>

        {/* Video snippets for assistant messages */}
        {!isUser && message.topChunks && message.topChunks.length > 0 && (
          <div className="mt-4 space-y-3">
            <div className="text-sm font-medium text-gray-500 mb-2">
              Related video segments:
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {message.topChunks.slice(0, 2).map((chunk, index) => (
                <VideoSnippetCard
                  key={chunk.chunk_id}
                  chunk={chunk}
                  rank={(index + 1) as 1 | 2}
                />
              ))}
            </div>
          </div>
        )}

        {/* Reasoning (optional, collapsed by default) */}
        {!isUser && message.reasoning && (
          <details className="mt-3 text-xs text-gray-400">
            <summary className="cursor-pointer hover:text-gray-600">
              Why these clips?
            </summary>
            <p className="mt-1 pl-2 border-l-2 border-gray-200">
              {message.reasoning}
            </p>
          </details>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs mt-2 ${
            isUser ? "text-white/70" : "text-gray-400"
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}
