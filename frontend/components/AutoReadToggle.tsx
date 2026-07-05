"use client";

import { Volume2 } from "lucide-react";
import { useVoice } from "@/context/VoiceContext";
import { cn } from "@/lib/utils";

/** Sidebar toggle for automatically reading each new assistant answer
 * aloud as soon as it arrives — persisted via VoiceContext (localStorage)
 * so it survives a refresh. Disabled with a tooltip when the browser has
 * no SpeechSynthesis support, rather than hidden. */
export function AutoReadToggle() {
  const { isSupported, autoReadEnabled, setAutoReadEnabled } = useVoice();

  return (
    <button
      type="button"
      role="switch"
      aria-checked={autoReadEnabled}
      onClick={() => setAutoReadEnabled(!autoReadEnabled)}
      disabled={!isSupported}
      title={isSupported ? undefined : "Voice output isn't supported in this browser."}
      className={cn(
        "flex items-center justify-between gap-2 rounded-lg border border-border bg-bg-surface px-2.5 py-2 text-left transition-colors",
        !isSupported && "cursor-not-allowed opacity-50"
      )}
    >
      <span className="flex items-center gap-2 text-xs font-medium text-text">
        <Volume2 size={14} className="shrink-0 text-text-muted" />
        Auto-read responses
      </span>
      <span
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full transition-colors",
          autoReadEnabled ? "bg-accent-cyan" : "bg-tint"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-soft transition-transform",
            autoReadEnabled ? "translate-x-4" : "translate-x-0.5"
          )}
        />
      </span>
    </button>
  );
}
