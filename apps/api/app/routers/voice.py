"""Voice endpoints — Gemini TTS/STT and client voice config."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.gemini import GeminiClient
from app.services.voice import GEMINI_TTS_VOICES, normalize_gemini_voice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class VoiceConfigResponse(BaseModel):
    gemini_tts_available: bool
    confidence_threshold: float
    voice: str
    available_voices: list[str] = Field(default_factory=lambda: sorted(GEMINI_TTS_VOICES))


class SttResponse(BaseModel):
    text: str


def _macos_say_wav(text: str) -> bytes | None:
    """Local offline TTS fallback when Gemini is rate-limited (macOS only)."""
    if platform.system() != "Darwin":
        return None
    if not shutil.which("say") or not shutil.which("afconvert"):
        return None

    spoken = text.strip()
    if not spoken:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            aiff = Path(tmp) / "speech.aiff"
            wav = Path(tmp) / "speech.wav"
            subprocess.run(
                ["say", "-v", "Samantha", "-o", str(aiff), spoken],
                check=True,
                capture_output=True,
                timeout=60,
            )
            subprocess.run(
                ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            data = wav.read_bytes()
            return data if len(data) > 100 else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("macOS say TTS fallback failed: %s", exc)
        return None


@router.get("/config", response_model=VoiceConfigResponse)
def voice_config() -> VoiceConfigResponse:
    settings = get_settings()
    client = GeminiClient()
    # Treat local say fallback as TTS available so the client prefers Audio playback.
    local_tts = platform.system() == "Darwin" and bool(shutil.which("say"))
    return VoiceConfigResponse(
        gemini_tts_available=(client.available and bool(settings.gemini_api_key)) or local_tts,
        confidence_threshold=settings.llm_confidence_threshold,
        voice=normalize_gemini_voice(settings.gemini_voice),
    )


@router.post("/tts")
def synthesize_speech(body: TtsRequest) -> Response:
    client = GeminiClient()
    text = body.text.strip()
    wav_bytes: bytes | None = None

    if client.available:
        try:
            wav_bytes = client.generate_speech(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini TTS failed; trying local fallback: %s", exc)

    if not wav_bytes:
        wav_bytes = _macos_say_wav(text)

    if not wav_bytes:
        raise HTTPException(
            status_code=502,
            detail="TTS synthesis failed (Gemini unavailable and no local fallback).",
        )

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/stt", response_model=SttResponse)
async def speech_to_text(audio: UploadFile = File(...)) -> SttResponse:
    """Fallback STT when browser Web Speech API fails (e.g. Chrome network error)."""
    client = GeminiClient()
    if not client.available:
        raise HTTPException(status_code=503, detail="Gemini STT is not configured.")

    data = await audio.read()
    if not data or len(data) < 200:
        raise HTTPException(status_code=400, detail="Audio recording was empty.")

    mime = (audio.content_type or "audio/webm").split(";")[0].strip() or "audio/webm"
    try:
        text = client.transcribe_audio(data, mime)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"STT failed: {exc}") from exc

    return SttResponse(text=text.strip())
