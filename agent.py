from dotenv import load_dotenv
load_dotenv()
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents import inference
from livekit.plugins import cartesia, groq
from config import MAX_CONTEXT_ITEMS, ACTIVE_LLM, ACTIVE_PERSONALITY, ACTIVE_STT

from utils.prompts import get_personality
from utils.stt_factory import create_stt_engine, resolve_stt_provider
from utils.tools import AssistantTools
from utils.interruption import (
    AEC_WARMUP_DURATION,
    INTERRUPTION_TURN_HANDLING,
    get_barge_in_room_input_options,
    load_barge_in_vad,
    register_barge_in_handlers,
)
import json


class Assistant(Agent):
    def __init__(self, system_prompt: str, greeting_instructions: str) -> None:
        super().__init__(
            instructions=system_prompt,
        )
        self.greeting_instructions = greeting_instructions

    async def on_enter(self) -> None:
        # generate_reply runs the LLM; say() would read the instruction text aloud.
        self.session.generate_reply(
            instructions=self.greeting_instructions,
            allow_interruptions=True,
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        turn_ctx.truncate(max_items=MAX_CONTEXT_ITEMS)


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    participant = await ctx.wait_for_participant()

    try:
        metadata = json.loads(participant.metadata) if participant.metadata else {}
    except Exception:
        metadata = {}

    personality_name = metadata.get("personality", ACTIVE_PERSONALITY)
    llm_choice = metadata.get("llm", ACTIVE_LLM)
    stt_choice = resolve_stt_provider(metadata.get("stt", ACTIVE_STT))

    system_prompt, greeting = get_personality(personality_name)

    fnc_ctx = AssistantTools()

    if llm_choice == "groq":
        llm_engine = groq.LLM(model="openai/gpt-oss-120b")
    else:
        llm_engine = inference.LLM(model="openai/gpt-4o")

    stt_engine = create_stt_engine(stt_choice)
    tts_engine = cartesia.TTS(
        model="sonic-3-latest",
        language="hi",  
        voice="95d51f79-c397-46f9-b49a-23763d3eaa2d",
        sample_rate=24000,
    )

    session = AgentSession(
        stt=stt_engine,
        llm=llm_engine,
        tts=tts_engine,
        vad=load_barge_in_vad(),
        aec_warmup_duration=AEC_WARMUP_DURATION,
        turn_handling=INTERRUPTION_TURN_HANDLING,
        tools=llm.find_function_tools(fnc_ctx),
    )

    register_barge_in_handlers(session)

    import asyncio

    def _send_metric(metric_type, latency_ms):
        print(f"METRIC COLLECTED: {metric_type} = {latency_ms}ms")
        if ctx.room.local_participant:
            asyncio.create_task(
                ctx.room.local_participant.publish_data(
                    json.dumps({"type": metric_type, "latency": latency_ms}).encode("utf-8"),
                    topic="agent_metrics",
                )
            )

    @session.on("metrics_collected")
    def on_metrics_collected(event):
        m = event.metrics
        if hasattr(m, "transcription_delay") and m.transcription_delay > 0:
            _send_metric("stt", int(m.transcription_delay * 1000))
        elif hasattr(m, "ttft") and m.ttft > 0:
            _send_metric("llm", int(m.ttft * 1000))
        elif hasattr(m, "ttfb") and m.ttfb > 0:
            _send_metric("tts", int(m.ttfb * 1000))

    fnc_ctx.session = session

    await session.start(
        agent=Assistant(system_prompt=system_prompt, greeting_instructions=greeting),
        room=ctx.room,
        room_input_options=get_barge_in_room_input_options(),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
