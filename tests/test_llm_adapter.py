"""Tests for LLM adapter layer."""

import pytest

from techbrief.apps.integrations.llm import (
    BaseLLMAdapter,
    MockLLMAdapter,
    get_llm_adapter,
)


@pytest.mark.django_db
class TestMockLLMAdapter:
    def test_returns_predictable_response(self):
        adapter = MockLLMAdapter()
        result = adapter.chat("Translate this: Hello World")
        assert result.text.startswith("[MOCK LLM RESPONSE]")
        assert result.model == "mock-llm-v1"
        assert "usage" in result.raw_response or "total_tokens" in result.usage

    def test_usage_fields_populated(self):
        adapter = MockLLMAdapter()
        result = adapter.chat("test prompt")
        assert result.usage["total_tokens"] > 0
        assert result.usage["prompt_tokens"] > 0

    def test_system_prompt_param_accepted(self):
        adapter = MockLLMAdapter()
        result = adapter.chat("test", system_prompt="You are a translator.")
        assert result.text


@pytest.mark.django_db
class TestGetLLMAdapter:
    def test_default_returns_mock(self, settings):
        settings.LLM_ADAPTER = "mock"
        adapter = get_llm_adapter()
        assert isinstance(adapter, MockLLMAdapter)

    def test_unknown_returns_mock(self, settings):
        settings.LLM_ADAPTER = "nonexistent"
        adapter = get_llm_adapter()
        assert isinstance(adapter, MockLLMAdapter)

    def test_openai_compatible_adapter_selected(self, settings):
        from techbrief.apps.integrations.llm import OpenAICompatibleAdapter

        settings.LLM_ADAPTER = "openai_compatible"
        adapter = get_llm_adapter()
        assert isinstance(adapter, OpenAICompatibleAdapter)

    def test_base_adapter_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseLLMAdapter()
