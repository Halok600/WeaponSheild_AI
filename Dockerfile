# Dockerfile for deploying the WeaponShield AI backend to Hugging Face Spaces
# (Docker SDK) — an alternative to Render with a much larger free RAM tier
# (16GB vs Render's 512MB), which matters since YOLOv8 + torch CPU inference
# is memory-hungry.
#
# HF Spaces expects the container to listen on port 7860 by default.

FROM python:3.10-slim

WORKDIR /app

# opencv-python-headless still needs these shared libs present on a slim
# base image, even though it doesn't need a full X11/GUI stack.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies first (better layer caching)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code and model weights, preserving the relative layout
# backend/config.py expects (PROJECT_ROOT = backend/.., i.e. /app here)
COPY backend/ backend/
COPY model/best.pt model/best.pt

WORKDIR /app/backend

ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
