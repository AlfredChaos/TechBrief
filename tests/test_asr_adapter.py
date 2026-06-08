"""Tests for ASR adapter layer."""

import pytest

from techbrief.apps.integrations.asr import (
    BaseASRAdapter,
    MockASRAdapter,
    TranscriptResult,
    get_asr_adapter,
)


@pytest.mark.django_db
class TestMockASRAdapter:
    def test_returns_transcript_result(self):
        adapter = MockASRAdapter()
        result = adapter.transcribe(audio_url="https://example.com/audio.mp3")
        assert isinstance(result, TranscriptResult)
        assert result.text
        assert len(result.segments) >= 1
        assert result.provider == "mock_asr"

    def test_segments_have_timestamps(self):
        adapter = MockASRAdapter()
        result = adapter.transcribe()
        for seg in result.segments:
            assert seg.start_ms >= 0
            assert seg.end_ms > seg.start_ms
            assert seg.text

    def test_no_input_works(self):
        adapter = MockASRAdapter()
        result = adapter.transcribe()
        assert result.text


@pytest.mark.django_db
class TestGetASRAdapter:
    def test_default_returns_mock(self, settings):
        settings.ASR_ADAPTER = "mock"
        adapter = get_asr_adapter()
        assert isinstance(adapter, MockASRAdapter)

    def test_unknown_returns_mock(self, settings):
        settings.ASR_ADAPTER = "nonexistent"
        adapter = get_asr_adapter()
        assert isinstance(adapter, MockASRAdapter)

    def test_whisper_adapter_selected(self, settings):
        from techbrief.apps.integrations.asr import WhisperASRAdapter

        settings.ASR_ADAPTER = "whisper"
        adapter = get_asr_adapter()
        assert isinstance(adapter, WhisperASRAdapter)

    def test_base_adapter_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseASRAdapter()
