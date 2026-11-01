# Vercel Deployment Guide

`apps/web` is a self-contained Next.js app — confirmed by inspection, not assumed: its
`tsconfig.json` only aliases `@/*` to itself, there is no root-level `package.json`,
`pnpm-workspace.yaml`, or Turborepo config anywhere in this monorepo, and it imports nothing from
`packages/shared/python` (that package is Python-only, used only by `services/api` and
`services/worker`). **No shared monorepo package needs to be built or linked for the frontend.**

## Project settings

| Setting | Value |
|---|---|
| Framework Preset | Next.js (auto-detected) |
| **Root Directory** | `apps/web` |
| Build Command | `next build` (default — do not override) |
| Output Directory | `.next` (default — do not override) |
| Install Command | `npm install` (default — `package-lock.json` is present and committed) |
| Node.js Version | 18.x or 20.x (either works; this was built/tested against Node 22 locally, so anything ≥18 is fine) |

## Environment variables

Only one is required:

| Name | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://security-api.yono777hub.com` | The real, already-deployed API domain. Set this for all three Vercel environments (Production, Preview, Development) unless you want previews hitting a different backend. |

Nothing else needs to be set. There is no server-side secret in this app at all — it's a pure
client that talks to the API directly from the browser (see "BFF vs. direct" below). `.gitignore`
already excludes `apps/web/.env*` except `.env.example`, so nothing here risks being committed.

## Private GitHub repository workflow

1. Push this monorepo to a **private** GitHub repository. Confirm `.gitignore` is in effect
   before the first push — `git status` should show no `.env`, no `node_modules/`, no `.next/`,
   no `__pycache__/`. (All already covered by the repo's `.gitignore`.)
2. In Vercel: **Add New Project → Import Git Repository**, select the private repo (Vercel's
   GitHub App needs read access — grant it only to this repository, not all repos, when prompted).
3. Set **Root Directory** to `apps/web` during import (Vercel shows this field before the first
   deploy).
4. Add the `NEXT_PUBLIC_API_URL` environment variable (above) before deploying.
5. Deploy. Vercel will auto-deploy on every push to the default branch, and create a Preview
   deployment for every PR/branch — both get `NEXT_PUBLIC_API_URL` from the env var above unless
   you scope it to Production only.

## After the first deploy: close the loop on CORS

The backend's `CORS_ALLOWED_ORIGINS` is still a placeholder until this point — it cannot be set
correctly before Vercel hands you a real domain. Once deployed:

```bash
# On the VPS:
cd /opt/server-security-center/infra/docker
nano .env   # set CORS_ALLOWED_ORIGINS=https://<your-project>.vercel.app (or your custom domain)
docker compose up -d api
curl -s https://security-api.yono777hub.com/health   # sanity check the API is still up
```

Until this is done, the deployed frontend will load but every API call will fail with a CORS
error in the browser console — that's expected and this is the fix.

## Build validation

Run locally before pushing, exactly as Vercel will:

```bash
cd apps/web
npm install
npm run typecheck
npm run build
```

All three must succeed with zero errors. (Already confirmed clean during this project's earlier
rounds — re-run after any further frontend change, including this one, since nothing in
`apps/web` was touched by this security audit beyond `.env.example`.)

## On the BFF question (Task 2)

This architecture has the browser call the API's domain directly (`fetch(..., {credentials:
"include"})`), with the session cookie set on the **API's** domain rather than Vercel's. That
requires `SameSite=None` (already configured) and is the reason the CSRF-token-in-a-header
pattern exists (`lib/api.ts`'s `cachedCsrfToken`) — a cross-site cookie alone isn't enough CSRF
protection, the header is what closes that gap.

A Next.js **backend-for-frontend** (API routes under `apps/web/app/api/*` proxying every call to
the real backend, with the actual session cookie becoming a first-party cookie between the
browser and Vercel instead) is the more conventional pattern for this exact cross-domain shape,
and would let the cookie go back to `SameSite=Lax` — strictly less to defend. It's a genuinely
larger piece of work: Vercel's serverless functions would need to hold or re-attach the real
backend session somehow (their own encrypted cookie, or a KV-backed session map), which is new
infrastructure, not a port of existing code.

I did not build this. The reasons: no privileged credential is exposed to browser JavaScript
today (the session cookie is `HttpOnly`; the CSRF token is the one thing deliberately readable by
JS, and by itself is useless without that cookie); CSRF is already covered by the header
requirement; and this is a single-owner, non-multi-tenant dashboard, which caps the blast radius
of the remaining theoretical gap. **If you want this hardening anyway, it's a reasonable follow-up
— flag it and it can be scoped as its own piece of work** rather than folded into this audit.
