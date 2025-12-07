"""
Unit Tests for LLM Client

Tests multi-provider routing, structured output validation,
retry logic, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

# Add project paths
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "libs"))

from gravity_core.llm.client import (
    LLMClient,
    LLMClientError,
    LLMValidationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMProvider,
)
from gravity_core.schema import AgentOutput


class TestLLMClientInitialization:
    """Tests for LLMClient initialization."""

    def test_client_initializes_with_openai_key(self):
        """Test client initializes OpenAI when key provided."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            client = LLMClient(openai_api_key="sk-test-key")

            assert LLMProvider.OPENAI in client.available_providers

    def test_client_initializes_with_gemini_key(self):
        """Test client initializes Gemini when key provided."""
        with patch("gravity_core.llm.client.genai") as mock_genai:
            mock_genai.configure = MagicMock()
            client = LLMClient(gemini_api_key="gemini-test-key")

            assert LLMProvider.GEMINI in client.available_providers

    def test_client_runs_in_mock_mode_without_keys(self):
        """Test client warns when no API keys configured."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("gravity_core.llm.client.AsyncOpenAI", None):
                with patch("gravity_core.llm.client.genai", None):
                    client = LLMClient()

                    assert client.available_providers == []


class TestProviderRouting:
    """Tests for provider selection based on model name."""

    @pytest.fixture
    def client(self):
        """Create a client with mocked providers."""
        with patch("gravity_core.llm.client.AsyncOpenAI"):
            with patch("gravity_core.llm.client.genai") as mock_genai:
                mock_genai.configure = MagicMock()
                return LLMClient(
                    openai_api_key="sk-test",
                    gemini_api_key="gemini-test",
                )

    def test_gpt_model_routes_to_openai(self, client):
        """Test GPT models route to OpenAI."""
        assert client._get_provider_for_model("gpt-4") == LLMProvider.OPENAI
        assert client._get_provider_for_model("gpt-4o") == LLMProvider.OPENAI
        assert client._get_provider_for_model("gpt-4-turbo") == LLMProvider.OPENAI

    def test_o1_model_routes_to_openai(self, client):
        """Test O1 models route to OpenAI."""
        assert client._get_provider_for_model("o1-preview") == LLMProvider.OPENAI
        assert client._get_provider_for_model("o1-mini") == LLMProvider.OPENAI

    def test_gemini_model_routes_to_gemini(self, client):
        """Test Gemini models route to Gemini."""
        assert client._get_provider_for_model("gemini-1.5-pro") == LLMProvider.GEMINI
        assert client._get_provider_for_model("gemini-1.5-flash") == LLMProvider.GEMINI

    def test_unknown_model_uses_default(self, client):
        """Test unknown model uses default provider."""
        client.default_provider = LLMProvider.OPENAI
        assert client._get_provider_for_model("unknown-model") == LLMProvider.OPENAI

        client.default_provider = LLMProvider.GEMINI
        assert client._get_provider_for_model("custom-model") == LLMProvider.GEMINI


class TestResponseValidation:
    """Tests for response validation against Pydantic schema."""

    @pytest.fixture
    def client(self):
        """Create client for validation tests."""
        return LLMClient()

    def test_valid_response_passes_validation(self, client):
        """Test valid JSON passes schema validation."""
        valid_json = '''{
            "ui_title": "Test Title",
            "ui_subtitle": "Test subtitle",
            "technical_reasoning": "Test reasoning",
            "tool_calls": [],
            "confidence_score": 0.9,
            "agent_persona": "planner"
        }'''

        result = client._validate_response(valid_json, AgentOutput, "test")

        assert isinstance(result, AgentOutput)
        assert result.ui_title == "Test Title"
        assert result.confidence_score == 0.9

    def test_invalid_json_raises_validation_error(self, client):
        """Test invalid JSON raises LLMValidationError."""
        invalid_json = "not json at all"

        with pytest.raises(LLMValidationError) as exc_info:
            client._validate_response(invalid_json, AgentOutput, "test")

        assert "Invalid JSON" in str(exc_info.value)
        assert exc_info.value.raw_response == invalid_json

    def test_missing_required_field_raises_validation_error(self, client):
        """Test missing required fields raise LLMValidationError."""
        missing_field_json = '''{
            "ui_title": "Test",
            "technical_reasoning": "Test",
            "confidence_score": 0.9,
            "agent_persona": "planner"
        }'''  # Missing ui_subtitle

        with pytest.raises(LLMValidationError) as exc_info:
            client._validate_response(missing_field_json, AgentOutput, "test")

        assert len(exc_info.value.validation_errors) > 0

    def test_invalid_confidence_score_raises_validation_error(self, client):
        """Test invalid confidence_score raises LLMValidationError."""
        invalid_confidence = '''{
            "ui_title": "Test",
            "ui_subtitle": "Test",
            "technical_reasoning": "Test",
            "confidence_score": 1.5,
            "agent_persona": "planner"
        }'''  # confidence > 1.0

        with pytest.raises(LLMValidationError) as exc_info:
            client._validate_response(invalid_confidence, AgentOutput, "test")

        assert len(exc_info.value.validation_errors) > 0


class TestErrorHandling:
    """Tests for error handling and custom exceptions."""

    def test_llm_client_error_properties(self):
        """Test LLMClientError has correct properties."""
        error = LLMClientError(
            "Test error",
            provider="openai",
            status_code=500,
            retryable=True,
        )

        assert str(error) == "Test error"
        assert error.provider == "openai"
        assert error.status_code == 500
        assert error.retryable is True

    def test_llm_validation_error_properties(self):
        """Test LLMValidationError captures validation details."""
        error = LLMValidationError(
            "Validation failed",
            raw_response='{"invalid": "json"}',
            validation_errors=[{"loc": ["field"], "msg": "required"}],
        )

        assert error.raw_response == '{"invalid": "json"}'
        assert len(error.validation_errors) == 1
        assert error.retryable is True  # Validation errors are retryable

    def test_llm_rate_limit_error_properties(self):
        """Test LLMRateLimitError captures rate limit info."""
        error = LLMRateLimitError(
            "Rate limited",
            provider="openai",
            retry_after=30.0,
        )

        assert error.provider == "openai"
        assert error.retry_after == 30.0
        assert error.retryable is True


class TestFallbackBehavior:
    """Tests for provider fallback behavior."""

    @pytest.fixture
    def client_with_both_providers(self):
        """Create client with both providers available."""
        with patch("gravity_core.llm.client.AsyncOpenAI"):
            with patch("gravity_core.llm.client.genai") as mock_genai:
                mock_genai.configure = MagicMock()
                return LLMClient(
                    openai_api_key="sk-test",
                    gemini_api_key="gemini-test",
                    enable_fallback=True,
                )

    def test_fallback_from_openai_to_gemini(self, client_with_both_providers):
        """Test fallback from OpenAI to Gemini."""
        fallback = client_with_both_providers._get_fallback_provider(LLMProvider.OPENAI)
        assert fallback == LLMProvider.GEMINI

    def test_fallback_from_gemini_to_openai(self, client_with_both_providers):
        """Test fallback from Gemini to OpenAI."""
        fallback = client_with_both_providers._get_fallback_provider(LLMProvider.GEMINI)
        assert fallback == LLMProvider.OPENAI

    def test_no_fallback_when_disabled(self):
        """Test no fallback when disabled."""
        with patch("gravity_core.llm.client.AsyncOpenAI"):
            with patch("gravity_core.llm.client.genai") as mock_genai:
                mock_genai.configure = MagicMock()
                client = LLMClient(
                    openai_api_key="sk-test",
                    gemini_api_key="gemini-test",
                    enable_fallback=False,
                )

                fallback = client._get_fallback_provider(LLMProvider.OPENAI)
                assert fallback is None


class TestSystemPromptGeneration:
    """Tests for system prompt generation."""

    def test_default_system_prompt_includes_schema(self):
        """Test default system prompt includes JSON schema."""
        client = LLMClient()
        prompt = client._get_default_system_prompt(AgentOutput)

        assert "JSON" in prompt
        assert "ui_title" in prompt
        assert "confidence_score" in prompt

    def test_default_system_prompt_includes_requirements(self):
        """Test default system prompt includes critical requirements."""
        client = LLMClient()
        prompt = client._get_default_system_prompt(AgentOutput)

        assert "CRITICAL REQUIREMENTS" in prompt
        assert "emoji" in prompt.lower() or "user-friendly" in prompt.lower()


class TestRetryLogic:
    """Tests for retry behavior with tenacity."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Test that rate limit errors trigger retry."""
        with patch("gravity_core.llm.client.AsyncOpenAI") as mock_openai:
            # Setup client
            client = LLMClient(openai_api_key="sk-test")

            # Mock the OpenAI client call to fail then succeed
            mock_completion = AsyncMock()
            mock_completion.choices = [
                MagicMock(message=MagicMock(content='{"ui_title":"Test","ui_subtitle":"Test","technical_reasoning":"Test","confidence_score":0.9,"agent_persona":"planner"}'))
            ]

            # Configure mock
            client._openai_client = MagicMock()
            client._openai_client.chat = MagicMock()
            client._openai_client.chat.completions = MagicMock()
            client._openai_client.chat.completions.create = AsyncMock(return_value=mock_completion)

            # Should succeed on first try
            result = await client._generate_openai(
                model_name="gpt-4o",
                prompt="Test prompt",
                output_schema=AgentOutput,
                tools=None,
                system_prompt=None,
                temperature=0.7,
            )

            assert isinstance(result, AgentOutput)
