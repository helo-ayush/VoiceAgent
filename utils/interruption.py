"""
Barge-in / interruption handling for the LiveKit voice agent.

Tuning guide:
  - VAD_OPTIONS: how quickly user speech is detected
  - INTERRUPTION_TURN_HANDLING: SDK turn/interrupt settings
  - try_barge_in / register_barge_in_handlers: force-stop agent audio on overlap
"""

from __future__ import annotations

import logging
from typing import Any

from livekit.agents import AgentSession, RoomInputOptions
from livekit.agents.voice import agent_activity as _agent_activity_module
from livekit.agents.voice import agent_session as _agent_session_module
from livekit.agents.voice.agent_activity import AgentActivity
from livekit.plugins import noise_cancellation, silero

logger = logging.getLogger(__name__)

# --- VAD (voice activity detection for barge-in) ---

VAD_OPTIONS: dict[str, float] = {
    "min_silence_duration": 0.3,
    "min_speech_duration": 0.05,
    "activation_threshold": 0.35,
}

# --- AgentSession turn_handling slice for interruptions ---

INTERRUPTION_TURN_HANDLING: dict[str, Any] = {
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
}

# Disable the default 3s AEC warmup that blocks interrupts on the first agent turn.
AEC_WARMUP_DURATION = 0


class InterruptibleAgentActivity(AgentActivity):
    """Prevent the SDK from turning off VAD-based barge-in when TTS starts."""

    def _disable_vad_interruption_soon(self) -> None:
        pass


_patches_applied = False


def apply_interruption_patches() -> None:
    """Use InterruptibleAgentActivity when AgentSession creates activities."""
    global _patches_applied
    if _patches_applied:
        return
    _agent_activity_module.AgentActivity = InterruptibleAgentActivity
    _agent_session_module.AgentActivity = InterruptibleAgentActivity
    _patches_applied = True


def load_barge_in_vad() -> silero.VAD:
    return silero.VAD.load(**VAD_OPTIONS)


def get_barge_in_room_input_options() -> RoomInputOptions:
    # NC instead of BVC — BVC can suppress the user's voice during agent speech.
    return RoomInputOptions(noise_cancellation=noise_cancellation.NC())


def try_barge_in(session: AgentSession) -> None:
    """Force-stop agent speech when the user talks over the agent."""
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
        logger.warning("barge-in interrupt failed: %s", e)


def register_barge_in_handlers(session: AgentSession) -> None:
    """Wire session events that trigger immediate barge-in."""

    @session.on("user_state_changed")
    def _on_user_state_changed(ev) -> None:
        if ev.new_state == "speaking":
            try_barge_in(session)

    @session.on("user_input_transcribed")
    def _on_user_transcript(ev) -> None:
        if not ev.is_final and ev.transcript.strip():
            try_barge_in(session)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev) -> None:
        if ev.new_state == "speaking" and session._activity is not None:
            session._activity._interruption_by_audio_activity_enabled = True


# Apply SDK patches on import so agent.py only needs to import this module.
apply_interruption_patches()
