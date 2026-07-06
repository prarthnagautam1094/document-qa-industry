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

/** Which source(s) the backend routed the question to and grounded the
 * answer in — see backend/services/rag_service.py's classify_route(). */
export type SourceType = "document" | "web" | "both";

export interface ChatResponse {
  answer: string;
  sources: string[];
  source_type: SourceType;
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

export interface QueryCountByDate {
  date: string;
  count: number;
}

export interface DocumentQueryCount {
  filename: string;
  count: number;
}

export interface RecentConversation {
  timestamp: string;
  question: string;
  was_answered: boolean;
}

/** Response shape for GET /analytics — scoped entirely to the signed-in user. */
export interface AnalyticsResponse {
  total_documents: number;
  total_queries: number;
  success_rate: number;
  avg_response_time: number;
  queries_over_time: QueryCountByDate[];
  most_queried_documents: DocumentQueryCount[];
  recent_conversations: RecentConversation[];
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
  sourceType?: SourceType;
  pending?: boolean;
}
