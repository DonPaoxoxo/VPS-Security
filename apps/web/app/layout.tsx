import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth-context";

import "./globals.css";

export const metadata: Metadata = {
  title: "Server Security Center",
  description: "Multi-server security, uptime, and domain monitoring.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
