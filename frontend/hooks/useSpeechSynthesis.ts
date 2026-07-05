"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { stripMarkdown } from "@/lib/utils";

export interface SpeakOptions {
  /** Called once this specific utterance finishes, whether it completed
   * naturally or was cut short by an error — not called if a *different*
   * speak()/stop() call cancels it first (that call's own stop/onEnd is
   * what fires instead). Lets a caller like VoiceContext clear "which
   * message is currently speaking" state exactly when this utterance's
   * output truly stops, without watching `isSpeaking` from an effect. */
  onEnd?: () => void;
}

export interface UseSpeechSynthesisResult {
  /** False in browsers with no `window.speechSynthesis` at all. */
  isSupported: boolean;
  isSpeaking: boolean;
  speak: (text: string, options?: SpeakOptions) => void;
  stop: () => void;
}

/**
 * Wraps the browser's native SpeechSynthesis API for voice output.
 * `window.speechSynthesis` is a single global queue shared by the whole
 * page — speak() always cancels any utterance already in progress first,
 * so only one thing is ever read aloud at a time, and callers don't need
 * to coordinate that themselves.
 */
export function useSpeechSynthesis(): UseSpeechSynthesisResult {
  // Boolean(...) rather than the `in` operator: some environments define
  // `window.speechSynthesis` as an existing-but-falsy property rather
  // than omitting it entirely, which `"speechSynthesis" in window` alone
  // would misreport as supported.
  const [isSupported] = useState(
    () => typeof window !== "undefined" && Boolean(window.speechSynthesis)
  );
  const [isSpeaking, setIsSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Stop speaking if the component using this hook unmounts mid-utterance
  // (e.g. navigating away) — otherwise the browser keeps talking with no
  // UI left showing it's doing so.
  useEffect(() => {
    return () => {
      if (isSupported) window.speechSynthesis.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stop = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    // cancel() doesn't reliably fire the utterance's onend/onerror across
    // browsers, so isSpeaking is set directly here rather than waiting on
    // an event that might never come.
    setIsSpeaking(false);
  }, [isSupported]);

  const speak = useCallback(
    (text: string, options?: SpeakOptions) => {
      if (!isSupported) return;
      window.speechSynthesis.cancel();

      const cleaned = stripMarkdown(text);
      if (!cleaned) {
        options?.onEnd?.();
        return;
      }

      const utterance = new SpeechSynthesisUtterance(cleaned);
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => {
        setIsSpeaking(false);
        options?.onEnd?.();
      };
      utterance.onerror = () => {
        setIsSpeaking(false);
        options?.onEnd?.();
      };

      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    },
    [isSupported]
  );

  return { isSupported, isSpeaking, speak, stop };
}
