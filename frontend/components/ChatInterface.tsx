"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { useAppState } from "@/context/AppStateContext";
import { useChat } from "@/hooks/useChat";
import { ApiError } from "@/lib/api";
import { ChatBubble } from "./ChatBubble";
import { ChatEmptyState } from "./ChatEmptyState";
import { ChatInput } from "./ChatInput";

export function ChatInterface() {
  const { documents } = useAppState();
  const { messages, isSending, sendMessage } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const hasDocuments = documents.length > 0;

  const handleSend = async (question: string) => {
    try {
      await sendMessage(question);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to get an answer. Please try again."
      );
    }
  };

  const disabled = isSending || !hasDocuments;
  const placeholder = !hasDocuments
    ? "Upload a document to start asking questions"
    : isSending
      ? "Waiting for a response…"
      : "Ask a question about your documents…";
  const helperText = !hasDocuments
    ? "Upload at least one PDF in the sidebar before asking a question."
    : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        {messages.length === 0 ? (
          <ChatEmptyState hasDocuments={hasDocuments} />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            <AnimatePresence initial={false}>
              {messages.map((message) => (
                <ChatBubble key={message.id} message={message} />
              ))}
            </AnimatePresence>
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput
        onSend={handleSend}
        disabled={disabled}
        placeholder={placeholder}
        helperText={helperText}
      />
    </div>
  );
}
