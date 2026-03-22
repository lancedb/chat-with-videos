export interface ChunkData {
  chunk_id: string;
  score: number;
  video_id: string;
  video_title: string;
  start_seconds: number;
  end_seconds: number;
  timestamp_formatted: string;
  text: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  chunks?: ChunkData[];
  topChunks?: ChunkData[];
  reasoning?: string;
  timestamp: Date;
}

export interface ChatStatus {
  stage: "idle" | "rewriting" | "searching" | "ranking" | "done" | "error";
  message?: string;
}

export interface VideoSnippet {
  url: string;
  start_seconds: number;
  end_seconds: number;
  type: "local" | "s3" | "youtube" | "unavailable";
}
