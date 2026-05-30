"""
Advanced Voice Interruption and Barge-In Controller.

This module configures the WebRTC audio interception layer.
To make a voice assistant feel human, the agent must instantly stop speaking
the millisecond the user makes an utterance.
We configure:
1. **Silero VAD**: Low-latency, high-frequency speech classification.
2. **Turn Handling Settings**: Governs how and when turns are swapped.
3. **Interruptible Agent Activity**: A custom class patch that overrides default
   LiveKit SDK behaviors, ensuring that VAD barge-in is never temporarily disabled
   during initial Text-to-Speech (TTS) buffer delivery.
"""

from __future__ import annotations

import logging
from typing import Any

from livekit.agents import AgentSession, RoomInputOptions
from livekit.agents.voice import agent_activity as _agent_activity_module
from livekit.agents.voice import agent_session as _agent_session_module
from livekit.agents.voice.agent_activity import AgentActivity
from livekit.plugins import noise_cancellation, silero

# Import dynamically tunable settings from config
from config import (
    VAD_MIN_SILENCE_DURATION,
    VAD_MIN_SPEECH_DURATION,
    VAD_ACTIVATION_THRESHOLD,
    AEC_WARMUP_DURATION,
    INTERRUPTION_MIN_SPEECH_DURATION,
    INTERRUPTION_MIN_WORDS,
    ENDPOINTING_MIN_DELAY,
    PREEMPTIVE_GENERATION_ENABLED,
    PREEMPTIVE_TTS_ENABLED,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. VOICE ACTIVITY DETECTION (VAD) PARAMETERS
# ==============================================================================
# VAD options bound to dynamic configurations in config.py
VAD_OPTIONS: dict[str, float] = {
    "min_silence_duration": VAD_MIN_SILENCE_DURATION,
    "min_speech_duration": VAD_MIN_SPEECH_DURATION,
    "activation_threshold": VAD_ACTIVATION_THRESHOLD,
}

# ==============================================================================
# 2. AGENT SESSION TURN HANDLING PARAMETERS
# ==============================================================================
# Interruption options bound to dynamic configurations in config.py
INTERRUPTION_TURN_HANDLING: dict[str, Any] = {
    "interruption": {
        "mode": "vad",
        "enabled": True,
        "min_duration": INTERRUPTION_MIN_SPEECH_DURATION,
        "min_words": INTERRUPTION_MIN_WORDS,
        "discard_audio_if_uninterruptible": False,
        "backchannel_boundary": None,
        "resume_false_interruption": False,
    },
    "endpointing": {
        "min_delay": ENDPOINTING_MIN_DELAY,
    },
    "preemptive_generation": {
        "enabled": PREEMPTIVE_GENERATION_ENABLED,
        "preemptive_tts": PREEMPTIVE_TTS_ENABLED,
    },
}



# ==============================================================================
# 3. INTERRUPTIBLE AGENT ACTIVITY CLASS PATCH
# ==============================================================================
class InterruptibleAgentActivity(AgentActivity):
    """
    SDK Hot Patch: Overrides standard LiveKit AgentActivity speech controls.
    
    By default, the LiveKit SDK temporarily disables VAD barge-in during the initial
    warmup of TTS segments to prevent echo loopbacks. However, in modern setups using
    proper hardware AEC or headset environments, this creates a sluggish, unresponsive
    experience.
    
    We bypass `_disable_vad_interruption_soon` with a no-op to keep barge-in constantly active,
    and override `on_start_of_speech` to instantly trigger overlap interrupts.
    """

    def _disable_vad_interruption_soon(self) -> None:
        """Prevent the SDK from turning off VAD-based barge-in when TTS starts."""
        pass

    def on_start_of_speech(
        self,
        ev,
        *args,
        **kwargs
    ) -> None:
        """
        Triggered when VAD flags user speech while the agent is speaking.
        Calls the superclass methods to synchronize WebRTC events, then executes barge-in.
        """
        super().on_start_of_speech(ev, *args, **kwargs)
        if (
            self._session.agent_state == "speaking"
            and self._current_speech is not None
            and not self._current_speech.interrupted
            and self._current_speech.allow_interruptions
        ):
            # Force enable interruption and stop agent audio playback immediately.
            self._interruption_by_audio_activity_enabled = True
            self._interrupt_by_audio_activity()



_patches_applied = False


def apply_interruption_patches() -> None:
    """
    Applies the class monkeypatch to LiveKit's internal modules.
    Ensures that our custom InterruptibleAgentActivity class is utilized
    whenever AgentSession instantiates conversational flows.
    """
    global _patches_applied
    if _patches_applied:
        return
    _agent_activity_module.AgentActivity = InterruptibleAgentActivity
    _agent_session_module.AgentActivity = InterruptibleAgentActivity
    _patches_applied = True


def load_barge_in_vad() -> silero.VAD:
    """
    Downloads and instantiates the Silero Voice Activity Detector (VAD) model
    pre-configured with our high-responsiveness threshold options.
    """
    return silero.VAD.load(**VAD_OPTIONS)


def get_barge_in_room_input_options() -> RoomInputOptions:
    """
    Configures advanced server-side audio preprocessing.
    We inject LiveKit's Noise Cancellation (NC) filter. This strips out
    ambient environment noise, keyboard typing, and fan hums, feeding
    a clean vocal feed into the VAD processor.
    """
    return RoomInputOptions(noise_cancellation=noise_cancellation.NC())


def try_barge_in(session: AgentSession) -> None:
    """
    Programmatic interruption fallback.
    Stops the agent's playback using the standard SDK audio-activity overlap channel.
    This guarantees that WebRTC state indices and turn structures remain in sync.
    """
    if session.agent_state != "speaking" or session._activity is None:
        return
    activity = session._activity
    current = activity._current_speech
    if current is not None and current.interrupted:
        return
    activity._interruption_by_audio_activity_enabled = True
    try:
        activity._interrupt_by_audio_activity()
    except Exception as e:
        logger.warning("barge-in interrupt failed: %s", e)


def register_barge_in_handlers(session: AgentSession) -> None:
    """
    Sets up event listener callbacks on the LiveKit AgentSession.
    """

    @session.on("user_input_transcribed")
    def _on_user_transcript(ev) -> None:
        """
        Secondary Interruption Path (Transcription-based fallback).
        If the VAD onset missed a quiet utterance, but the Speech-to-Text transcriber
        successfully decodes spoken text, we immediately force an interruption.
        """
        if not ev.is_final and ev.transcript.strip():
            try_barge_in(session)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev) -> None:
        """
        Enforce constant barge-in capability whenever the agent transitions to a speaking state.
        """
        if ev.new_state == "speaking" and session._activity is not None:
            session._activity._interruption_by_audio_activity_enabled = True


# Automatically apply SDK monkeypatches upon import to guarantee load order.
apply_interruption_patches()

