"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Minimal local typings for the Web Speech API's SpeechRecognition —
 * TypeScript's standard DOM lib doesn't include it (it's still
 * non-standard/webkit-prefixed in most browsers), so these are declared
 * here rather than assumed to exist globally. Only the pieces this hook
 * actually uses are typed; everything else stays untouched.
 */
interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly [index: number]: { readonly transcript: string };
}

interface SpeechRecognitionEventLike extends Event {
  readonly results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
}

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface UseSpeechRecognitionResult {
  /** False in browsers with no SpeechRecognition (or its webkit-prefixed
   * variant) at all — Firefox desktop and most non-Chromium browsers. */
  isSupported: boolean;
  isListening: boolean;
  /** Live transcript — interim results while listening, then the final
   * result once recognition stops. Never cleared automatically; the
   * caller owns when to reset it (e.g. after the user sends/edits it). */
  transcript: string;
  error: string | null;
  startListening: () => void;
  stopListening: () => void;
  resetTranscript: () => void;
}

export interface UseSpeechRecognitionOptions {
  /** Called synchronously from the browser's own `onresult` event with
   * the latest combined (interim + final) transcript — lets a consumer
   * like ChatInput mirror live speech into its own input state directly
   * from this external-system callback, without needing a
   * useEffect+setState round trip to react to `transcript` changing. */
  onTranscript?: (transcript: string) => void;
}

/**
 * Wraps the browser's native SpeechRecognition API for voice input.
 * `continuous = false` (one utterance per start/stop cycle) with
 * `interimResults = true` so the caller can show live, updating text
 * while the user is still talking, not just the final result.
 */
export function useSpeechRecognition(
  options: UseSpeechRecognitionOptions = {}
): UseSpeechRecognitionResult {
  const { onTranscript } = options;
  const [isSupported] = useState(() => getSpeechRecognitionCtor() !== null);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  // Kept in a ref (not a dependency of startListening below) so a new
  // onTranscript identity on every render doesn't force
  // startListening/recognition.onresult to be recreated. Updated from an
  // effect (not directly during render) since refs must only be written
  // outside of rendering.
  const onTranscriptRef = useRef(onTranscript);
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  });

  // Stop any in-flight recognition if the component using this hook
  // unmounts mid-listen (e.g. navigating away) — otherwise the browser
  // keeps the microphone open with no UI left to show for it.
  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  const startListening = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setError("Voice input isn't supported in this browser.");
      return;
    }

    setError(null);
    setTranscript("");

    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      let combined = "";
      for (let i = 0; i < event.results.length; i++) {
        combined += event.results[i][0].transcript;
      }
      setTranscript(combined);
      onTranscriptRef.current?.(combined);
    };
    recognition.onerror = (event) => {
      setError(
        event.error === "not-allowed" || event.error === "permission-denied"
          ? "Microphone access was denied."
          : "Voice input failed. Please try again."
      );
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const resetTranscript = useCallback(() => setTranscript(""), []);

  return {
    isSupported,
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
    resetTranscript,
  };
}
