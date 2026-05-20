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
from livekit.plugins import cartesia, deepgram, groq, sarvam
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
        self.session.say(self.greeting_instructions, allow_interruptions=True)

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
    
    # Parse frontend choices from the token metadata (wait for sync if needed)
    metadata_str = participant.metadata
    if not metadata_str:
        logging.info("Participant metadata is empty. Waiting for metadata update...")
        for i in range(10):  # wait up to 1.0 seconds
            await asyncio.sleep(0.1)
            participant = ctx.room.remote_participants.get(participant.identity) or participant
            metadata_str = participant.metadata
            if metadata_str:
                logging.info(f"Metadata sync complete after {i+1} retries: {metadata_str}")
                break
                
    try:
        metadata = json.loads(metadata_str) if metadata_str else {}
    except Exception as e:
        logging.error(f"Failed to parse participant metadata: {e}")
        metadata = {}
        
    personality_name = metadata.get("personality", ACTIVE_PERSONALITY)
    llm_choice = metadata.get("llm", ACTIVE_LLM)
    
    logging.info(f"Dynamic configuration: LLM = {llm_choice}, Personality = {personality_name}")
    
    system_prompt, greeting = get_personality(personality_name)
    
    fnc_ctx = AssistantTools()

    # Select LLM based on user choice (fallback to config)
    if llm_choice == "groq":
        llm_engine = groq.LLM(model="openai/gpt-oss-120b")
    else:
        # Use the inference interface for OpenAI to utilize the LiveKit AI Proxy
        llm_engine = inference.LLM(model="openai/gpt-4o")

    # Initialize nodes separately to hook into their metrics
    stt_engine = deepgram.STTv2(
        model="flux-general-multi",
        language_hint=["hi", "en"],
    )
    tts_engine = cartesia.TTS(
        model="sonic-3-latest",
        language="hi",
        voice="95d51f79-c397-46f9-b49a-23763d3eaa2d",
        sample_rate=24000,
    )

    session = AgentSession(
        # Deepgram STT (Supports streaming and word alignments for Adaptive Interruption)
        stt=stt_engine,
        llm=llm_engine,
        tts=tts_engine,
        vad=silero.VAD.load(
            min_silence_duration=0.3, # 300ms silence detection
            min_speech_duration=0.25, # Ignore short breaths/clicks (250ms)
            activation_threshold=0.6, # Noise-resilient onset threshold
            deactivation_threshold=0.48, # High-threshold to prevent silence-lockup on fan noise
        ),
        # turn_detection=MultilingualModel(),
        turn_handling={
            "interruption": {
                "mode": "adaptive",
                "min_duration": 0.3, # Responsiveness without being overly sensitive to quick breath or noise
                "resume_false_interruption": False,
                "min_words": 1,      # Requires transcribing 1+ words to interrupt (prevents fan noise barge-in)
            },
            "endpointing": {
                "mode": "fixed",
                "min_delay": 0.3, # Reduce endpointing silence delay to 300ms (blazingly fast responses)
            },
            "preemptive_generation": {
                "enabled": True,
                "preemptive_tts": True, # Pre-generate TTS audio for near-zero reply latency
            }
        },
        tools=llm.find_function_tools(fnc_ctx),
    )

    import asyncio
    import json
    
    def _send_metric(metric_type, latency_ms):
        print(f"METRIC COLLECTED: {metric_type} = {latency_ms}ms")
        if ctx.room.local_participant:
            asyncio.create_task(
                ctx.room.local_participant.publish_data(
                    json.dumps({"type": metric_type, "latency": latency_ms}).encode("utf-8"), 
                    topic="agent_metrics"
                )
            )

    @session.on("metrics_collected")
    def on_metrics_collected(event):
        m = event.metrics
        if hasattr(m, "transcription_delay") and m.transcription_delay is not None:
            delay = m.transcription_delay if m.transcription_delay > 0 else getattr(m, "end_of_utterance_delay", 0.0)
            if delay > 0:
                _send_metric("stt", int(delay * 1000))
        if hasattr(m, "ttft") and m.ttft > 0:
            _send_metric("llm", int(m.ttft * 1000))
        if hasattr(m, "ttfb") and m.ttfb > 0:
            _send_metric("tts", int(m.ttfb * 1000))

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
