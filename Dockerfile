# ==============================================================================
# BASE IMAGE
# ==============================================================================
# Use official lightweight Python 3.11 slim image as the execution base.
FROM python:3.11-slim

# Set working directory inside the container filesystem.
WORKDIR /app

# ==============================================================================
# DEPENDENCIES STAGE
# ==============================================================================
# Install critical system build libraries (gcc/g++) required to compile C++ wheels
# used by third-party deep learning libraries (like ONNX runtime for Silero VAD).
# Cleans apt cache immediately after compilation to reduce container image bloat.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# PYTHON CACHING LAYER
# ==============================================================================
# Copy and install python dependencies first.
# This maximizes Docker layer caching: rebuilding backend files won't re-trigger pip installs.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# SOURCE COPY STAGE
# ==============================================================================
# Copy individual backend application components into the container working directory.
COPY agent.py .
COPY server.py .
COPY config.py .
COPY utils/ ./utils/

# ==============================================================================
# PRE-DOWNLOAD DEEP LEARNING MODEL CACHE
# ==============================================================================
# Programmatically pre-download deep learning model files (such as Silero VAD weights).
# Without this, the model file would download on the first user call, adding high initial latency.
RUN python -m livekit.agents download-files

# ==============================================================================
# RUNTIME CONFIGURATION
# ==============================================================================
# Default HTTP service port. Exposes port 7860 (Hugging Face Spaces default container port).
ENV PORT=7860
EXPOSE 7860

# ==============================================================================
# MULTI-PROCESS RUNTIME INITIATOR
# ==============================================================================
# Starts both processes concurrently inside the container:
# 1. FastAPI Token Auth Endpoint: Runs on host 0.0.0.0, bound to port 7860 (Uvicorn).
# 2. LiveKit agent background loop: Connects outward to LiveKit Cloud via persistent WebSocket.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port 7860 & python agent.py start"]

