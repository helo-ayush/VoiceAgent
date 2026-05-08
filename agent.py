import logging

from dotenv import load_dotenv
load_dotenv()
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext, 
    RoomInputOptions,
    WorkerOptions,
    cli,
    llm,
)

from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import AgentSession, inference
from livekit.plugins import cartesia, deepgram

# ELEVEN LABS manual REST request method
# from elevenlabs_http_tts import ElevenLabsHttpTTS


from config import ACTIVE_LLM
from utils.prompts import SYSTEM_PROMPT, GREETING_INSTRUCTIONS
from utils.tools import AssistantTools
from livekit.plugins import cartesia, deepgram, openai

# ──────────────────────────────────────────────────────────────────────
# Maximum number of chat messages to keep in context.
# Older messages are automatically trimmed to keep LLM fast and cheap.
# The system prompt is always preserved regardless of this limit.
# ──────────────────────────────────────────────────────────────────────
MAX_CONTEXT_ITEMS = 20

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
        )

    async def on_enter(self) -> None:
        """
        Called the moment the agent joins the room.
        We use this to proactively greet the user so
        they don't have to speak first.
        """
        self.session.generate_reply(
            instructions=GREETING_INSTRUCTIONS
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        """
        Called after the user finishes speaking, before the LLM responds.
        We use this hook to trim old messages from the chat history
        so that long conversations don't bloat the context window.
        
        LiveKit's truncate() is smart:
          - Always preserves the system/developer prompt
          - Removes partial function call leftovers
          - Keeps the most recent N messages
        """
        turn_ctx.truncate(max_items=MAX_CONTEXT_ITEMS)




async def entrypoint(ctx: JobContext):
    fnc_ctx = AssistantTools()

    session = AgentSession(

        # Sarvam STT (direct API — higher latency ~1.1s)
        # stt=sarvam.STT(
        #     language="en-IN",
        #     model="saaras:v3",
        #     mode="transcribe",
        # ),

        # Deepgram STT (Streaming - much faster)
        stt=deepgram.STT(
            language="hi",
            model="nova-3",
        ),

        llm=openai.LLM(
            model="gpt-4o" if ACTIVE_LLM == "openai" else "llama-3.3-70b-versatile",
            base_url="https://api.groq.com/openai/v1" if ACTIVE_LLM == "groq" else None,
            api_key=os.getenv("GROQ_API_KEY") if ACTIVE_LLM == "groq" else os.getenv("OPENAI_API_KEY")
        ),

        # tts=ElevenLabsHttpTTS(
        #     model="eleven_v3",
        #     voice_id="EXAVITQu4vr4xnSDxMaL",
        # ),

        # ElevenLabs TTS via LiveKit inference (great quality, high latency ~2.5s)
        # tts=inference.TTS(
        #     model="elevenlabs/eleven_v3", 
        #     voice="Ms9OTvWb99V6DwRHZn6q",
        # ),

        tts=cartesia.TTS(
            model="sonic-3-latest",
            language="hi",
            voice="95d51f79-c397-46f9-b49a-23763d3eaa2d",
            sample_rate=24000,
        ),

        vad=silero.VAD.load(
            min_silence_duration=0.3, # Detect end of speech faster
            min_speech_duration=0.05, # Extremely sensitive to user barge-in
        ),
        turn_detection=MultilingualModel(),
        tools=llm.find_function_tools(fnc_ctx),
    )

    
    fnc_ctx.session = session

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
