# Grabbertoullie backend — FastAPI + Playwright (Chromium).
#
# Built from the repo root so the image gets both the FastAPI app (backend/)
# and the core engine package (grabbertoullie/), which backend/main.py imports.
# Uses the official Playwright image so Chromium and all of its system
# dependencies are preinstalled and version-matched. Runs the app under Xvfb
# so the Anna's Archive download resolver's *headed* browser has a virtual
# display to render into (headless can't pass Anna's bot challenge).
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app

# xvfb provides the virtual display for the headed browser. It ships with the
# Playwright image, but install it explicitly so the build is self-contained.
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Core engine package. Its dependencies are already pinned in requirements.txt,
# hence --no-deps.
COPY pyproject.toml ./
COPY grabbertoullie/ ./grabbertoullie/
RUN pip install --no-cache-dir --no-deps .

# Ensure the Chromium build matching this Playwright version is present.
RUN python -m playwright install chromium

# Application code
COPY backend/ ./

# The platform injects the port to listen on via $PORT (Cloud Run uses 8080).
ENV PORT=8080
EXPOSE 8080

# Run the API under a virtual framebuffer so the headed browser works.
# Shell form so ${PORT} is expanded at runtime.
CMD xvfb-run -a --server-args="-screen 0 1280x1024x24" \
    uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
