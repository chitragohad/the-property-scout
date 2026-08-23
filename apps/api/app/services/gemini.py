"""Google Gemini client wrapper with offline/heuristic fallback."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.config import get_settings
from app.services.voice import is_pcm_mime, normalize_gemini_voice, parse_pcm_sample_rate, pcm_to_wav

logger = logging.getLogger(__name__)


class GeminiClient:
    """Thin wrapper around google-genai. Falls back when key/SDK missing."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.gemini_api_key) or ""
        self.model = model or settings.llm_model
        self._client = None
        if self.api_key:
            try:
                from google import genai  # type: ignore

                self._client = genai.Client(api_key=self.api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini SDK unavailable: %s", exc)
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        if not self._client:
            raise RuntimeError("Gemini client not configured")
        from google.genai import types  # type: ignore

        settings = get_settings()
        contents = prompt if system is None else f"{system}\n\n{prompt}"
        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=settings.llm_temperature,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            # google-genai sometimes nests candidates
            text = str(response)
        return text.strip()

    def generate_speech(self, text: str) -> bytes:
        """Single-speaker WAV via Gemini TTS (consistent voice, no chunk seams)."""
        if not self._client:
            raise RuntimeError("Gemini client not configured")
        from google.genai import types  # type: ignore

        settings = get_settings()
        voice_name = normalize_gemini_voice(settings.gemini_voice)
        # Light style cue improves pacing without changing content.
        spoken = text.strip()
        if spoken and not spoken.lower().startswith("say "):
            spoken = (
                "Speak naturally and clearly at a calm conversational pace, "
                "with smooth phrasing and no robotic pauses:\n\n"
                f"{spoken}"
            )
        last_error: Exception | None = None

        for attempt in range(4):
            try:
                response = self._client.models.generate_content(
                    model=settings.gemini_tts_model,
                    contents=spoken,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            language_code="en-IN",
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name,
                                ),
                            ),
                        ),
                    ),
                )
                audio = self._extract_tts_audio(response)
                if audio:
                    return audio
                raise RuntimeError("Gemini TTS returned no audio data")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < 3 and self._is_rate_limited(exc):
                    delay = max(self._retry_delay_seconds(exc, default=3.0), 2.0 * (attempt + 1))
                    logger.warning("Gemini TTS rate limited; retrying in %.1fs", delay)
                    time.sleep(delay)
                    continue
                raise

        assert last_error is not None
        raise last_error

    @staticmethod
    def _extract_tts_audio(response: Any) -> bytes | None:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if not inline or not getattr(inline, "data", None):
                    continue
                data = inline.data
                mime = (getattr(inline, "mime_type", None) or "").lower()
                if mime in {"audio/wav", "audio/x-wav", "audio/wave"}:
                    return data
                if is_pcm_mime(mime):
                    return pcm_to_wav(data, rate=parse_pcm_sample_rate(mime))
        return None

    @staticmethod
    def _is_rate_limited(exc: Exception) -> bool:
        message = str(exc).lower()
        return "429" in message or "resource_exhausted" in message or "quota" in message

    @staticmethod
    def _retry_delay_seconds(exc: Exception, *, default: float = 2.0) -> float:
        match = re.search(r"retry in ([0-9.]+)s", str(exc), flags=re.IGNORECASE)
        if match:
            return min(float(match.group(1)) + 0.5, 15.0)
        return default

    def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        raw = self.generate_text(prompt, system=system)
        return parse_json_object(raw)

    def transcribe_audio(self, data: bytes, mime_type: str) -> str:
        """Transcribe spoken audio via Gemini multimodal (Web Speech fallback)."""
        if not self._client:
            raise RuntimeError("Gemini client not configured")
        from google.genai import types  # type: ignore

        settings = get_settings()
        # Prefer a text/multimodal model — native-audio preview is for live sessions.
        stt_model = settings.llm_model
        if "native-audio" in stt_model or "tts" in stt_model.lower():
            stt_model = "gemini-2.5-flash"

        prompt = (
            "Transcribe this speech exactly. The speaker is looking for a rental home "
            "in Bengaluru and may use English or light Hinglish. "
            "Return only the transcript text with no quotes, labels, or commentary."
        )
        response = self._client.models.generate_content(
            model=stt_model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=data, mime_type=mime_type or "audio/webm"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        text = getattr(response, "text", None)
        if not text:
            text = str(response)
        return text.strip().strip('"').strip("'")


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        value = json.loads(match.group(0))
        if isinstance(value, dict):
            return value
    raise ValueError(f"Could not parse JSON from model output: {raw[:200]}")
