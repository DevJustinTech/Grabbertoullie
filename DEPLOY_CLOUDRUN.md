# Deploying Grabbertoullie — Google Cloud Run

Frontend → **Vercel**. Backend → **Google Cloud Run** (Docker container, automatic HTTPS,
no VM/firewall/cert setup). Deploy from your local machine where this repo already lives.

Rough time: ~20–30 min.

---

## Phase 1 — Google Cloud project

1. Go to <https://console.cloud.google.com>, sign in.
2. Create a project (top bar → **New Project**), e.g. `grabbertoullie`.
3. Enable **billing** on it (Billing → link a card). The free tier won't charge for this traffic;
   the card is just required to use Cloud Run.

## Phase 2 — Install the gcloud CLI

- Download the installer: <https://cloud.google.com/sdk/docs/install> (Windows installer is fine).
- Then, in a terminal:
  ```bash
  gcloud auth login
  gcloud config set project YOUR_PROJECT_ID
  ```
  (`YOUR_PROJECT_ID` is shown in the console next to the project name.)

## Phase 3 — Deploy the backend

From the repo root (`Grabbertoullie/`), one command builds the Dockerfile and deploys it:

```bash
gcloud run deploy grabbertoullie \
  --source ./backend \
  --region europe-west1 \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 4 \
  --timeout 600 \
  --allow-unauthenticated \
  --set-env-vars "GROQ_API_KEY=your_groq_key,ALLOWED_ORIGINS=https://YOUR-APP.vercel.app"
```

- The **first** run asks to enable APIs (Cloud Build, Artifact Registry, Run) — answer **y**.
- It uploads `./backend`, builds the container in the cloud (~8–12 min the first time — it pulls
  Chromium), and deploys.
- When done it prints a **Service URL** like `https://grabbertoullie-xxxxxxxx.run.app` — that's your
  backend, with HTTPS already working.
- Don't have the Vercel URL yet? Put a placeholder for `ALLOWED_ORIGINS` and fix it in Phase 5.

Quick check:
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://grabbertoullie-xxxxxxxx.run.app/docs   # expect 200
```

## Phase 4 — Frontend on Vercel

1. <https://vercel.com> → **Add New → Project** → import the `Grabbertoullie` repo.
2. **Root Directory: `frontend`**.
3. **Environment Variable:** `NEXT_PUBLIC_API_URL` = your Cloud Run Service URL.
4. Deploy → you get `https://your-app.vercel.app`.

## Phase 5 — Wire CORS

Point the backend at your real Vercel URL (no trailing slash):
```bash
gcloud run services update grabbertoullie --region europe-west1 \
  --update-env-vars "ALLOWED_ORIGINS=https://your-app.vercel.app"
```
(No rebuild — this just restarts with the new value.)

---

## Verify
- Open the Vercel URL, search `grab Pride and Prejudice epub` → expect a result.
- Logs: `gcloud run services logs read grabbertoullie --region europe-west1` (shows each search's
  `RESULT for ...: SUCCESS/FAIL`).

## Updating later
```bash
# re-run the Phase 3 deploy command; it rebuilds and rolls out a new revision
```

## Tuning / notes
- **Cold start:** the service scales to zero; the first request after idle takes ~10–30s to spin up
  (Chromium is heavy). Subsequent requests are fast.
- **Out-of-memory on Chromium-heavy searches?** raise `--memory 4Gi` and/or lower `--concurrency 1`.
- **Region:** `europe-west3` is Frankfurt (closer if you're in EU/Africa); any region works.
- **Anna's / Z-Library** may be blocked from Cloud Run's datacenter IP (Cloudflare). The free HTTP
  sources always work. If Anna's fails, that's the datacenter-IP reality, not Cloud Run.
