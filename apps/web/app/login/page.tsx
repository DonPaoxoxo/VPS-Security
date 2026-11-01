"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
    return <div className="flex h-screen items-center justify-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="flex h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-lg border border-card-border bg-card p-6">
        <h1 className="text-lg font-semibold">Server Security Center</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {setupRequired ? "Create the owner account to get started." : "Sign in to your private dashboard."}
        </p>

        <form onSubmit={setupRequired ? handleSetup : handleLogin} className="mt-6 space-y-3">
          {setupRequired && (
            <Input
              placeholder="Display name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          )}
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder={setupRequired ? "Password (min 12 characters)" : "Password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={setupRequired ? 12 : undefined}
            required
          />
          {!setupRequired && needsTotp && (
            <Input
              placeholder="6-digit MFA code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              required
            />
          )}

          {error && <p className="text-sm text-critical">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {setupRequired ? "Create owner account" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
