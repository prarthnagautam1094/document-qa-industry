"use client";

import { useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import { Loader2, Lock, Mail, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { supabase } from "@/lib/supabase";

type Mode = "login" | "signup";

/**
 * Email/password auth screen. Rendered standalone (no sidebar/shell) —
 * AppShell's AuthGate special-cases this route so a signed-out visitor
 * always lands here instead of a half-authenticated main app. On
 * success, AuthContext's onAuthStateChange picks up the new session and
 * AuthGate redirects to "/" itself; this component doesn't navigate.
 */
export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (mode === "login") {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (signInError) throw signInError;
      } else {
        const { data, error: signUpError } = await supabase.auth.signUp({ email, password });
        if (signUpError) throw signUpError;
        // If the Supabase project requires email confirmation, signUp
        // succeeds but returns no session — there's nothing to redirect
        // to yet, so tell the user what to do next instead of appearing
        // to silently do nothing.
        if (!data.session) {
          toast.success("Account created. Check your email to confirm before signing in.");
          setMode("login");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full w-full items-center justify-center bg-bg-page px-4">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="shadow-elevated w-full max-w-sm rounded-2xl border border-border bg-bg-surface p-6 sm:p-8"
      >
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-cyan">
            <Sparkles size={20} className="text-[#0B0E14]" />
          </div>
          <div>
            <h1 className="font-heading text-lg font-bold text-text">Document Q&amp;A</h1>
            <p className="mt-1 text-sm text-text-muted">
              {mode === "login" ? "Sign in to your account" : "Create an account"}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex items-center gap-2 rounded-lg border border-border bg-bg-page px-3 py-2 transition-colors focus-within:border-accent-cyan">
            <Mail size={15} className="shrink-0 text-text-muted" />
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-transparent text-sm text-text placeholder:text-text-muted focus:outline-none"
            />
          </label>

          <label className="flex items-center gap-2 rounded-lg border border-border bg-bg-page px-3 py-2 transition-colors focus-within:border-accent-cyan">
            <Lock size={15} className="shrink-0 text-text-muted" />
            <input
              type="password"
              required
              minLength={6}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full bg-transparent text-sm text-text placeholder:text-text-muted focus:outline-none"
            />
          </label>

          {error && <p className="text-xs text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-accent to-accent-cyan px-4 py-2 text-sm font-medium text-[#0B0E14] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting && <Loader2 size={15} className="animate-spin" />}
            {mode === "login" ? "Sign in" : "Sign up"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-text-muted">
          {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setError(null);
            }}
            className="font-medium text-accent-cyan hover:underline"
          >
            {mode === "login" ? "Sign up" : "Sign in"}
          </button>
        </p>
      </motion.div>
    </div>
  );
}
