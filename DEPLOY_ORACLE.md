# Deploying Grabbertoullie

Frontend → **Vercel**. Backend → **Oracle Cloud always-free VM** (Docker + Caddy for HTTPS).

The backend runs FastAPI + Playwright/Chromium under Xvfb (headed browser for the
Anna's Archive resolver), so it needs a real VM. Oracle's always-free **Ampere A1**
shape gives up to 4 CPUs / 24 GB RAM at no cost.

Rough time: ~1–2 hours (mostly Oracle account setup + the first Docker build).

---

## Phase 1 — Create the Oracle VM

1. Sign up at <https://www.oracle.com/cloud/free/> (a card is required for identity
   verification; the always-free resources are never charged).
2. Console → **Compute → Instances → Create instance**:
   - **Image:** Canonical **Ubuntu 22.04**
   - **Shape:** Change shape → **Ampere** → **VM.Standard.A1.Flex** →
     set **2 OCPUs** and **12 GB RAM** (well within the free allowance; plenty for Chromium).
   - **Networking:** keep "Assign a public IPv4 address".
   - **SSH keys:** download the private key (or paste your own public key).
3. Create it, then copy the instance's **Public IP address**.
4. SSH in (from your machine):
   ```bash
   ssh -i /path/to/your-key.key ubuntu@YOUR_PUBLIC_IP
   ```

> If the Ampere shape says "out of capacity", try a different Availability Domain
> or retry later — it's a popular free shape. The AMD `VM.Standard.E2.1.Micro`
> works too but only has 1 GB RAM (too little for Chromium).

---

## Phase 2 — Open ports 80 and 443 (this trips everyone up)

Oracle blocks traffic in **two** places. You must open both.

**a) Cloud firewall (Security List):** Console → your instance → **Virtual Cloud Network**
→ **Security Lists** → default list → **Add Ingress Rules**, twice:
- Source `0.0.0.0/0`, IP Protocol TCP, Destination port **80**
- Source `0.0.0.0/0`, IP Protocol TCP, Destination port **443**

**b) The VM's own iptables** (Oracle's Ubuntu image blocks everything but SSH). On the VM:
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo apt-get update && sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```
(If a rule seems ignored, run `sudo iptables -L INPUT --line-numbers` and make sure
the two ACCEPT lines come **before** any REJECT/DROP line.)

---

## Phase 3 — Free HTTPS domain (DuckDNS)

1. Go to <https://www.duckdns.org>, sign in, create a subdomain, e.g. `grabbertoullie`.
2. Set its **current ip** to your VM's public IP and save.
3. Your backend will live at **`https://grabbertoullie.duckdns.org`**
   (use your own subdomain throughout the rest of this guide).

---

## Phase 4 — Install Docker and build the backend

On the VM:
```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Get the code
sudo apt-get install -y git
git clone https://github.com/DevJustinTech/Grabbertoullie.git
cd Grabbertoullie

# Build the backend image (first build ~8-12 min: it pulls Chromium)
sudo docker build -t grabbertoullie .
```

Run the container (replace the two env values):
```bash
sudo docker run -d --name grabbertoullie \
  --restart unless-stopped \
  --shm-size=1g \
  -p 127.0.0.1:7860:7860 \
  -e GROQ_API_KEY="your_groq_api_key" \
  -e ALLOWED_ORIGINS="https://YOUR-APP.vercel.app" \
  grabbertoullie
```
- `-p 127.0.0.1:7860:...` keeps the app private — only Caddy (next phase) can reach it.
- Set `ALLOWED_ORIGINS` to your Vercel URL once you have it (Phase 6); you can update it
  later with `sudo docker rm -f grabbertoullie` and re-running this command.

Check it's alive:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7860/docs   # expect 200
sudo docker logs -f grabbertoullie   # watch startup / search logs
```

---

## Phase 5 — Caddy for automatic HTTPS

Install Caddy:
```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

Point Caddy at the container — write the Caddyfile (use your DuckDNS domain):
```bash
sudo tee /etc/caddy/Caddyfile >/dev/null <<'CADDY'
grabbertoullie.duckdns.org {
    reverse_proxy 127.0.0.1:7860
}
CADDY
sudo systemctl reload caddy
```
Caddy automatically fetches a Let's Encrypt certificate (needs ports 80/443 open — Phase 2).
Verify from your own machine:
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://grabbertoullie.duckdns.org/docs   # expect 200
```

---

## Phase 6 — Frontend on Vercel

1. <https://vercel.com> → **Add New → Project** → import the `Grabbertoullie` repo.
2. **Root Directory: `frontend`** (the Next.js app is not at the repo root).
3. **Environment Variable:**
   `NEXT_PUBLIC_API_URL = https://grabbertoullie.duckdns.org`
4. Deploy. You'll get a URL like `https://your-app.vercel.app`.
5. Back on the VM, make sure the container's `ALLOWED_ORIGINS` matches that exact URL
   (no trailing slash). If you need to change it:
   ```bash
   sudo docker rm -f grabbertoullie
   # re-run the `docker run` command from Phase 4 with the correct ALLOWED_ORIGINS
   ```

---

## Verify end-to-end
- Open your Vercel URL, search `grab Pride and Prejudice epub` → should return a result.
- `sudo docker logs -f grabbertoullie` shows each search's outcome
  (`RESULT for '...': SUCCESS via ... / FAIL`).

## Updating later
```bash
cd ~/Grabbertoullie && git pull
sudo docker build -t grabbertoullie .
sudo docker rm -f grabbertoullie
# re-run the Phase 4 `docker run` command
```

## Notes / expectations
- Free HTTP sources (Gutenberg, Open Library, Standard Ebooks, Semantic Scholar) will work.
- Anna's Archive / Z-Library depend on passing Cloudflare from the VM's datacenter IP —
  they may be flaky. Watch the logs; if the Anna's resolver times out, ping me and I'll
  tune it (fewer partner servers / shorter waits).
- The container auto-restarts on crash/reboot (`--restart unless-stopped`).
