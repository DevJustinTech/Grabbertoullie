"""Hugging Face Space entrypoint (free CPU Basic, non-Docker SDK).

HF runs `python app.py` and expects something listening on port 7860. We run
the FastAPI backend directly with uvicorn. Two Space-specific concerns are
handled here before the app imports anything that launches a browser:

  1. Chromium binary — free Spaces are read-only except /tmp (and $HOME), so we
     point Playwright's browser cache at a writable dir and download Chromium on
     first boot. The system *libraries* it needs come from packages.txt (apt,
     installed as root at build time); only the browser download happens here.

  2. Virtual display — the Anna's Archive slow-download resolver runs a *headed*
     browser to pass the bot challenge, which needs an X display. We start an
     Xvfb display via pyvirtualdisplay so headed Chromium has somewhere to draw.
"""

import os
import subprocess
import sys

PORT = int(os.environ.get("PORT", "7860"))
BROWSERS_PATH = os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/tmp/ms-playwright")


def ensure_chromium() -> None:
    marker = os.path.join(BROWSERS_PATH, ".installed")
    if os.path.exists(marker):
        return
    os.makedirs(BROWSERS_PATH, exist_ok=True)
    # No --with-deps here: that needs root/apt and would fail at runtime. System
    # libs are provided by packages.txt at build time; this only fetches the
    # browser binary, which works as the non-root Space user.
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    open(marker, "w").close()


def start_virtual_display() -> None:
    # Best-effort: headless search works without it; only the headed resolver
    # needs a display. Never let a display failure take down the whole app.
    try:
        from pyvirtualdisplay import Display

        display = Display(visible=0, size=(1280, 1024))
        display.start()
        # Keep a reference so it isn't garbage-collected.
        globals()["_xvfb_display"] = display
    except Exception as exc:  # noqa: BLE001
        print(f"[app] virtual display unavailable, headed resolver may fail: {exc}", flush=True)


ensure_chromium()
start_virtual_display()

import uvicorn  # noqa: E402
from main import app  # noqa: E402  FastAPI instance from the copied backend/main.py

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
