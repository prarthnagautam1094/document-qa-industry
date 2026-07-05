/**
 * Created by Prarthna Gautam (https://github.com/prarthnagautam1094) — 2026.
 * Part of the Document Q&A project.
 */

import type { Metadata } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["500", "700"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Document Q&A",
  description: "Ask questions grounded in your own documents. Built by Prarthna Gautam.",
  authors: [{ name: "Prarthna Gautam", url: "https://github.com/prarthnagautam1094" }],
};

// Sets data-theme on <html> from localStorage before React hydrates, so
// the page never paints the wrong theme and then flashes to the right
// one. Must run synchronously in <head> — a useEffect in ThemeProvider
// would run after first paint, which is exactly the flash this avoids.
// No user input flows into this string, so dangerouslySetInnerHTML here
// carries no injection risk; it's the only way to run a truly
// pre-hydration script in the App Router.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      // The inline script above legitimately overwrites data-theme before
      // hydration when a light preference was saved — that's the anti-
      // flash mechanism working as intended, not a bug, so this specific
      // attribute is expected to differ between the SSR markup and the
      // real DOM at hydration time. suppressHydrationWarning scopes that
      // exception to just this element/attribute rather than silencing
      // hydration warnings anywhere else in the tree.
      suppressHydrationWarning
      className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="h-full font-sans">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
