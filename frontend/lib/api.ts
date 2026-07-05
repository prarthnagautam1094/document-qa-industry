/**
 * Typed client for the FastAPI backend. Every function here corresponds
 * to exactly one endpoint documented in backend's /docs — see
 * lib/types.ts for the response shapes.
 *
 * Network failures (backend unreachable — connection refused, DNS
 * failure, timeout) and HTTP error responses (backend reachable but
 * returned 4xx/5xx) are deliberately surfaced as different ApiError
 * "kind"s, since the UI needs to tell them apart: a network failure
 * means "show the global backend-not-connected state", while an HTTP
 * error means "the backend is up, but this specific request failed" (a
 * toast, not a full-page takeover).
 */

import { supabase } from "./supabase";
import type {
  ChatRequest,
  ChatResponse,
  DeleteResponse,
  DocumentListResponse,
  HealthResponse,
  UploadResponse,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");

export type ApiErrorKind = "network" | "http";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Every protected backend route requires a Supabase-verified bearer
  // token (see backend/services/auth_service.py) — attaching it here,
  // once, means individual endpoint functions below never have to
  // remember to do it themselves. getSession() reads the already-cached
  // session (refreshing it first if it's expired), so this doesn't cost
  // a network round trip beyond what supabase-js already does internally.
  const { data } = await supabase.auth.getSession();
  const headers = new Headers(init?.headers);
  if (data.session?.access_token) {
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    // fetch() rejects (rather than resolving with a response) when the
    // request never reached a server at all — connection refused, DNS
    // failure, CORS preflight failure, etc. This is the "backend not
    // connected" case, distinct from the backend responding with an
    // error status.
    throw new ApiError(
      `Could not reach the backend at ${API_URL}. Is it running?`,
      "network"
    );
  }

  if (!response.ok) {
    // FastAPI's default error shape is {"detail": "..."} for both
    // HTTPException and 422 validation errors (where detail is an array
    // of {msg, ...} objects instead of a string).
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        detail = body.detail[0].msg;
      }
    } catch {
      // Response wasn't JSON (e.g. a proxy error page) — fall back to
      // statusText rather than failing to construct the ApiError itself.
    }
    throw new ApiError(detail, "http", response.status);
  }

  return response.json() as Promise<T>;
}

export function getApiUrl(): string {
  return API_URL;
}

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents/");
}

export async function uploadDocuments(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return request<UploadResponse>("/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function deleteDocument(filename: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/documents/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
}

export async function askQuestion(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/chat/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
