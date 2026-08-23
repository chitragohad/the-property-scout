"""Voice settings helpers — Gemini TTS voice normalization."""

from __future__ import annotations

import io
import re
import wave

MAX_SPEECH_CHARS = 320
SHORTLIST_REVEAL_RE = re.compile(r"I found \d+ options?", re.IGNORECASE)
LISTING_LINE_RE = re.compile(r"\d+\.\s+.+?\d+\s*BHK", re.IGNORECASE)
LISTING_SCORE_RE = re.compile(r"\(score\s[\d.]+\)", re.IGNORECASE)

# Prebuilt voices for gemini-2.5-*-preview-tts (see Gemini API speech-generation docs).
GEMINI_TTS_VOICES: frozenset[str] = frozenset(
    {
        "Achernar",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Aoede",
        "Autonoe",
        "Callirrhoe",
        "Charon",
        "Despina",
        "Enceladus",
        "Erinome",
        "Fenrir",
        "Gacrux",
        "Iapetus",
        "Kore",
        "Laomedeia",
        "Leda",
        "Orus",
        "Puck",
        "Pulcherrima",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Sulafat",
        "Umbriel",
        "Vindemiatrix",
        "Zephyr",
        "Zubenelgenubi",
    }
)

DEFAULT_GEMINI_VOICE = "Charon"


def normalize_gemini_voice(raw: str) -> str:
    """Map env values like Charon_v2_premium → Charon for the Gemini TTS API."""
    name = raw.strip()
    if not name:
        return DEFAULT_GEMINI_VOICE
    name = re.sub(r"_v\d+(_premium)?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_premium$", "", name, flags=re.IGNORECASE)
    if name.islower():
        name = name[:1].upper() + name[1:]
    if name in GEMINI_TTS_VOICES:
        return name
    return DEFAULT_GEMINI_VOICE


def pcm_to_wav(
    pcm: bytes,
    *,
    rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def parse_pcm_sample_rate(mime_type: str | None) -> int:
    """Extract sample rate from Gemini PCM mime types like audio/L16;codec=pcm;rate=24000."""
    if not mime_type:
        return 24000
    match = re.search(r"rate=(\d+)", mime_type, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 24000


def is_pcm_mime(mime_type: str | None) -> bool:
    if not mime_type:
        return True
    base = mime_type.split(";", 1)[0].strip().lower()
    return base in {"audio/pcm", "audio/l16", "audio/raw", "audio/x-raw"}


def _truncate_for_speech(text: str, max_chars: int = MAX_SPEECH_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    boundary = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    if boundary >= 80:
        return cut[: boundary + 1].strip()
    return f"{cut.strip()}…"


def speech_text_for_playback(assistant_text: str, shortlist_count: int) -> str:
    """Mirror frontend assistantTextForSpeech — shared phrasing for inline TTS."""
    trimmed = assistant_text.strip()
    if not trimmed:
        return trimmed

    if shortlist_count > 0:
        listing_line_count = len(re.findall(r"\d+\.\s+", trimmed))
        is_shortlist_reveal = (
            SHORTLIST_REVEAL_RE.search(trimmed) is not None
            or "Here are the listings as per your request" in trimmed
            or LISTING_LINE_RE.search(trimmed) is not None
            or listing_line_count >= 2
            or (LISTING_SCORE_RE.search(trimmed) is not None and listing_line_count >= 1)
        )
        if is_shortlist_reveal:
            return "Here are the listings as per your request."

    return _truncate_for_speech(trimmed)
