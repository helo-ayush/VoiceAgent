# ==============================================================================
# 1. CORE SELECTIONS
# ==============================================================================
ACTIVE_PERSONALITY = "neutral"          # Selected voice agent persona profile: "neutral" | "savage" | "genz"
ACTIVE_LLM = "openai"                  # LLM vendor option: "openai" | "groq"
ACTIVE_STT = "deepgram"                # Speech-To-Text vendor option: "deepgram" | "sarvam"
MAX_CONTEXT_ITEMS = 20                 # Maximum chat history turns kept in memory to manage billing and latency

# ==============================================================================
# 2. VOICE ACTIVITY DETECTION (VAD) & ECHO CONTROL
# ==============================================================================
VAD_MIN_SILENCE_DURATION = 0.3          # Silence gap (in seconds) required to flag a user turn boundary
VAD_MIN_SPEECH_DURATION = 0.05          # Minimal voice duration (in seconds) recognized as valid user speech
VAD_ACTIVATION_THRESHOLD = 0.35         # Classification confidence threshold above which speech is registered
AEC_WARMUP_DURATION = 0.10              # Connection warmup block window (in seconds) during which VAD is ignored

# ==============================================================================
# 3. INTERRUPTION & TURN TIMINGS
# ==============================================================================
INTERRUPTION_MIN_SPEECH_DURATION = 0.05 # Minimum overlap duration (in seconds) before agent stops playing audio
INTERRUPTION_MIN_WORDS = 0              # Minimum words transcribing before registering a user interruption
ENDPOINTING_MIN_DELAY = 0.3             # Delay window (in seconds) from user silence to calling the LLM
PREEMPTIVE_GENERATION_ENABLED = True    # Begins LLM generation before the user fully stops speaking
PREEMPTIVE_TTS_ENABLED = True           # Begins TTS audio buffer calculations during active LLM token emission
USER_AWAY_TIMEOUT = 10.0                # Idle duration (in seconds) of user silence before triggering the fallback prompt


# ==============================================================================
# 4. LARGE LANGUAGE MODELS (LLM)
# ==============================================================================
OPENAI_LLM_MODEL = "openai/gpt-4o"       # OpenAI model used for context parsing and emotional intelligence
GROQ_LLM_MODEL = "openai/gpt-oss-120b"   # Groq engine model utilized for fast open-source inference

# ==============================================================================
# 5. SPEECH-TO-TEXT (STT) ENGINE PARAMS
# ==============================================================================
# --- Deepgram Nova-3 ---
DEEPGRAM_STT_MODEL = "nova-3"           # Deepgram model version used for transcription
DEEPGRAM_STT_LANGUAGE = "hi"            # Target ISO locale set on Deepgram for Hindi/Hinglish phonetics

# --- Sarvam AI ---
SARVAM_STT_MODEL = "saaras:v3"          # Sarvam AI model version used for native Hinglish speech
SARVAM_STT_LANGUAGE = "hi-IN"           # Primary language setting assigned to the Sarvam engine
SARVAM_STT_MODE = "codemix"             # Specialized Hinglish-friendly mode combining Hindi and English

# --- Groq Whisper ---
GROQ_STT_LANGUAGE = "en"                # Target language setting for Groq Whisper transcription

# ==============================================================================
# 6. TEXT-TO-SPEECH (TTS) ENGINE PARAMS
# ==============================================================================
TTS_MODEL = "sonic-3-latest"            # Cartesia TTS sound generator model
TTS_LANGUAGE = "hi"                     # Output locale utilized by the TTS generator
TTS_VOICE_ID = "95d51f79-c397-46f9-b49a-23763d3eaa2d" # Premium custom voice identifier profile
TTS_SAMPLE_RATE = 24000                 # Sample rate of outbound audio stream in Hertz
