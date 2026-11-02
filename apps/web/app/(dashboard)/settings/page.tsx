"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface TelegramSettings {
  configured: boolean;
  chat_id_masked: string | null;
}

interface MfaEnableResponse {
  secret: string;
  qr_uri: string;
}

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const [telegram, setTelegram] = useState<TelegramSettings | null>(null);
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const [mfaSetup, setMfaSetup] = useState<MfaEnableResponse | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaSubmitting, setMfaSubmitting] = useState(false);

  useEffect(() => {
    api.get<TelegramSettings>("/settings/telegram").then(setTelegram);
  }, []);

  async function saveTelegram(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const result = await api.put<TelegramSettings>("/settings/telegram", { bot_token: botToken, chat_id: chatId });
      setTelegram(result);
      setBotToken("");
      setChatId("");
      setMessage("Telegram settings saved.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function startMfaSetup() {
    setMfaError(null);
    try {
      const result = await api.post<MfaEnableResponse>("/auth/mfa/enable");
      setMfaSetup(result);
    } catch (err) {
      setMfaError(err instanceof ApiError ? err.message : "Failed to start MFA setup");
    }
  }

  async function verifyMfa(e: React.FormEvent) {
    e.preventDefault();
    setMfaSubmitting(true);
    setMfaError(null);
    try {
      await api.post("/auth/mfa/verify", { totp_code: mfaCode });
      setMfaSetup(null);
      setMfaCode("");
      await refresh();
    } catch (err) {
      setMfaError(err instanceof ApiError ? err.message : "Invalid code");
    } finally {
      setMfaSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader title="Settings" />

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 pt-0 text-sm">
          <p className="font-medium text-foreground">{user?.display_name}</p>
          <p className="text-muted-foreground">{user?.email}</p>
          <p className="text-muted-foreground">
            MFA:{" "}
            <span className={user?.totp_enabled ? "text-healthy" : "text-muted-foreground"}>
              {user?.totp_enabled ? "Enabled" : "Not enabled"}
            </span>
          </p>

          {!user?.totp_enabled && !mfaSetup && (
            <Button variant="outline" className="mt-2" onClick={startMfaSetup}>
              Enable MFA
            </Button>
          )}

          {mfaSetup && (
            <form onSubmit={verifyMfa} className="mt-3 space-y-2 rounded-md border border-card-border p-3">
              <p className="text-xs text-muted-foreground">
                Add this account to your authenticator app, either by scanning a QR code generated from the URI
                below or by entering the secret manually, then enter the 6-digit code it shows to confirm.
              </p>
              <p className="break-all rounded bg-background p-2 font-mono text-xs">{mfaSetup.qr_uri}</p>
              <p className="text-xs text-muted-foreground">
                Secret: <span className="font-mono">{mfaSetup.secret}</span>
              </p>
              <Input placeholder="6-digit code" value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} required />
              <Button type="submit" disabled={mfaSubmitting}>
                {mfaSubmitting ? "Verifying..." : "Confirm and Enable MFA"}
              </Button>
            </form>
          )}
          {mfaError && <p className="text-sm text-critical">{mfaError}</p>}
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Telegram Notifications</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground">
            {telegram?.configured
              ? `Configured (chat ${telegram.chat_id_masked}). Enter new values below to replace them.`
              : "Not configured yet. Alerts for downtime, aaPanel issues, and security events will be sent here."}
          </p>
          <form onSubmit={saveTelegram} className="mt-3 space-y-2">
            <Input placeholder="Bot token" value={botToken} onChange={(e) => setBotToken(e.target.value)} type="password" />
            <Input placeholder="Chat ID" value={chatId} onChange={(e) => setChatId(e.target.value)} />
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </form>
          {message && <p className="mt-2 text-sm text-muted-foreground">{message}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
