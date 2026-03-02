"""Tests for agent/audio_transcriber.py."""

from __future__ import annotations

import pytest

from agent.audio_transcriber import is_audio


# ---------------------------------------------------------------------------
# is_audio
# ---------------------------------------------------------------------------


class TestIsAudio:
    def test_ogg_content_type(self):
        assert is_audio("audio/ogg") is True

    def test_mp3_content_type(self):
        assert is_audio("audio/mpeg") is True

    def test_wav_content_type(self):
        assert is_audio("audio/wav") is True

    def test_webm_content_type(self):
        assert is_audio("audio/webm") is True

    def test_opus_content_type(self):
        assert is_audio("audio/opus") is True

    def test_non_audio_content_type(self):
        assert is_audio("application/pdf") is False

    def test_audio_extension_ogg(self):
        assert is_audio("application/octet-stream", "voice.ogg") is True

    def test_audio_extension_mp3(self):
        assert is_audio("application/octet-stream", "song.mp3") is True

    def test_non_audio_extension(self):
        assert is_audio("application/octet-stream", "doc.pdf") is False

    def test_empty_content_type_and_filename(self):
        assert is_audio("") is False

    def test_case_insensitive_extension(self):
        assert is_audio("", "VOICE.OGG") is True
