"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { Mic, Send } from "lucide-react";
import { toast } from "sonner";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
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
 * `placeholder`/`helperText`, set by the caller). Also supports voice
 * dictation via the mic button — see useSpeechRecognition. */
export function ChatInput({ onSend, disabled, placeholder, helperText }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const {
    isSupported: micSupported,
    isListening,
    error: micError,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    // Mirror the live (interim + final) transcript into the textarea so
    // the user sees their words appear as they speak — once recognition
    // stops, whatever's there stays put and editable rather than being
    // auto-sent, per the "review before sending" intent. Called directly
    // from the browser's own recognition event, not an effect.
    onTranscript: setValue,
  });

  useEffect(() => {
    if (micError) toast.error(micError);
  }, [micError]);

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

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  return (
    <div className="border-t border-border bg-bg-page/95 px-4 py-4 backdrop-blur sm:px-6">
      {isListening ? (
        <p className="mb-2 flex items-center justify-center gap-1.5 text-center text-xs font-medium text-accent-cyan">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-cyan opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-cyan" />
          </span>
          Listening…
        </p>
      ) : (
        helperText && <p className="mb-2 text-center text-xs text-text-muted">{helperText}</p>
      )}
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
          onClick={handleMicClick}
          disabled={disabled || !micSupported}
          aria-label={isListening ? "Stop voice input" : "Start voice input"}
          title={micSupported ? undefined : "Voice input isn't supported in this browser."}
          className={cn(
            "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border transition-colors",
            isListening
              ? "border-transparent bg-red-500/15 text-red-400"
              : "border-border bg-transparent text-text-muted hover:text-accent-cyan",
            (disabled || !micSupported) && "cursor-not-allowed opacity-40 hover:text-text-muted"
          )}
        >
          <motion.span
            animate={isListening ? { scale: [1, 1.15, 1] } : { scale: 1 }}
            transition={{ duration: 1.1, repeat: isListening ? Infinity : 0, ease: "easeInOut" }}
            className="flex items-center justify-center"
          >
            <Mic size={16} />
          </motion.span>
        </button>
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
