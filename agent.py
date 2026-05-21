import logging
from typing import TYPE_CHECKING

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
from livekit.agents.voice import agent_activity as _agent_activity_module
from livekit.agents.voice import agent_session as _agent_session_module
from livekit.agents.voice.agent_activity import AgentActivity

from livekit.plugins import noise_cancellation, silero
from livekit.agents import inference
from livekit.plugins import cartesia, deepgram, groq
from config import MAX_CONTEXT_ITEMS, ACTIVE_LLM, ACTIVE_PERSONALITY

if TYPE_CHECKING:
    from livekit.agents import vad

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
        self.session.say(self.greeting_instructions, allow_interruptions=True)

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        turn_ctx.truncate(max_items=MAX_CONTEXT_ITEMS)


class InterruptibleAgentActivity(AgentActivity):
    """Prevent the SDK from turning off VAD-based barge-in when TTS starts."""

    def _disable_vad_interruption_soon(self) -> None:
        pass


# Ensure AgentSession instantiates our activity class.
_agent_activity_module.AgentActivity = InterruptibleAgentActivity
_agent_session_module.AgentActivity = InterruptibleAgentActivity


def _try_barge_in(session: AgentSession) -> None:
    """Force-stop agent speech when the user starts talking over the agent."""
    if session.agent_state != "speaking" or session._activity is None:
        return
    activity = session._activity
    current = activity._current_speech
    if current is not None and current.interrupted:
        return
    activity._interruption_by_audio_activity_enabled = True
    try:
        activity.interrupt(force=True)
    except Exception as e:
        logging.warning("barge-in interrupt failed: %s", e)


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    participant = await ctx.wait_for_participant()

    try:
        metadata = json.loads(participant.metadata) if participant.metadata else {}
    except Exception:
        metadata = {}

    personality_name = metadata.get("personality", ACTIVE_PERSONALITY)
    llm_choice = metadata.get("llm", ACTIVE_LLM)

    system_prompt, greeting = get_personality(personality_name)

    fnc_ctx = AssistantTools()

    if llm_choice == "groq":
        llm_engine = groq.LLM(model="openai/gpt-oss-120b")
    else:
        llm_engine = inference.LLM(model="openai/gpt-4o")

    stt_engine = deepgram.STT(language="hi")
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
        vad=silero.VAD.load(
            min_silence_duration=0.3,
            min_speech_duration=0.05,
            activation_threshold=0.35,
        ),
        aec_warmup_duration=0,
        turn_handling={
            "interruption": {
                # VAD-only barge-in — adaptive needs LiveKit inference and can block VAD.
                "mode": "vad",
                "enabled": True,
                "min_duration": 0.05,
                "min_words": 0,
                "discard_audio_if_uninterruptible": False,
                "backchannel_boundary": None,
                "resume_false_interruption": False,
            },
            "endpointing": {
                "min_delay": 0.3,
            },
            "preemptive_generation": {
                "enabled": True,
                "preemptive_tts": True,
            },
        },
        tools=llm.find_function_tools(fnc_ctx),
    )

    @session.on("user_state_changed")
    def _on_user_state_changed(ev) -> None:
        if ev.new_state == "speaking":
            _try_barge_in(session)

    @session.on("user_input_transcribed")
    def _on_user_transcript(ev) -> None:
        if not ev.is_final and ev.transcript.strip():
            _try_barge_in(session)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev) -> None:
        if ev.new_state == "speaking" and session._activity is not None:
            session._activity._interruption_by_audio_activity_enabled = True

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
        room_input_options=RoomInputOptions(
            # NC instead of BVC — BVC can suppress the user's voice during agent speech,
            # which makes barge-in appear completely broken.
            noise_cancellation=noise_cancellation.NC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
