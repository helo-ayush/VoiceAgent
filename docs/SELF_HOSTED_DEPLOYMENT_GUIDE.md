# Master Guide: Self-Hosting LiveKit (Local & Production Docker)

This master guide provides detailed, step-by-step instructions to run your own self-hosted **LiveKit Server**. 

By self-hosting, you run the WebRTC media server on your own computer or cloud server. **You bypass the LiveKit Cloud platform entirely, which means zero usage charges, no credit limit, and no subscription costs.**

---

## 🏛️ 1. Understanding LiveKit's Architecture

LiveKit works differently than standard HTTP servers. It is a real-time WebRTC media router. To run this system, you need to understand how the parts connect:

* **The React Frontend** runs in the user's browser. It captures microphone audio and sends/receives audio packets.
* **The FastAPI Token Server (`server.py`)** acts as the keymaker. The frontend asks it for a signed room token, which it generates using a secret key.
* **The LiveKit Server** is the central router. Both the frontend and the Python agent connect to it. It routes the audio packets between the user and the agent.
* **The Voice Agent Worker (`agent.py`)** connects to the LiveKit server as a background client, waiting to transcribe user speech, pass it to the LLM brain, and speak back.

---

## 💻 PART 1: Local Development Environment Setup (100% Free)

This section guides you through installing and running the LiveKit Server on your local machine for rapid offline testing.

### Step 1.1: Install the LiveKit Server Binary

You need the `livekit-server` executable on your computer. Choose the appropriate installation method for your operating system:

#### A. Windows Installation Methods (Choose One)

##### Method A: Using Scoop (Recommended)
Scoop is a command-line installer that downloads packages and sets up environment paths automatically.
1. If you don't have Scoop, open PowerShell and install it by running:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   Invoke-RestMethod -Uri https://get.scoop.sh | Initialize-Shell
   ```
2. Once installed, add the LiveKit bucket and install the server:
   ```powershell
   scoop bucket add livekit https://github.com/livekit/scoop-bucket.git
   scoop install livekit-cli livekit-server
   ```

##### Method B: Using Chocolatey
Chocolatey is another Windows package manager. Open an **Administrator PowerShell** and run:
```powershell
choco install livekit-server livekit-cli
```

##### Method C: Manual Download & PATH Configuration (No Package Manager)
If you don't use package managers, you can download and configure it manually:
1. Open your browser and go to [LiveKit Github Releases](https://github.com/livekit/livekit/releases).
2. Download the ZIP file for Windows (e.g. `livekit-server_X.Y.Z_windows_amd64.zip`).
3. Extract the ZIP file. You will see `livekit-server.exe` and `livekit-cli.exe`.
4. Create a folder on your computer to store them (e.g., `C:\LiveKit`). Move both `.exe` files into this folder.
5. **Add the folder to your system PATH:**
   - Search for **"Environment Variables"** in the Windows Start menu.
   - Click **Environment Variables...** at the bottom.
   - Under **System variables**, select the variable named **Path** and click **Edit...**.
   - Click **New** and type your folder path (`C:\LiveKit`).
   - Click **OK** on all windows to save.
   - Open a **new** Command Prompt or PowerShell, type `livekit-server --version`, and press Enter. If it prints the version, it is installed correctly!

---

#### B. macOS Installation
Open your terminal and run:
```bash
brew install livekit/tap/livekit-cli livekit/tap/livekit-server
```

---

#### C. Linux Installation
Open your terminal and run the installation script:
```bash
curl -sSL https://get.livekit.io | bash
```

---

#### D. Running via Docker (Cross-Platform Option)
If you have Docker Desktop running, you can run the server directly without installing binaries:
```bash
docker run --rm -p 7880:7880 -p 7881:7881 -p 7882:7882/udp livekit/livekit-server --dev
```

---

### Step 1.2: Start the Local LiveKit Server
Open a command prompt or terminal window and start the server in development mode:
```bash
livekit-server --dev
```

**What is Dev Mode (`--dev`)?**
Dev mode tells the LiveKit server to:
- Bind HTTP and WebSockets connections to port `7880`.
- Bypass TLS/HTTPS checks (so it runs on unencrypted `ws://` and `http://` which is necessary on localhost).
- Create a default, static API key and secret:
  - **API Key:** `devkey`
  - **API Secret:** `secret`

> [!WARNING]
> Keep this terminal window open! If you close it, your local LiveKit server shuts down.

---

### Step 1.3: Configure the Backend `.env` File
Create or open the file named `.env` in the root directory of your project. We must configure our backend Python scripts to use the local credentials:

```env
# Point to your local LiveKit instance
LIVEKIT_URL=ws://localhost:7880
# Use the static dev API key and secret
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# Active Configurations
ACTIVE_PERSONALITY=neutral
ACTIVE_LLM=openai
ACTIVE_STT=deepgram

# Cognitive APIs (Required for translation, brain, and speech)
OPENAI_API_KEY=your_openai_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

---

### Step 1.4: Run the Backend Services

To run the backend, you must open two new, separate terminal windows.

#### Terminal A: Launch the FastAPI Token Server
This server generates secure JWT WebRTC connection tokens for the client.
1. Open a new terminal window and navigate to the project directory:
   ```bash
   cd "C:\Users\Ayush Kumar\Desktop\Workshop"
   ```
2. Activate your Python virtual environment:
   - **Windows:** `venv\Scripts\activate`
   - **macOS/Linux:** `source venv/bin/activate`
3. Launch the server using Uvicorn:
   ```bash
   uvicorn server:app --reload --port 8000
   ```
   The token service is now running at `http://localhost:8000`.

