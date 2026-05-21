"""Create STT engines from provider id. Independent of interruption / barge-in."""

from livekit.agents import stt
from livekit.plugins import deepgram, sarvam

from config import (
    ACTIVE_STT,
    DEEPGRAM_STT_LANGUAGE,
    SARVAM_STT_LANGUAGE,
    SARVAM_STT_MODE,
    SARVAM_STT_MODEL,
)

VALID_STT_PROVIDERS = frozenset({"deepgram", "sarvam"})


def resolve_stt_provider(name: str | None) -> str:
    if name in VALID_STT_PROVIDERS:
        return name
    return ACTIVE_STT if ACTIVE_STT in VALID_STT_PROVIDERS else "deepgram"


def create_stt_engine(provider: str | None = None) -> stt.STT:
    choice = resolve_stt_provider(provider)

    if choice == "sarvam":
        return sarvam.STT(
            language=SARVAM_STT_LANGUAGE,
            model=SARVAM_STT_MODEL,
            mode=SARVAM_STT_MODE,
        )

    return deepgram.STT(language=DEEPGRAM_STT_LANGUAGE)


def stt_display_name(provider: str) -> str:
    return "Sarvam" if provider == "sarvam" else "Deepgram"
