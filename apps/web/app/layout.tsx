import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/lib/theme-context";

import "./globals.css";

export const metadata: Metadata = {
  title: "Server Security Center",
  description: "Multi-server security, uptime, and domain monitoring.",
};

// Runs before React hydrates so the correct theme applies on first paint —
// otherwise every load would flash dark (the CSS default) before the
// stored/system preference is read client-side.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("ssc-theme");
    var theme = stored || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-screen antialiased">
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
