---
title: Grabbertoullie Backend
emoji: 📚
colorFrom: indigo
colorTo: purple
sdk: gradio
app_file: app.py
pinned: false
---

# Grabbertoullie Backend (Hugging Face Space)

FastAPI backend for Grabbertoullie, packaged to run on a **free CPU Basic**
Space (no Docker SDK, no credit card). It parses book requests, searches
multiple sources in parallel (Anna's Archive, Z-Library, Open Library, Project
Gutenberg, Standard Ebooks, Semantic Scholar), and resolves direct download
links.

`app.py` runs uvicorn on port 7860, installs Chromium into a writable path on
first boot, and starts an Xvfb display for the headed Anna's-download resolver.
System libraries for Chromium come from `packages.txt`.

> This directory is a **build bundle**. `main.py` and the `grabbertoullie/`
> package are copied in from the repo by `deploy.sh` at deploy time — don't edit
> them here; edit the originals under `backend/` and `grabbertoullie/`.

## Configuration (Space → Settings → Variables and secrets)

| Name | Required | Purpose |
|------|----------|---------|
| `GROQ_API_KEY` | optional | Enables Groq (`llama-3.3-70b-versatile`) query parsing. Without it, a built-in fallback parser is used. |
| `ALLOWED_ORIGINS` | recommended | Comma-separated allowed frontend origins for CORS, e.g. `https://your-app.vercel.app`. Defaults to `http://localhost:3001`. |

## Endpoints
- `GET  /healthz` — liveness check.
- `POST /api/chat` — SSE stream: search + ranking + link verification.
- `GET  /api/download?url=…` — SSRF-protected download proxy.
- `GET  /api/annas-download?md5=…` — resolves an Anna's Archive direct URL (headed browser).
