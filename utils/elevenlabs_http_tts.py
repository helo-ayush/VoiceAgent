"""
Custom ElevenLabs TTS plugin that uses the HTTP streaming endpoint
instead of WebSocket multi-stream-input.

This is needed because eleven_v3 does NOT support the WebSocket
streaming endpoint that the default livekit-plugins-elevenlabs uses.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aiohttp

from livekit.agents import tts, utils
from livekit.agents._exceptions import APIConnectionError, APIStatusError, APITimeoutError
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
from livekit.agents.utils import is_given


API_BASE_URL = "https://api.elevenlabs.io/v1"


@dataclass
class _Options:
    api_key: str
    voice_id: str
    model: str
    output_format: str
    language: NotGivenOr[str]


class ElevenLabsHttpTTS(tts.TTS):
    """ElevenLabs TTS using the HTTP streaming endpoint (supports eleven_v3)."""

    def __init__(
        self,
        *,
        voice_id: str = "l7kNoIfnJKPg7779LI2t",
        model: str = "eleven_v3",
        api_key: NotGivenOr[str] = NOT_GIVEN,
        output_format: str = "mp3_22050_32",
        language: NotGivenOr[str] = NOT_GIVEN,
    ) -> None:
        # Parse sample rate from format string (e.g. "mp3_22050_32" -> 22050)
        sample_rate = int(output_format.split("_")[1])

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=sample_rate,
            num_channels=1,
        )

        resolved_key = api_key if is_given(api_key) else os.environ.get("ELEVEN_API_KEY")
        if not resolved_key:
            raise ValueError(
                "ElevenLabs API key is required, either as argument or set ELEVEN_API_KEY env var"
            )

        self._opts = _Options(
            api_key=resolved_key,
            voice_id=voice_id,
            model=model,
            output_format=output_format,
            language=language,
        )
        self._session: aiohttp.ClientSession | None = None

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()
        return self._session

    def synthesize(self, text: str, *, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return _ChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    def stream(self, *, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return _HttpSynthesizeStream(tts=self, conn_options=conn_options)

    async def aclose(self) -> None:
        pass


class _ChunkedStream(tts.ChunkedStream):
    """Single-shot HTTP synthesis."""

    def __init__(self, *, tts: ElevenLabsHttpTTS, input_text: str, conn_options):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        opts = self._tts._opts
        url = (
            f"{API_BASE_URL}/text-to-speech/{opts.voice_id}/stream"
            f"?model_id={opts.model}&output_format={opts.output_format}"
        )

        body: dict = {"text": self._input_text, "model_id": opts.model}
        if is_given(opts.language):
            body["language_code"] = opts.language

        try:
            async with self._tts._ensure_session().post(
                url,
                headers={"xi-api-key": opts.api_key, "Content-Type": "application/json"},
                json=body,
                timeout=aiohttp.ClientTimeout(total=30, sock_connect=self._conn_options.timeout),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise APIStatusError(
                        message=f"ElevenLabs returned {resp.status}: {text}",
                        status_code=resp.status,
                        request_id=None,
                        body=text,
                    )

                output_emitter.initialize(
                    request_id=utils.shortuuid(),
                    sample_rate=self._tts._opts.output_format.split("_")[1],
                    num_channels=1,
                    mime_type="audio/mp3",
                )

                async for data, _ in resp.content.iter_chunks():
                    output_emitter.push(data)

                output_emitter.flush()

        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except aiohttp.ClientResponseError as e:
            raise APIStatusError(
                message=e.message, status_code=e.status, request_id=None, body=None
            ) from e
        except (APIStatusError, APITimeoutError):
            raise
        except Exception as e:
            raise APIConnectionError() from e


class _HttpSynthesizeStream(tts.SynthesizeStream):
    """
    Streaming TTS using the HTTP endpoint.

    Collects text from the input channel, then synthesizes via HTTP streaming.
    This gives us eleven_v3 support while still fitting into the LiveKit agent pipeline.
    """

    def __init__(self, *, tts: ElevenLabsHttpTTS, conn_options):
        super().__init__(tts=tts, conn_options=conn_options)
        self._tts = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        opts = self._tts._opts
        request_id = utils.shortuuid()

        output_emitter.initialize(
            request_id=request_id,
            sample_rate=int(opts.output_format.split("_")[1]),
            num_channels=1,
            stream=True,
            mime_type="audio/mp3",
        )
        output_emitter.start_segment(segment_id=request_id)

        # Collect all text from the input channel
        text_parts: list[str] = []
        async for data in self._input_ch:
            if isinstance(data, self._FlushSentinel):
                continue
            text_parts.append(data)

        full_text = "".join(text_parts).strip()
        if not full_text:
            output_emitter.end_segment()
            return

        self._mark_started()

        url = (
            f"{API_BASE_URL}/text-to-speech/{opts.voice_id}/stream"
            f"?model_id={opts.model}&output_format={opts.output_format}"
        )

        body: dict = {"text": full_text, "model_id": opts.model}
        if is_given(opts.language):
            body["language_code"] = opts.language

        try:
            async with self._tts._ensure_session().post(
                url,
                headers={"xi-api-key": opts.api_key, "Content-Type": "application/json"},
                json=body,
                timeout=aiohttp.ClientTimeout(total=30, sock_connect=self._conn_options.timeout),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    raise APIStatusError(
                        message=f"ElevenLabs returned {resp.status}: {err_text}",
                        status_code=resp.status,
                        request_id=None,
                        body=err_text,
                    )

                async for data, _ in resp.content.iter_chunks():
                    output_emitter.push(data)

        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except (APIStatusError, APITimeoutError):
            raise
        except Exception as e:
            raise APIConnectionError(f"could not connect to ElevenLabs: {e}") from e
        finally:
            output_emitter.end_segment()
