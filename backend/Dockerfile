# Grabbertoullie backend — FastAPI + Playwright (Chromium).
#
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
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Ensure the Chromium build matching this Playwright version is present.
RUN python -m playwright install chromium

# Application code
COPY . ./

# Hugging Face Spaces routes external traffic to this port (see README app_port).
ENV PORT=7860
EXPOSE 7860

# Run the API under a virtual framebuffer so the headed browser works.
CMD ["xvfb-run", "-a", "--server-args=-screen 0 1280x1024x24", \
     "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
