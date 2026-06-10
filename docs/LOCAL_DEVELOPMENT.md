# Local Development: Setting up LiveKit Locally (Free)

Running the LiveKit server locally allows you to develop and test your Voice Agent completely free of charge, without consuming any LiveKit Cloud API credits.

---

## 💡 How Local Development Works
When running LiveKit in local development mode (`--dev` flags):
- **Server Address:** The server binds locally to `ws://localhost:7880`.
- **Default Dev Credentials:**
  - **API Key:** `devkey`
  - **API Secret:** `secret`
- No internet connection or LiveKit Cloud subscription is needed for WebRTC audio routing. (Note: You will still need your LLM/TTS/STT credentials like OpenAI, Cartesia, and Deepgram in your `.env` to generate transcripts and speech.)

---

## 🛠️ Step-by-Step Setup Guide

### 1. Install & Run LiveKit Server Locally

#### Option A: Using Docker (Recommended)
If you have Docker installed, you can launch the official LiveKit Server container with a single command:
```bash
docker run --rm \
  -p 7880:7880 \
  -p 7881:7881 \
  -p 7882:7882/udp \
  livekit/livekit-server --dev
```

#### Option B: Standalone Binary (Windows / macOS / Linux)
If you do not want to use Docker, you can install the standalone binary:
1. **Windows (via Scoop):**
   ```powershell
   scoop bucket add livekit https://github.com/livekit/scoop-bucket.git
   scoop install livekit-cli livekit-server
   ```
2. **macOS (via Homebrew):**
   ```bash
   brew install livekit/tap/livekit-cli livekit/tap/livekit-server
   ```
3. **Manual Download:** Download the latest release binary from the [LiveKit Github Releases page](https://github.com/livekit/livekit/releases).
4. **Run Server:**
   ```bash
   livekit-server --dev
   ```

---

### 2. Configure Backend Environment Variables (`.env`)
In the root directory of your project, locate or create your `.env` file and configure it to point to your local LiveKit instance:

```env
# Local LiveKit Server Settings (Free dev credentials)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# Voice Agent Engine Keys (Required for AI features)
OPENAI_API_KEY=your_openai_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
SARVAM_API_KEY=your_sarvam_api_key_here
```

---

### 3. Start the FastAPI Token Server
The frontend app retrieves WebRTC access tokens from this server. Run it locally:
```bash
# From the project root
uvicorn server:app --reload --port 8000
```
This launches the token distribution server at `http://localhost:8000`.

---

### 4. Launch the Voice Agent Worker
The agent process handles Speech-to-Text, LLM processing, and text-to-speech generation. Run it in dev-mode:
```bash
# From the project root (ensure your virtual environment is active)
python agent.py dev
```
The worker will automatically connect to your local LiveKit server and wait for participant room requests.

---

### 5. Launch the React Frontend
Now, boot the frontend web application:
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Make sure your local `.env.local` file contains the correct backend URL:
   ```env
   VITE_BACKEND_URL=http://localhost:8000
   ```
3. Install dependencies and start the Vite dev server:
   ```bash
   npm install
   npm run dev
   ```
4. Open `http://localhost:5173` in your browser, select your settings, and click the **Microphone** icon to begin!
