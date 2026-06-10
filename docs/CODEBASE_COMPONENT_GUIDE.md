# Voice Agent Backend Component Guide

This guide details the internal Python backend architecture of **VoiceAgent**, documenting the design patterns and structures of each core file.

---

## 📂 Codebase Tree

```
Workshop/
├── config.py              # Centralized defaults and pipeline preferences
├── server.py             # FastAPI token distribution server
├── agent.py              # Main LiveKit worker script
├── Dockerfile            # Optimized compilation instruction set
├── requirements.txt      # Python dependencies list
└── utils/
    ├── prompts.py        # System prompt personalities and Hinglish instructions
    ├── interruption.py   # Silero VAD configurations and AEC warmup monkeypatch
    └── tools.py          # LLM function calling tools (sync vs async pattern)

```

---

## ⚙️ 1. Configurations (`config.py`)

Handles dynamic and fallback configuration keys. Enables switching between multiple model vendors and prompt styles.

### Component Logic & Examples
* **Active Personalities**: Dictates the primary prompt instruction loaded from `utils/prompts.py` (`"neutral" | "savage" | "genz"`).
* **Vendor Selection**: Allows developers to switch STT engines (`"deepgram"`, `"sarvam"`, `"groq-whisper-v3"`, or `"groq-whisper-turbo"`) and LLM instances (`"openai"` or `"groq"`) instantly.
* **Context Trimming Limits**: Configures `MAX_CONTEXT_ITEMS = 20`. This ensures that only the last 20 messages are maintained in the chat history, automatically dropping earlier cycles to optimize both API latency and billing costs.

---

## 🔐 2. FastAPI Token Server (`server.py`)

A light REST API hosting Uvicorn. Interacts with frontends to allocate separate room channels for individual callers.

### Core Architecture Flow
1. **Request Received**: The client contacts `/getToken?personality=savage&llm=openai`.
2. **Room Allocation**: Instantiates a unique UUID room identifier (`room-user-xxxxxx`).
3. **Session Parameter Isolation**: Encodes the dynamic selections into participant metadata using a serialized JSON string.
4. **JWT Signing**: Signs the token using secret credentials (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`), granting precise WebRTC access to the allocated room.

```python
# JWT Creation snippet from server.py
metadata = json.dumps({"personality": personality, "llm": llm, "stt": stt})
token = AccessToken(api_key, api_secret).with_identity(participant_identity) \
                                        .with_name("Human") \
                                        .with_metadata(metadata) \
                                        .with_grants(VideoGrants(room_join=True, room=room_name))
```

---

## 🤖 3. LiveKit Core Worker (`agent.py`)

The heartbeat process. Connects to LiveKit Cloud, listens to WebRTC rooms, manages LLM cognitive state transitions, and streams audio data.

### Key Logic Handlers
- **Entrypoint Routing**: Connects to the room, waits for the user, and extracts JWT metadata to set up the session:
  ```python
  metadata = json.loads(participant.metadata) if participant.metadata else {}
  personality_name = metadata.get("personality", ACTIVE_PERSONALITY)
  llm_choice = metadata.get("llm", ACTIVE_LLM)
  ```
- **Cartesia TTS Initialization**: Connects to Cartesia's Sonic 3 models at 24kHz using Hindi locales and premium voices.
- **Latency Data Channel Broadcast**: Hooks into the `"metrics_collected"` event to extract STT, LLM (TTFT), and TTS (TTFB) latency statistics. It broadcasts these values back to the client over a WebRTC data channel:
  ```python
  @session.on("metrics_collected")
  def on_metrics_collected(event):
      # Broadcasts latencies dynamically to the user interface
      _send_metric("llm", int(event.metrics.ttft * 1000))
  ```

---

## 🧠 4. Prompt Personalities (`utils/prompts.py`)

Defines system prompts, Hinglish rules, and emotion control tags.

### Standard System Prompts & SSML Emotion Tags
Cartesia TTS supports XML emotional markers. When GPT-4o emits emotional brackets, the TTS engine dynamically modulates the voice's pitch and timbre.
* **Shared Conversational Constraints**:
  - Requires casual Indian **Hinglish** (Hindi words in Devanagari script, English words in standard characters).
  - Enforces brevity (maximum **2-3 sentences** per turn) for immediate playback.
* **Personality Profiles**:
  - `"neutral"`: Helpful, warm, and cheekily friendly friend profile.
  - `"savage"`: Brutally honest roaster buddy (*"tujhse na ho payega, chal ruk"* style).
  - `"genz"`: Hype-filled internet kid using heavy slang (*"no cap", "bruh that's an L moment"*).

---

## ⚡ 5. Voice Interruption & AEC Warmup (`utils/interruption.py`)

Manages low-level audio engineering details, configuring VAD levels and applying SDK hot-patches.

### Custom Interruption Hot-Patch Detail
By default, the LiveKit SDK temporarily disables VAD barge-in during the initial startup of TTS buffers to prevent echo loopbacks. We patch `_disable_vad_interruption_soon` with a no-op to bypass this limitation. This ensures the agent stops speaking immediately when interrupted by the user, even during its first sentence.

```python
class InterruptibleAgentActivity(AgentActivity):
    def _disable_vad_interruption_soon(self) -> None:
        # Keep VAD active at all times, ignoring the default SDK block.
        pass

    def on_start_of_speech(self, ev, speech_start_time: float) -> None:
        super().on_start_of_speech(ev, speech_start_time)
        if self._session.agent_state == "speaking" and self._current_speech:
            # Force barge-in
            self._interruption_by_audio_activity_enabled = True
            self._interrupt_by_audio_activity()
```

---

## 🔧 6. Cognitive LLM Action Tools (`utils/tools.py`)

Exposes tool definitions to GPT-4o. Features two architectural design patterns.

### Option A: Fast Synchronous Tools
For quick calculations or database queries (under 2 seconds). The LLM blocks, executes the call, and continues speaking.
```python
@llm.function_tool(description="Check the weather for a given city")
async def get_weather(self, location: str):
    await asyncio.sleep(1) # Fast API simulation
    return f"The weather in {location} is 25 degrees."
```

### Option B: Decoupled Async Background Tools (Slow Tools)
For heavy operations (scraping, AI models, queries taking >3 seconds). The tool starts a background worker task and returns a quick status report instantly. The agent tells the user *"I'm looking into that,"* and continues chatting. Once the background worker completes, it injects a simulated message to update the user automatically.
```python
@llm.function_tool(description="Run a complex background task to analyze a dataset")
async def analyze_dataset(self, dataset_name: str):
    # 1. Spawn background worker
    asyncio.create_task(self._background_analysis(dataset_name))
    # 2. Return instantly to keep agent speaking
    return f"Task started for {dataset_name}. Tell the user you will let them know when it's done."

async def _background_analysis(self, dataset_name: str):
    await asyncio.sleep(10) # 10 seconds of heavy calculation
    if self.session:
        # 3. Inject message to update the user automatically
        message = llm.ChatMessage(
            role="user",
            content=[f"[SYSTEM NOTIFICATION]: The background task for '{dataset_name}' has finished. Please inform me of the result."]
        )
        self.session.generate_reply(user_input=message)
```
