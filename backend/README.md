---
title: Grabbertoullie Backend
emoji: 📚
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 8080
pinned: false
---

# Grabbertoullie Backend

FastAPI backend for Grabbertoullie — parses book requests, searches multiple
sources in parallel (Anna's Archive, Z-Library, Open Library, Project Gutenberg,
Standard Ebooks, Semantic Scholar), and resolves direct download links.

This Space runs as a Docker container (FastAPI + Playwright/Chromium under Xvfb).

## Configuration (Space → Settings → Variables and secrets)

| Name | Required | Purpose |
|------|----------|---------|
| `GROQ_API_KEY` | optional | Enables AI-powered query parsing. Without it, a built-in fallback parser is used. |
| `ALLOWED_ORIGINS` | recommended | Comma-separated list of allowed frontend origins for CORS, e.g. `https://your-app.vercel.app`. Defaults to `http://localhost:3001`. |

## Endpoints
- `POST /api/chat` — Server-Sent Events stream: search + ranking + link verification.
- `GET /api/download?url=…` — SSRF-protected download proxy.
- `GET /api/annas-download?md5=…` — resolves an Anna's Archive direct download URL.
