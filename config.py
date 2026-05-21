# ╔══════════════════════════════════════════════════════════════════════╗
# ║  AGENT CONFIGURATION                                                 ║
# ║  Defaults used when the frontend does not pass a choice (metadata).  ║
# ╚══════════════════════════════════════════════════════════════════════╝

ACTIVE_PERSONALITY = "neutral"
# Available: "neutral", "savage", "genz"

ACTIVE_LLM = "openai"
# Available: "openai", "groq"

ACTIVE_STT = "deepgram"
# Available: "deepgram", "sarvam"
# Note: STT choice does not affect barge-in (utils/interruption.py uses VAD + events).

MAX_CONTEXT_ITEMS = 20

# --- STT provider settings (agent reads these; not tied to interruption) ---

DEEPGRAM_STT_LANGUAGE = "hi"

SARVAM_STT_MODEL = "saaras:v3"
SARVAM_STT_LANGUAGE = "hi-IN"
SARVAM_STT_MODE = "codemix"  # Hinglish-friendly; requires saaras model
