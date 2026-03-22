"use client";

import { useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";
import { ProgressSteps } from "./ProgressSteps";

export function ChatContainer() {
  const { messages, status, isLoading, sendMessage, clearMessages } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="gradient-bg p-4 shadow-md">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              Chat with Your Videos
            </h1>
            <p className="text-white/80 text-sm">
              Ask questions about video content
            </p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="text-white/80 hover:text-white text-sm px-3 py-1.5 rounded-lg
                         border border-white/30 hover:border-white/50 transition-colors"
            >
              Clear chat
            </button>
          )}
        </div>
      </header>

      {/* Messages area */}
      <main className="flex-1 overflow-y-auto chat-scroll bg-[var(--bg-light)]">
        <div className="max-w-4xl mx-auto p-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center">
              <div className="w-16 h-16 mb-4 rounded-full gradient-bg flex items-center justify-center">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="white"
                  className="w-8 h-8"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">
                Ask about your videos
              </h2>
              <p className="text-gray-500 max-w-md">
                Type a question below to search through your video transcripts
                and get answers with relevant video clips.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                  "What topics are covered?",
                  "Explain the main concepts",
                  "Find examples of...",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => sendMessage(suggestion)}
                    className="px-4 py-2 bg-white rounded-full text-sm text-gray-600
                               border border-gray-200 hover:border-[var(--coral)]
                               hover:text-[var(--coral)] transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isLoading && <ProgressSteps status={status} />}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </main>

      {/* Input area */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
