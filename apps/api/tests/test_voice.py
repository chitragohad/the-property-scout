"""Voice service tests."""

from app.services.voice import (
    is_pcm_mime,
    normalize_gemini_voice,
    parse_pcm_sample_rate,
    pcm_to_wav,
)


def test_normalize_gemini_voice_strips_premium_suffix():
    assert normalize_gemini_voice("Charon_v2_premium") == "Charon"
    assert normalize_gemini_voice("kore") == "Kore"
    assert normalize_gemini_voice("NotARealVoice") == "Charon"


def test_gemini_voice_catalog_includes_common_choices():
    from app.services.voice import GEMINI_TTS_VOICES

    assert "Charon" in GEMINI_TTS_VOICES
    assert "Kore" in GEMINI_TTS_VOICES
    assert "Aoede" in GEMINI_TTS_VOICES


def test_pcm_to_wav_wraps_bytes():
    pcm = b"\x00\x01" * 100
    wav = pcm_to_wav(pcm)
    assert wav.startswith(b"RIFF")
    assert b"WAVE" in wav


def test_is_pcm_mime_accepts_gemini_l16():
    assert is_pcm_mime("audio/L16;codec=pcm;rate=24000")
    assert is_pcm_mime("audio/pcm")
    assert not is_pcm_mime("audio/wav")


def test_speech_text_for_playback_shortlist():
    from app.services.voice import speech_text_for_playback

    text = "I found 3 options for 2BHK; Koramangala. Here are the listings..."
    assert speech_text_for_playback(text, 3) == "Here are the listings as per your request."


def test_speech_text_for_playback_truncates():
    from app.services.voice import speech_text_for_playback

    long = "word " * 120
    spoken = speech_text_for_playback(long, 0)
    assert len(spoken) <= 321
