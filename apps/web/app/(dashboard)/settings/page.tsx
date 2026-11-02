"use client";

import { Trash2, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AdminUser } from "@/lib/types";

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

  const [admins, setAdmins] = useState<AdminUser[] | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [showAddAdmin, setShowAddAdmin] = useState(false);
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminName, setNewAdminName] = useState("");
  const [newAdminPassword, setNewAdminPassword] = useState("");
  const [addingAdmin, setAddingAdmin] = useState(false);
  const [removingAdminId, setRemovingAdminId] = useState<string | null>(null);

  function loadAdmins() {
    api.get<AdminUser[]>("/auth/users").then(setAdmins).catch(() => setAdmins([]));
  }

  useEffect(() => {
    api.get<TelegramSettings>("/settings/telegram").then(setTelegram);
    loadAdmins();
  }, []);

  async function addAdmin(e: React.FormEvent) {
    e.preventDefault();
    setAddingAdmin(true);
    setAdminError(null);
    try {
      await api.post<AdminUser>("/auth/users", {
        email: newAdminEmail,
        display_name: newAdminName,
        password: newAdminPassword,
      });
      setNewAdminEmail("");
      setNewAdminName("");
      setNewAdminPassword("");
      setShowAddAdmin(false);
      loadAdmins();
    } catch (err) {
      setAdminError(err instanceof ApiError ? err.message : "Failed to create admin account");
    } finally {
      setAddingAdmin(false);
    }
  }

  async function removeAdmin(id: string) {
    setRemovingAdminId(id);
    setAdminError(null);
    try {
      await api.delete(`/auth/users/${id}`);
      loadAdmins();
    } catch (err) {
      setAdminError(err instanceof ApiError ? err.message : "Failed to remove admin account");
    } finally {
      setRemovingAdminId(null);
    }
  }

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
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Administrators</CardTitle>
          <Button variant="outline" onClick={() => setShowAddAdmin((v) => !v)}>
            <UserPlus className="mr-1.5 h-3.5 w-3.5" />
            Add admin
          </Button>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground">
            Every admin has equal, full access to this dashboard. There&apos;s no owner tier &mdash; anyone here can
            add or remove any other admin, except themselves.
          </p>

          {showAddAdmin && (
            <form onSubmit={addAdmin} className="mt-3 space-y-2 rounded-md border border-card-border p-3">
              <Input placeholder="Full name" value={newAdminName} onChange={(e) => setNewAdminName(e.target.value)} required />
              <Input
                placeholder="Email"
                type="email"
                value={newAdminEmail}
                onChange={(e) => setNewAdminEmail(e.target.value)}
                required
              />
              <Input
                placeholder="Temporary password (min 12 characters)"
                type="password"
                minLength={12}
                value={newAdminPassword}
                onChange={(e) => setNewAdminPassword(e.target.value)}
                required
              />
              <Button type="submit" disabled={addingAdmin}>
                {addingAdmin ? "Creating..." : "Create admin account"}
              </Button>
            </form>
          )}
          {adminError && <p className="mt-2 text-sm text-critical">{adminError}</p>}

          <div className="mt-3 space-y-1.5">
            {admins === null && <p className="text-sm text-muted-foreground">Loading…</p>}
            {admins?.map((admin) => {
              const isSelf = admin.id === user?.id;
              return (
                <div
                  key={admin.id}
                  className="flex items-center justify-between rounded-md border border-card-border px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {admin.display_name} {isSelf && <span className="text-xs text-muted-foreground">(you)</span>}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{admin.email}</p>
                  </div>
                  {!isSelf && (
                    <button
                      onClick={() => removeAdmin(admin.id)}
                      disabled={removingAdminId === admin.id}
                      title="Remove admin"
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-critical disabled:opacity-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
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
