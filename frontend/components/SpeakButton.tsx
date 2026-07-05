"use client";

import { Volume2, VolumeX } from "lucide-react";
import { useVoice } from "@/context/VoiceContext";
import { cn } from "@/lib/utils";

interface SpeakButtonProps {
  messageId: string;
  text: string;
}

/** Reads one assistant answer aloud via the shared VoiceContext — toggles
 * to a stop icon while this specific message is the one currently
 * speaking (only one utterance can play at a time app-wide, so clicking
 * a different bubble's button takes over from this one). Disabled with
 * an explanatory tooltip in browsers without SpeechSynthesis rather than
 * hidden, so it's clear the feature exists but isn't available here. */
export function SpeakButton({ messageId, text }: SpeakButtonProps) {
  const { isSupported, speakingMessageId, toggleSpeak } = useVoice();
  const isSpeakingThis = speakingMessageId === messageId;

  return (
    <button
      onClick={() => toggleSpeak(messageId, text)}
      disabled={!isSupported}
      title={
        isSupported
          ? isSpeakingThis
            ? "Stop reading aloud"
            : "Read answer aloud"
          : "Voice output isn't supported in this browser."
      }
      aria-label={isSpeakingThis ? "Stop reading answer aloud" : "Read answer aloud"}
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors",
        isSpeakingThis
          ? "bg-accent-cyan/15 text-accent-cyan"
          : "text-text-muted hover:bg-tint hover:text-text",
        !isSupported && "cursor-not-allowed opacity-40 hover:bg-transparent hover:text-text-muted"
      )}
    >
      {isSpeakingThis ? <VolumeX size={13} /> : <Volume2 size={13} />}
    </button>
  );
}
