"use client";

import { useState, useCallback } from "react";
import { ChatMessage, ChatStatus, ChunkData } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>({ stage: "idle" });
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setStatus({ stage: "rewriting", message: "Analyzing your question..." });

    try {
      const response = await fetch(`${API_URL}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content, limit: 5, vector_weight: 0.8 }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Read the entire response as text first
      const text = await response.text();
      console.log("Full SSE response:", text);

      // Parse SSE events - handle both \r\n\r\n and \n\n separators
      const normalizedText = text.replace(/\r\n/g, "\n");
      const events = normalizedText.split("\n\n").filter(e => e.trim());

      let answerText = "";
      let topChunks: ChunkData[] = [];
      let reasoning = "";

      for (const event of events) {
        const lines = event.split("\n");
        let eventType = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.slice(5).trim();
          }
        }

        if (!dataStr) continue;

        try {
          const data = JSON.parse(dataStr);
          console.log("Parsed event:", eventType, data);

          if (data.stage) {
            setStatus({ stage: data.stage, message: data.message });
          }

          if (data.text) {
            answerText = data.text;
            topChunks = data.top_chunks || [];
            reasoning = data.reasoning || "";
          }

          if (eventType === "error" && data.message) {
            answerText = `Error: ${data.message}`;
          }
        } catch (e) {
          console.error("Failed to parse SSE data:", dataStr, e);
        }
      }

      // Add assistant message with the answer
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: answerText || "No response received.",
        topChunks,
        reasoning,
        timestamp: new Date(),
      };

      console.log("Adding assistant message:", assistantMessage);
      setMessages((prev) => [...prev, assistantMessage]);
      setStatus({ stage: "done" });

    } catch (error) {
      console.error("Chat error:", error);
      setStatus({
        stage: "error",
        message: error instanceof Error ? error.message : "An error occurred",
      });

      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Sorry, an error occurred while processing your question.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStatus({ stage: "idle" });
  }, []);

  return {
    messages,
    status,
    isLoading,
    sendMessage,
    clearMessages,
  };
}
