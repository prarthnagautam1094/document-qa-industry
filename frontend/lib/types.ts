/**
 * TypeScript types mirroring the FastAPI backend's Pydantic schemas
 * (backend/models/schemas.py) exactly — field names and optionality here
 * should always match that file, since this is the only contract between
 * the two codebases.
 */

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatRequest {
  question: string;
  session_id: string;
  conversation_history: ChatMessage[];
}

export interface ChatResponse {
  answer: string;
  sources: string[];
}

export interface DocumentInfo {
  filename: string;
  chunk_count: number;
  upload_timestamp: string | null;
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
}

export type UploadStatus = "success" | "failed";

export interface UploadResult {
  filename: string;
  status: UploadStatus;
  chunk_count: number | null;
  detail: string | null;
}

export interface UploadResponse {
  results: UploadResult[];
  total_chunks: number;
}

export interface DeleteResponse {
  filename: string;
  message: string;
}

export interface HealthResponse {
  status: string;
}

/**
 * A chat message as displayed in the UI — a superset of ChatMessage that
 * also carries per-message UI state (sources, a client-side id for React
 * keys/animation, and a pending flag for the in-flight assistant turn).
 */
export interface DisplayMessage {
  id: string;
  role: ChatRole;
  content: string;
  sources?: string[];
  pending?: boolean;
}
