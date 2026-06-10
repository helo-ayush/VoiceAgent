"""
LiveKit Voice Agent Core Worker.

This script boots the voice agent backend process. When the FastAPI server
generates a JWT, the frontend browser connects to a LiveKit Room.
The LiveKit server triggers this background worker, passing a JobContext.
The agent connects to the room, inspects the participant's configuration metadata,
initializes the Speech-to-Text (STT), Large Language Model (LLM), and
Text-to-Speech (TTS) engines, registers voice activity detection, and manages
the conversational turn lifecycle.
"""

from dotenv import load_dotenv
# Load secret API keys from the local environment (e.g. OpenAI, Deepgram, Cartesia, LiveKit URL)
load_dotenv()

import json
import asyncio
import logging

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents import inference
from livekit.plugins import cartesia, groq, deepgram, sarvam
from config import (
    MAX_CONTEXT_ITEMS,
    ACTIVE_LLM,
    ACTIVE_PERSONALITY,
    ACTIVE_STT,
    OPENAI_LLM_MODEL,
    GROQ_LLM_MODEL,
    DEEPGRAM_STT_MODEL,
    DEEPGRAM_STT_LANGUAGE,
    SARVAM_STT_MODEL,
    SARVAM_STT_LANGUAGE,
    SARVAM_STT_MODE,
    GROQ_STT_LANGUAGE,
    TTS_MODEL,
    TTS_LANGUAGE,
    TTS_VOICE_ID,
    TTS_SAMPLE_RATE,
    USER_AWAY_TIMEOUT,
)

logger = logging.getLogger("voice_agent")


# Import internal modular utilities
from utils.prompts import get_personality
from utils.tools import AssistantTools
from utils.interruption import (
    AEC_WARMUP_DURATION,
    INTERRUPTION_TURN_HANDLING,
    get_barge_in_room_input_options,
    load_barge_in_vad,
    register_barge_in_handlers,
)




