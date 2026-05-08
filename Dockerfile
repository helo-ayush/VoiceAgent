FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by LiveKit
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source code
COPY agent.py .
COPY server.py .
COPY config.py .
COPY utils/ ./utils/

# Pre-download model files (Silero VAD, Turn Detector, etc.) 
# so they are baked into the image and don't fail at runtime.
RUN python agent.py download-files

# Hugging Face Spaces exposes port 7860 by default
ENV PORT=7860

# Expose the port
EXPOSE 7860

# Start both the FastAPI token server and the LiveKit agent
# The token server runs on port 7860 (HF default)
# The agent connects to LiveKit Cloud via WebSocket (no port needed)
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port 7860 & python agent.py start"]
