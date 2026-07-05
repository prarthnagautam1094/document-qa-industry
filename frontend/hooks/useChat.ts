"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError, askQuestion } from "@/lib/api";
import type { ChatMessage, DisplayMessage } from "@/lib/types";

function generateId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Owns the chat transcript and talks to POST /chat/ask.
 *
 * conversation_history is rebuilt from the current `messages` state on
 * every send (not accumulated separately) — the backend only uses it to
 * rewrite follow-up questions into standalone queries before retrieval,
 * so it needs exactly the prior {role, content} turns, in order, with no
 * UI-only fields (sources, pending flags) leaking into the request.
 */
export function useChat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const sessionIdRef = useRef<string>(generateId());

  const sendMessage = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isSending) return;

      const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }));

      const userMessage: DisplayMessage = { id: generateId(), role: "user", content: trimmed };
      const pendingId = generateId();
      const pendingMessage: DisplayMessage = {
        id: pendingId,
        role: "assistant",
        content: "",
        pending: true,
      };

      setMessages((prev) => [...prev, userMessage, pendingMessage]);
      setIsSending(true);

      try {
        const response = await askQuestion({
          question: trimmed,
          session_id: sessionIdRef.current,
          conversation_history: history,
        });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? {
                  ...m,
                  content: response.answer,
                  sources: response.sources,
                  sourceType: response.source_type,
                  pending: false,
                }
              : m
          )
        );
      } catch (err) {
        // Replace the pending bubble with a visible inline error rather
        // than leaving a permanent typing indicator — the caller is
        // still expected to catch this too (e.g. to show a toast), this
        // just keeps the transcript itself honest about what happened.
        const message =
          err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId ? { ...m, content: message, pending: false, sources: [] } : m
          )
        );
        throw err;
      } finally {
        setIsSending(false);
      }
    },
    [messages, isSending]
  );

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isSending, sendMessage, clearMessages };
}