#### Terminal B: Launch the Voice Agent Worker
This script runs the core audio pipeline and responds to user connections.
1. Open another new terminal window and navigate to the project directory.
2. Activate the virtual environment.
3. Start the worker process:
   ```bash
   python agent.py dev
   ```
   The agent will connect to `ws://localhost:7880` and wait for incoming calls.

---

### Step 1.5: Start the React Frontend

1. Open a fourth terminal window and navigate to the frontend folder:
   ```bash
   cd "C:\Users\Ayush Kumar\Desktop\Workshop\frontend"
   ```
2. Verify that your `.env.local` file contains:
   ```env
   VITE_BACKEND_URL=http://localhost:8000
   ```
3. Install node dependencies (only needed the first time):
   ```bash
   npm install
   ```
4. Start the Vite server:
   ```bash
   npm run dev
   ```
5. Click the link (usually `http://localhost:5173`) to open the app in your browser!

---

## ☁️ PART 2: Production Self-Hosted Deployment (Docker & Cloud VPS)

For production environments, you cannot run in `--dev` mode because HTTP/WS connections are insecure and static keys like `devkey` are vulnerable. You must run the server in a secure, containerized Docker environment with a custom configuration.

### Phase 2.1: How LiveKit Security Keys Work
LiveKit uses HMAC-SHA256 tokens to sign WebRTC permissions. Unlike other APIs, you do not need to register on any third-party portal to obtain credentials. **You can invent any custom key-secret pair yourself.** 

As long as the keys you put in the LiveKit Server config (`livekit.yaml`) match the keys you set in the FastAPI server's `.env`, the system will authenticate connections.

For example, choose a secure key and secret:
- **Your Custom Key:** `my_agent_key_99`
- **Your Custom Secret:** `my_agent_secret_xyz789abc`

---

### Phase 2.2: Create the Production Config File (`livekit.yaml`)
Create a file named `livekit.yaml` on your cloud server. This file configures the server, specifies your custom keys, and sets the UDP port ranges for WebRTC media routing:

```yaml
port: 7880
logging:
  level: info
rtc:
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
keys:
  # Map your custom key to its secret. You can add multiple key-secret pairs here.
  my_agent_key_99: my_agent_secret_xyz789abc
```

---

### Phase 2.3: Configure Firewalls (Open Ports)
WebRTC uses UDP packets for real-time audio streams. If your ports are blocked by a firewall (like AWS Security Groups or Ubuntu UFW), users won't hear any audio.

Open the following ports on your cloud server's firewall:
- **Port 7880 (TCP):** Used for HTTP/WebSockets control signaling (connecting, checking rooms).
- **Ports 50000 to 60000 (UDP):** Used for WebRTC media streams (sending and receiving audio packets).

If using Ubuntu UFW, run:
```bash
sudo ufw allow 7880/tcp
sudo ufw allow 50000:60000/udp
sudo ufw reload
```

---

### Phase 2.4: Deploy LiveKit Server Container
Start the LiveKit Server container in the background, mounting your `livekit.yaml` configuration file:

```bash
docker run -d \
  --name livekit-server \
  --restart unless-stopped \
  -p 7880:7880 \
  -p 50000-60000:50000-60000/udp \
  -v /path/to/livekit.yaml:/livekit.yaml \
  livekit/livekit-server \
  --config /livekit.yaml
```
- `-d`: Runs the container in the background (detached mode).
- `--restart unless-stopped`: Ensures the container restarts automatically if the server reboots.
- `-p 7880:7880`: Forwards the WebSocket control port.
- `-p 50000-60000:50000-60000/udp`: Forwards the UDP WebRTC media ports.
- `-v /path/to/livekit.yaml:/livekit.yaml`: Mounts your config file inside the container.

---

### Phase 2.5: Configure SSL Reverse Proxy (Mandatory)
Browsers **forcefully block** microphone access on insecure connections (`http://` domains). You **must** serve your frontend, FastAPI token endpoint, and LiveKit WebSockets over HTTPS/WSS.

#### Running Caddy for Automatic SSL
The easiest way to get SSL certificates is using **Caddy**, which automatically fetches and renews free Let's Encrypt certificates.

1. Install Caddy on your cloud server.
2. Create a file named `Caddyfile` in your configuration directory:
   ```text
   voice-agent.yourdomain.com {
       reverse_proxy localhost:7880
   }
   ```
3. Restart Caddy. Your LiveKit Server is now securely accessible over the web at `wss://voice-agent.yourdomain.com`.

---

### Phase 2.6: Run the Voice Agent & Token Server on Your VM
Configure your production environment variables to use your secure domains and custom keys:

```env
LIVEKIT_URL=wss://voice-agent.yourdomain.com
LIVEKIT_API_KEY=my_agent_key_99
LIVEKIT_API_SECRET=my_agent_secret_xyz789abc
```

Build and run your custom agent Docker image using the included `Dockerfile` to start the FastAPI server and agent worker concurrently:

```bash
# Build the Docker image
docker build -t voice-agent-production:latest .

# Run the container (exposing FastAPI on port 7860)
docker run -d \
  -p 7860:7860 \
  -e LIVEKIT_URL="wss://voice-agent.yourdomain.com" \
  -e LIVEKIT_API_KEY="my_agent_key_99" \
  -e LIVEKIT_API_SECRET="my_agent_secret_xyz789abc" \
  -e OPENAI_API_KEY="your-openai-key" \
  -e CARTESIA_API_KEY="your-cartesia-key" \
  -e DEEPGRAM_API_KEY="your-deepgram-key" \
  --restart unless-stopped \
  --name voice-agent-instance \
  voice-agent-production:latest
```

This runs:
1. The FastAPI token server at `https://voice-agent.yourdomain.com/getToken` (forwarded via Docker port 7860).
2. The python agent worker process connected outward to the LiveKit server.
