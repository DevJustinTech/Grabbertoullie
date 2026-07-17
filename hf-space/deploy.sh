#!/usr/bin/env bash
# Deploy the Grabbertoullie backend to a free Hugging Face CPU Basic Space.
#
# Assembles a self-contained bundle from the live source (backend/main.py + the
# grabbertoullie/ package + the hf-space/ files) and force-pushes it to the
# Space repo. Secrets are set via the HF API, not committed.
#
# Usage:
#   export HF_TOKEN=hf_xxx           # access token with WRITE scope
#   export HF_SPACE=YourName/grabbertoullie-backend
#   export GROQ_API_KEY=gsk_xxx      # optional, sets the Space secret
#   export ALLOWED_ORIGINS=https://your-app.vercel.app   # optional
#   bash hf-space/deploy.sh
set -euo pipefail

: "${HF_TOKEN:?Set HF_TOKEN to a write-scoped Hugging Face token}"
: "${HF_SPACE:?Set HF_SPACE to <owner>/<space-name>}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="${HF_SPACE%%/*}"
API="https://huggingface.co/api"

echo "==> Ensuring Space $HF_SPACE exists (gradio SDK)"
curl -sf -X POST "$API/repos/create" \
  -H "Authorization: Bearer $HF_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"space\",\"name\":\"${HF_SPACE#*/}\",\"organization\":\"$OWNER\",\"sdk\":\"gradio\",\"private\":false}" \
  >/dev/null 2>&1 && echo "    created" || echo "    already exists (or create skipped) — continuing"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Assembling bundle in $STAGE"
cp "$REPO_ROOT/hf-space/app.py"          "$STAGE/app.py"
cp "$REPO_ROOT/hf-space/requirements.txt" "$STAGE/requirements.txt"
cp "$REPO_ROOT/hf-space/packages.txt"    "$STAGE/packages.txt"
cp "$REPO_ROOT/hf-space/README.md"       "$STAGE/README.md"
cp "$REPO_ROOT/backend/main.py"          "$STAGE/main.py"
cp -r "$REPO_ROOT/grabbertoullie"        "$STAGE/grabbertoullie"
# Don't ship caches or the editable-install metadata.
find "$STAGE/grabbertoullie" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> Pushing to https://huggingface.co/spaces/$HF_SPACE"
cd "$STAGE"
git init -q
git checkout -q -b main
git add -A
git -c user.name="deploy" -c user.email="deploy@local" commit -qm "Deploy Grabbertoullie backend"
git push -q --force "https://${OWNER}:${HF_TOKEN}@huggingface.co/spaces/${HF_SPACE}" main:main

set_secret() {
  local key="$1" val="$2"
  [ -z "$val" ] && return 0
  echo "==> Setting Space secret $key"
  curl -sf -X POST "$API/spaces/$HF_SPACE/secrets" \
    -H "Authorization: Bearer $HF_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"key\":\"$key\",\"value\":\"$val\"}" >/dev/null \
    && echo "    ok" || echo "    WARN: could not set $key (set it in Space settings)"
}
set_secret GROQ_API_KEY "${GROQ_API_KEY:-}"
set_secret ALLOWED_ORIGINS "${ALLOWED_ORIGINS:-}"

echo "==> Done. Watch the build at https://huggingface.co/spaces/$HF_SPACE"
echo "    API base once running: https://${OWNER}-${HF_SPACE#*/}.hf.space"
