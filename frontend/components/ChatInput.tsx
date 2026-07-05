"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (question: string) => void;
  disabled: boolean;
  placeholder: string;
  helperText?: string;
}

/** Sticky bottom chat input — auto-growing textarea, Enter to send
 * (Shift+Enter for a newline), disabled while a response is in flight or
 * before any document has been uploaded (the two are distinguished via
 * `placeholder`/`helperText`, set by the caller). */
export function ChatInput({ onSend, disabled, placeholder, helperText }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-bg-page/95 px-4 py-4 backdrop-blur sm:px-6">
      {helperText && <p className="mb-2 text-center text-xs text-text-muted">{helperText}</p>}
      <div
        className={cn(
          "mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border bg-bg-surface px-3 py-2 transition-colors",
          disabled ? "opacity-60" : "focus-within:border-accent-cyan"
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={placeholder}
          className="max-h-40 flex-1 resize-none bg-transparent py-1.5 text-sm text-text placeholder:text-text-muted focus:outline-none disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSend}
          disabled={disabled || value.trim() === ""}
          aria-label="Send message"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-r from-accent to-accent-cyan text-[#0B0E14] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
