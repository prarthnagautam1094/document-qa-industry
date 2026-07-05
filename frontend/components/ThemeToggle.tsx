"use client";

import { useSyncExternalStore } from "react";
import { motion } from "framer-motion";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

const noopSubscribe = () => () => {};

/** Sun/moon toggle button. The icon is only rendered once actually on the
 * client: server-rendered markup always assumes "dark" (it has no access
 * to localStorage), but the client's real starting theme can differ, so
 * rendering the theme-dependent icon during the SSR/hydration pass would
 * produce a hydration mismatch. useSyncExternalStore's separate server
 * snapshot is React's documented way to detect "am I on the client yet"
 * without the extra render + lint friction of a mounted-flag + useEffect. */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isClient = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false
  );

  return (
    <button
      onClick={toggleTheme}
      aria-label={isClient ? `Switch to ${theme === "dark" ? "light" : "dark"} mode` : "Toggle theme"}
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-bg-surface text-text-muted transition-colors hover:text-accent-cyan"
    >
      {isClient ? (
        <motion.span
          key={theme}
          initial={{ opacity: 0, rotate: -90, scale: 0.6 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="flex items-center justify-center"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </motion.span>
      ) : (
        <span className="block h-[15px] w-[15px]" />
      )}
    </button>
  );
}
