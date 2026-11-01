"use client";

import { Check, Copy, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { EnrollmentToken, ServerSummary, Website } from "@/lib/types";

const STEPS = [
  "Server Information",
  "Connect Agent",
  "Verify Connection",
  "Discovering Websites",
  "Review Websites",
  "Finish",
];

export default function AddServerWizardPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Step 1 form state
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [provider, setProvider] = useState("");
  const [country, setCountry] = useState("");
  const [hasAapanel, setHasAapanel] = useState(false);
  const [aapanelUrl, setAapanelUrl] = useState("");
  const [aapanelPort, setAapanelPort] = useState("8888");

  const [server, setServer] = useState<ServerSummary | null>(null);
  const [enrollment, setEnrollment] = useState<EnrollmentToken | null>(null);
  const [copied, setCopied] = useState(false);
  const [pendingWebsites, setPendingWebsites] = useState<Website[] | null>(null);
  const [decisions, setDecisions] = useState<Record<string, "approve" | "exclude">>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleCreateServer(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.post<ServerSummary>("/servers", {
        name,
        hostname_or_ip: host,
        provider: provider || null,
        country: country || null,
        has_aapanel: hasAapanel,
        aapanel_endpoint_url: hasAapanel ? aapanelUrl : null,
        aapanel_port: hasAapanel ? Number(aapanelPort) : null,
      });
      setServer(created);
      const token = await api.post<EnrollmentToken>(`/servers/${created.id}/enrollment-token`);
      setEnrollment(token);
      setStep(1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create server");
    } finally {
      setSubmitting(false);
    }
  }

  // Step 3: poll for agent connection
  useEffect(() => {
    if (step !== 2 || !server) return;
    let cancelled = false;
    const interval = setInterval(async () => {
      try {
        const updated = await api.get<ServerSummary>(`/servers/${server.id}`);
        if (cancelled) return;
        setServer(updated);
        if (updated.agent_status === "connected") {
          setStep(3);
        }
      } catch {
        // keep polling silently; transient network errors shouldn't halt the wizard
      }
    }, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [step, server]);

  // Step 4: poll for discovered websites once agent is connected
  useEffect(() => {
    if (step !== 3 || !server) return;
    let cancelled = false;
    const interval = setInterval(async () => {
      try {
        const results = await api.get<Website[]>(`/domains/pending-review?server_id=${server.id}`);
        if (cancelled) return;
        if (results.length > 0) {
          setPendingWebsites(results);
          setDecisions(Object.fromEntries(results.map((w) => [w.id, "approve" as const])));
          setStep(4);
        }
      } catch {
        // keep polling
      }
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [step, server]);

  async function handleSubmitReview() {
    if (!pendingWebsites) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/domains/review", {
        decisions: pendingWebsites.map((w) => ({
          website_id: w.id,
          decision: decisions[w.id] ?? "exclude",
          enable_monitoring: true,
        })),
      });
      setStep(5);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save review decisions");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold">Add Server</h1>
      <ol className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
        {STEPS.map((s, i) => (
          <li
            key={s}
            className={`rounded-md px-2 py-1 ${i === step ? "bg-accent/20 text-accent" : i < step ? "text-healthy" : ""}`}
          >
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      {error && <p className="mt-4 text-sm text-critical">{error}</p>}

      <Card className="mt-6">
        <CardContent className="p-6">
          {step === 0 && (
            <form onSubmit={handleCreateServer} className="space-y-3">
              <Field label="Server Name">
                <Input value={name} onChange={(e) => setName(e.target.value)} required />
              </Field>
              <Field label="Server IP / Hostname">
                <Input value={host} onChange={(e) => setHost(e.target.value)} required />
              </Field>
              <Field label="Provider (optional)">
                <Input value={provider} onChange={(e) => setProvider(e.target.value)} />
              </Field>
              <Field label="Country / Region (optional)">
                <Input value={country} onChange={(e) => setCountry(e.target.value)} />
              </Field>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={hasAapanel} onChange={(e) => setHasAapanel(e.target.checked)} />
                aaPanel is installed on this server
              </label>
              {hasAapanel && (
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-2">
                    <Field label="aaPanel URL">
                      <Input
                        placeholder="https://1.2.3.4"
                        value={aapanelUrl}
                        onChange={(e) => setAapanelUrl(e.target.value)}
                      />
                    </Field>
                  </div>
                  <Field label="Port">
                    <Input value={aapanelPort} onChange={(e) => setAapanelPort(e.target.value)} />
                  </Field>
                </div>
              )}
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Creating..." : "Continue"}
              </Button>
            </form>
          )}

          {step === 1 && enrollment && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Run this command as root on the new server. It installs the lightweight agent, enrolls it with a
                one-time token (expires {new Date(enrollment.expires_at).toLocaleTimeString()}), and starts it as a
                systemd service.
              </p>
              <div className="relative rounded-md bg-background p-3 font-mono text-xs">
                <pre className="overflow-x-auto whitespace-pre-wrap">{enrollment.install_command}</pre>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(enrollment.install_command);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="absolute right-2 top-2 rounded-md bg-muted p-1.5 hover:opacity-80"
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
              <Button onClick={() => setStep(2)} className="w-full">
                I've run the install command
              </Button>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-accent" />
              <p className="text-sm">Waiting for the agent to connect...</p>
              <p className="text-xs text-muted-foreground">
                Current status: <span className="font-medium">{server?.agent_status ?? "pending"}</span>. This
                checks automatically every few seconds — no need to refresh.
              </p>
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-accent" />
              <p className="text-sm">Agent connected. Running read-only website discovery...</p>
              <div className="mt-2 grid grid-cols-3 gap-4 text-xs text-muted-foreground">
                <div>OS: {server?.operating_system ?? "—"}</div>
                <div>CPU: {server?.cpu_pct != null ? `${server.cpu_pct.toFixed(0)}%` : "—"}</div>
                <div>RAM: {server?.ram_pct != null ? `${server.ram_pct.toFixed(0)}%` : "—"}</div>
              </div>
            </div>
          )}

          {step === 4 && pendingWebsites && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Found {pendingWebsites.length} website(s). Approve the ones you want monitored, or exclude the rest.
              </p>
              {pendingWebsites.map((w) => (
                <div key={w.id} className="rounded-md border border-card-border p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">{w.domains.map((d) => d.hostname).join(", ") || w.document_root}</p>
                      <p className="text-xs text-muted-foreground">
                        {w.document_root} · {w.website_type} ({Math.round(w.classification_confidence * 100)}%
                        confidence)
                      </p>
                    </div>
                    <select
                      className="rounded-md border border-card-border bg-background px-2 py-1 text-xs"
                      value={decisions[w.id] ?? "approve"}
                      onChange={(e) =>
                        setDecisions((d) => ({ ...d, [w.id]: e.target.value as "approve" | "exclude" }))
                      }
                    >
                      <option value="approve">Approve</option>
                      <option value="exclude">Exclude</option>
                    </select>
                  </div>
                </div>
              ))}
              <Button onClick={handleSubmitReview} disabled={submitting} className="w-full">
                {submitting ? "Saving..." : "Save and Continue"}
              </Button>
            </div>
          )}

          {step === 5 && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <Check className="h-10 w-10 text-healthy" />
              <p className="text-sm font-medium">Server added and monitoring is active.</p>
              <div className="mt-4 flex gap-2">
                <Button onClick={() => router.push(`/servers/${server?.id}`)}>View Server</Button>
                <Button variant="outline" onClick={() => router.push("/domains")}>
                  View Domain Inventory
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
