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
from livekit.plugins import cartesia, deepgram, groq
from config import MAX_CONTEXT_ITEMS, ACTIVE_LLM, ACTIVE_PERSONALITY

# ELEVEN LABS manual REST request method
# from elevenlabs_http_tts import ElevenLabsHttpTTS


from utils.prompts import get_personality
from utils.tools import AssistantTools
import json

class Assistant(Agent):
    def __init__(self, system_prompt: str, greeting_instructions: str) -> None:
        super().__init__(
            instructions=system_prompt,
        )
        self.greeting_instructions = greeting_instructions

    async def on_enter(self) -> None:
        """
        Called the moment the agent joins the room.
        We use this to proactively greet the user so
        they don't have to speak first.
        """
        self.session.generate_reply(
            instructions=self.greeting_instructions
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
    # Connect to the room first so we can read user metadata
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    
    # Parse frontend choices from the token metadata
    try:
        metadata = json.loads(participant.metadata) if participant.metadata else {}
    except Exception:
        metadata = {}
        
    personality_name = metadata.get("personality", ACTIVE_PERSONALITY)
    llm_choice = metadata.get("llm", ACTIVE_LLM)
    
    system_prompt, greeting = get_personality(personality_name)
    
    fnc_ctx = AssistantTools()

    # Select LLM based on user choice (fallback to config)
    if llm_choice == "groq":
        llm_engine = groq.LLM(model="openai/gpt-oss-120b")
    else:
        # Use the inference interface for OpenAI to utilize the LiveKit AI Proxy
        llm_engine = inference.LLM(model="openai/gpt-4o")

    session = AgentSession(
        # Deepgram STT (Streaming - much faster)
        stt=deepgram.STT(
            language="hi",
            model="nova-3",
        ),

        llm=llm_engine,

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
            activation_threshold=0.1, # Extremely sensitive to catch the very first sound
            min_silence_duration=0.3, # Detect end of speech faster
            min_speech_duration=0.01, # React instantly to speech
        ),
        turn_detection=MultilingualModel(),
        min_interruption_duration=0.01,
        min_interruption_words=0, # Interrupt on any VAD activation, don't wait for full words
        tools=llm.find_function_tools(fnc_ctx),
    )

    
    fnc_ctx.session = session

    await session.start(
        agent=Assistant(system_prompt=system_prompt, greeting_instructions=greeting),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
