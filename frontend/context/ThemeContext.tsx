"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "theme";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getInitialTheme(): Theme {
  // The inline anti-flash script in app/layout.tsx has already set
  // data-theme on <html> synchronously, before hydration — reading it
  // back here (rather than re-reading localStorage) keeps this in sync
  // with what was actually painted first, and avoids a second source of
  // truth. During SSR `document` doesn't exist, so this falls back to
  // "dark", matching the static default in the <html> tag's JSX.
  if (typeof document !== "undefined") {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
  }
  return "dark";
}

/**
 * Owns the current theme (dark/light), persists it to localStorage, and
 * keeps the <html data-theme> attribute in sync so the CSS variables in
 * app/globals.css resolve correctly. Mounted once in AppShell, above
 * everything that needs to read or toggle the theme.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // localStorage can throw in private-browsing/disabled-storage
      // contexts — the theme still works for the current session, it
      // just won't persist across a refresh.
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return ctx;
}
