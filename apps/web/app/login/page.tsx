"use client";

import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { user, refresh } = useAuth();

  const [setupRequired, setSetupRequired] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) router.replace("/overview");
  }, [user, router]);

  useEffect(() => {
    api
      .get<{ setup_required: boolean }>("/auth/setup-required")
      .then((res) => setSetupRequired(res.setup_required))
      .catch(() => setSetupRequired(false));
  }, []);

  async function handleSetup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/setup", { email, password, display_name: displayName });
      setSetupRequired(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Setup failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/login", { email, password, totp_code: totpCode || undefined });
      await refresh();
      router.replace("/overview");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.message.toLowerCase().includes("mfa")) {
          setNeedsTotp(true);
        }
        setError(err.message);
      } else {
        setError("Login failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (setupRequired === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-accent" />
      </div>
    );
  }

  return (
    <div className="relative flex h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div
        className="pointer-events-none absolute left-1/2 top-0 h-[32rem] w-[48rem] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-20 blur-3xl"
        style={{ background: "radial-gradient(circle, hsl(var(--accent)), transparent 70%)" }}
      />

      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">Server Security Center</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {setupRequired ? "Create the owner account to get started." : "Sign in to your private dashboard."}
          </p>
        </div>

        <div className="rounded-xl border border-card-border bg-card p-6 shadow-elevated">
          <form onSubmit={setupRequired ? handleSetup : handleLogin} className="space-y-3.5">
            {setupRequired && (
              <Field label="Display name">
                <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
              </Field>
            )}
            <Field label="Email">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <Field label={setupRequired ? "Password (min 12 characters)" : "Password"}>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={setupRequired ? 12 : undefined}
                required
              />
            </Field>
            {!setupRequired && needsTotp && (
              <Field label="6-digit MFA code">
                <Input value={totpCode} onChange={(e) => setTotpCode(e.target.value)} required />
              </Field>
            )}

            {error && (
              <div className="rounded-md border border-critical/30 bg-critical/10 px-3 py-2 text-sm text-critical">
                {error}
              </div>
            )}

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
              {setupRequired ? "Create owner account" : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
