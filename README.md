---
title: Voice Agent
emoji: 🎙️
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# 🎙️ Voice Agent: Multi-Personality Conversational AI

An interactive, ultra-low-latency voice assistant utilizing **LiveKit** (WebRTC), **FastAPI**, and **React**. 

The agent features multiple personality profiles (Neutral, Sarcastic Roaster, Gen-Z Slang), emotional expression matching via inline XML emotion tagging, and real-time frontend latency metric visualization.

---

## 🚀 Architectural Readiness: Local Dev vs. Production

This repository is structured to be **100% production-ready** while offering a completely **free and offline local development path**. Switching between them requires zero code changes; you only swap your credentials in the environment configuration (`.env`).

### 💻 Local Development (100% Free)
You can run the entire pipeline locally without registering for a LiveKit Cloud account or spending any API credits. 
- The system connects to a local, self-hosted **LiveKit Server** running in developer mode.
- Local tokens are cryptographically signed using static dev credentials (`devkey` / `secret`) that the local server automatically trusts.
- Detailed step-by-step instructions on installing LiveKit on Windows/macOS/Linux and running it locally are in:
  👉 **[docs/LOCAL_DEVELOPMENT.md](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/LOCAL_DEVELOPMENT.md)**

### ☁️ Production Deployment (Scale & Cloud)
The system is built to scale enterprise-wide:
- **Zero Code Modifications:** Change your `.env` to point to a production-managed **LiveKit Cloud** cluster or a production VM cluster, and the codebase immediately functions in production mode.
- **Stateless Token Service:** The FastAPI endpoint can be deployed in container engines (AWS Fargate, Google Cloud Run, or Hugging Face Spaces) and scales horizontally behind load balancers.
- **Stateful Worker Scaling:** The Python worker runs in background job mode. You can spin up multiple agent workers, and the LiveKit server will automatically route incoming user calls (jobs) to the next available worker.
- Complete containerization blueprints and cloud architectures are in:
  👉 **[docs/PRODUCTION_DEPLOYMENT.md](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/PRODUCTION_DEPLOYMENT.md)**

---

## 📚 Documentation Map

For in-depth details, refer to the dedicated guides inside the `docs/` folder:

* 📖 **[System Architecture Guide](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/README_ARCHITECTURE.md):** Architectural diagrams and the end-to-end lifecycle of audio data.
* 📖 **[Local Development Master Guide](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/LOCAL_DEVELOPMENT.md):** Complete setup guide to run the server locally for free.
* 📖 **[Production Deployment Blueprint](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/PRODUCTION_DEPLOYMENT.md):** Operational guide for Docker, AWS, Google Cloud, and Hugging Face.
* 📖 **[Frontend Integration Details](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/FRONTEND_INTEGRATION.md):** Information on connections, latency charts, and noise cancellation.
* 📖 **[Custom Agent Tool Calling](file:///c:/Users/Ayush Kumar/Desktop/Workshop/docs/TOOL_CALLING_GUIDE.md):** Instructions on adding custom Python tools for the assistant to run during calls.

---

## ⚡ Quick Start: Running Locally

Here is a quick checklist of the commands to start development. Ensure your `.env` file is set up with your AI cognitive service keys (OpenAI, Cartesia, Deepgram).

1. **Start the LiveKit Server:**
   ```bash
   livekit-server --dev
   ```
2. **Start the FastAPI Token Server:**
   ```bash
   # From root directory
   uvicorn server:app --reload --port 8000
   ```
3. **Start the Voice Agent Worker:**
   ```bash
   # From root directory (with virtual env active)
   python agent.py dev
   ```
4. **Start the React Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.
