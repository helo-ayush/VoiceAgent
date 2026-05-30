# Voice Agent Production Deployment Blueprint

This guide provides the operational blueprint for containerizing, configuring, and deploying the **VoiceAgent** system to production-grade cloud environments.

---

## 🔑 1. Environment Secrets Matrix

Before deploying, ensure that the following environment variables are securely provisioned inside your target container environment (e.g. AWS Parameter Store, GCP Secret Manager, or Hugging Face Spaces Secret Console):

| Variable Name | Required | Provider / Role | Example Value |
|---------------|----------|-----------------|---------------|
| `LIVEKIT_URL` | **Yes** | LiveKit WebRTC Host URL | `wss://voice-agent-xxxx.livekit.cloud` |
| `LIVEKIT_API_KEY` | **Yes** | LiveKit Connection Key | `APIxxXXXXXXXXXX` |
| `LIVEKIT_API_SECRET` | **Yes** | LiveKit JWT Signature Key | `abcdefghijklmnopqrstuvwxy123456` |
| `OPENAI_API_KEY` | **Yes** | OpenAI GPT-4o Brain Inference | `sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx` |
| `CARTESIA_API_KEY` | **Yes** | Cartesia Sonic-3 TTS Synthesis | `car_xxxxxxxxxxxxxxxxxxxxxxxxx` |
| `DEEPGRAM_API_KEY` | **Yes** | Deepgram STT Nova-3 Transcriber | `dg_xxxxxxxxxxxxxxxxxxxxxxxxx` |
| `GROQ_API_KEY` | No | Optional Groq LLM API Key | `gsk_xxxxxxxxxxxxxxxxxxxxxxxxx` |
| `SARVAM_API_KEY` | No | Optional Sarvam AI Hinglish STT | `srv_xxxxxxxxxxxxxxxxxxxxxxxxx` |

---

## 🐳 2. Container Operations & Run Commands

The provided `Dockerfile` compiles the required build libraries, pre-downloads the Silero VAD neural models to prevent cold-start latencies, and exposes both the FastAPI server and the LiveKit agent worker concurrently under port `7860`.

### Build Image
```bash
docker build -t voice-agent-production:latest .
```

### Run Image Locally (For Testing)
Substitute active credential keys in the command below:
```bash
docker run -d \
  -p 7860:7860 \
  -e LIVEKIT_URL="wss://your-livekit.livekit.cloud" \
  -e LIVEKIT_API_KEY="your-key" \
  -e LIVEKIT_API_SECRET="your-secret" \
  -e OPENAI_API_KEY="your-openai-key" \
  -e CARTESIA_API_KEY="your-cartesia-key" \
  -e DEEPGRAM_API_KEY="your-deepgram-key" \
  --name voice-agent-instance \
  voice-agent-production:latest
```

---

## ☁️ 3. Cloud Target Architectures

### Target A: Hugging Face Spaces (Quickest Deploy)
Hugging Face Spaces natively supports running single Docker containers exposing port `7860` over HTTPS.
1. Create a new **Space** on Hugging Face.
2. Select **Docker** as the Space SDK (Blank template).
3. Under the **Space Settings**, add all secret variables from the Secrets Matrix above.
4. Git push the repository files directly to the Hugging Face Git remote.
5. The container will automatically build, pre-download models, launch the token endpoint on HTTPS, and spin up the LiveKit worker.

### Target B: AWS ECS or Google Cloud Run (Enterprise-Scale)
For scalable cloud infrastructure:
1. Push the compiled image to **AWS ECR** or **GCP Artifact Registry**.
2. **FastAPI Scaling**: Deploy the token server container to **Google Cloud Run** or **AWS Fargate** behind an Application Load Balancer with CPU/Memory metrics-based scaling rules.
3. **LiveKit Agent Scaling**: Deploy the agent worker to a stateful EC2 or GCE cluster. 
   - *Important*: While the FastAPI token server is stateless, the LiveKit agent worker requires a persistent connection.
   - It is highly recommended to configure LiveKit's **Queue Mode** or **Load Balancer** to spin up separate container nodes for active calls, rather than packing multiple conversations onto a single worker thread.

---

## 🔒 4. SSL & WebRTC Policy Requirements

> [!WARNING]
> **Production HTTPS Enforcements:**
> - Modern client browsers **forcefully block microphone access (`navigator.mediaDevices.getUserMedia`)** on insecure HTTP domains.
> - Microphone capture is only allowed on `localhost` (for developers) and secure `https://` production environments.
> - Ensure your token server API and frontend Vite deployment are served behind SSL/TLS endpoints (HTTPS / WSS). Use Let's Encrypt, Cloudflare proxy, or AWS ACM to secure your domains.
