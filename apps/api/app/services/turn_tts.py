"""Inline TTS for turn responses — audio bundled with assistant reply."""

from __future__ import annotations

import base64
import logging

from app.schemas.session import TurnResponse
from app.services.gemini import GeminiClient
from app.services.voice import speech_text_for_playback

logger = logging.getLogger(__name__)


def attach_turn_tts(response: TurnResponse) -> TurnResponse:
    """Generate WAV for the spoken reply and embed as base64 on the turn response."""
    shortlist_count = len(response.shortlist or [])
    speech = speech_text_for_playback(response.assistant_text, shortlist_count)
    if not speech:
        return response

    client = GeminiClient()
    if not client.available:
        return response

    try:
        wav_bytes = client.generate_speech(speech)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Inline turn TTS failed: %s", exc)
        return response

    encoded = base64.b64encode(wav_bytes).decode("ascii")
    return response.model_copy(update={"tts_audio_base64": encoded})