class Assistant(Agent):
    """
    Custom Voice Assistant Agent.
    Extends the LiveKit Agent class to manage the active voice conversation flow.
    """
    def __init__(self, system_prompt: str, greeting_instructions: str) -> None:
        # Initialize the base Agent class with the dynamic system prompt instructions
        super().__init__(
            instructions=system_prompt,
        )
        # Store the greeting instructions separately to speak them out on connect
        self.greeting_instructions = greeting_instructions

    async def on_enter(self) -> None:
        """
        Lifecycle hook: Called automatically when the agent successfully connects to the room.
        Instead of waiting in silence, the agent proactively triggers an initial reply.
        """
        # generate_reply runs the LLM to output a greeting out loud.
        # allow_interruptions=True allows the user to speak immediately over the greeting.
        self.session.generate_reply(
            instructions=self.greeting_instructions,
            allow_interruptions=True,
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        """
        Lifecycle hook: Called automatically when a single user conversational turn completes.
        Used to prevent context memory leakage and control LLM pricing.
        """
        # Truncate the chat history to the configured maximum context items.
        # This keeps the last 20 messages, automatically preserving the core system prompt.
        turn_ctx.truncate(max_items=MAX_CONTEXT_ITEMS)


async def entrypoint(ctx: JobContext):
    """
    Main job entrypoint. Spawned by LiveKit when a room session is provisioned.
    """
    # 1. Establish the WebRTC connection between the worker process and the LiveKit room
    await ctx.connect()
    
    # 2. Block until the user participant joins the room to start the call
    participant = await ctx.wait_for_participant()

    # 3. Securely extract and parse the user session configuration metadata from the JWT
    try:
        metadata = json.loads(participant.metadata) if participant.metadata else {}
    except Exception:
        # Fallback to empty metadata on parse failure
        metadata = {}

    # Inherit or fallback to config.py defaults
    personality_name = metadata.get("personality", ACTIVE_PERSONALITY)
    llm_choice = metadata.get("llm", ACTIVE_LLM)
    
    # Resolve the requested Speech-to-Text provider with a safe fallback
    requested_stt = metadata.get("stt", ACTIVE_STT)
    stt_choice = requested_stt if requested_stt in {"deepgram", "sarvam", "groq-whisper-v3", "groq-whisper-turbo"} else "deepgram"

    # 4. Load the active system prompt, greeting text, and away prompt based on the chosen personality profile
    system_prompt, greeting, away_instructions = get_personality(personality_name)


    # 5. Initialize the Custom Tools container for LLM function calling
    fnc_ctx = AssistantTools()

    # 6. Dynamically load the LLM Engine based on user selection
    if llm_choice == "groq":
        # Initialize Groq Cloud LLM engine running the specified high-capacity model
        llm_engine = groq.LLM(model=GROQ_LLM_MODEL)
    else:
        # Default to standard OpenAI engine via LiveKit's optimized wrapper
        llm_engine = inference.LLM(model=OPENAI_LLM_MODEL)

    # 7. Dynamically instantiate the requested Speech-to-Text transcriber (Deepgram, Sarvam, or Groq)
    if stt_choice == "sarvam":
        stt_engine = sarvam.STT(
            language=SARVAM_STT_LANGUAGE,
            model=SARVAM_STT_MODEL,
            mode=SARVAM_STT_MODE,
        )
    elif stt_choice == "groq-whisper-v3":
        stt_engine = groq.STT(
            model="whisper-large-v3",
            language=GROQ_STT_LANGUAGE,
        )
    elif stt_choice == "groq-whisper-turbo":
        stt_engine = groq.STT(
            model="whisper-large-v3-turbo",
            language=GROQ_STT_LANGUAGE,
        )
    else:
        stt_engine = deepgram.STT(
            model=DEEPGRAM_STT_MODEL,
            language=DEEPGRAM_STT_LANGUAGE,
        )

    
    # 8. Instantiate Cartesia Text-to-Speech synthesizer
    #    Configured for Hinglish support with dynamic parameters from config.py
    tts_engine = cartesia.TTS(
        model=TTS_MODEL,
        language=TTS_LANGUAGE,
        voice=TTS_VOICE_ID,
        sample_rate=TTS_SAMPLE_RATE,
    )


    # 9. Assemble the AgentSession containing all transcription and speech engines
    session = AgentSession(
        stt=stt_engine,
        llm=llm_engine,
        tts=tts_engine,
        vad=load_barge_in_vad(),                                 # Load high-frequency Silero VAD engine
        aec_warmup_duration=AEC_WARMUP_DURATION,                 # Patch to 0ms for instant initial barge-in
        turn_handling=INTERRUPTION_TURN_HANDLING,                # Inject custom barge-in VAD options
        tools=llm.find_function_tools(fnc_ctx),                  # Register @llm.function_tool decorated methods
        user_away_timeout=USER_AWAY_TIMEOUT,                     # Idle duration before marking user as away
    )

    # 10. Wire custom event handlers for user interruptions (stopping speech immediately on user overlap)
    register_barge_in_handlers(session)

    # 10b. Setup fallback logic for when the user is silent/away for too long
    @session.on("user_state_changed")
    def on_user_state_changed(event):
        if event.new_state == "away":
            logger.info("User away timeout reached. Resetting user state and prompting user in Hinglish.")
            # Transition user state back to listening so that the away timer can trigger again if silent
            session._update_user_state("listening")
            session.generate_reply(
                instructions=away_instructions,
                allow_interruptions=True,
            )


    # 11. Conversational Performance Metrics Tracker
    #     Subscribes to pipeline metrics (STT delay, LLM TTFT, TTS TTFB) and broadcasts
    #     the latency values back to the client UI using a WebRTC Data Channel topic.
    def _send_metric(metric_type, latency_ms):
        print(f"METRIC COLLECTED: {metric_type} = {latency_ms}ms")
        if ctx.room.local_participant:
            # Publish JSON packet over WebRTC data channel asynchronously
            asyncio.create_task(
                ctx.room.local_participant.publish_data(
                    json.dumps({"type": metric_type, "latency": latency_ms}).encode("utf-8"),
                    topic="agent_metrics",
                )
            )

    @session.on("metrics_collected")
    def on_metrics_collected(event):
        m = event.metrics
        # Extract Speech-to-Text processing delay
        if hasattr(m, "transcription_delay") and m.transcription_delay > 0:
            _send_metric("stt", int(m.transcription_delay * 1000))
        # Extract LLM Time-To-First-Token (TTFT)
        elif hasattr(m, "ttft") and m.ttft > 0:
            _send_metric("llm", int(m.ttft * 1000))
        # Extract TTS Time-To-First-Byte (TTFB)
        elif hasattr(m, "ttfb") and m.ttfb > 0:
            _send_metric("tts", int(m.ttfb * 1000))

    # Reference the session back inside the tools container (enables slow background tasks inject replies)
    fnc_ctx.session = session

    # 12. Connect the session and start execution
    await session.start(
        agent=Assistant(system_prompt=system_prompt, greeting_instructions=greeting),
        room=ctx.room,
        room_input_options=get_barge_in_room_input_options(),   # Injects Noise Cancellation filters
    )


# Start the LiveKit agent worker loop via CLI command parser
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )

