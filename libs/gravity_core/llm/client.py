"""
LLM Client - Core Intelligence Interface

Centralizes all communication with external LLM providers (OpenAI, Gemini).
Enforces the Explainability Contract through structured output validation.
Implements production-grade resilience with retry logic and fallbacks.

Usage:
    from gravity_core.llm import LLMClient

    client = LLMClient(settings)
    output = await client.generate_structured_output(
        prompt="Analyze this task...",
        output_schema=AgentOutput,
        model_name="gpt-4o",
    )
"""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# LLM Provider SDKs
try:
    from openai import APIError as OpenAIAPIError
    from openai import AsyncOpenAI, RateLimitError
except ImportError:
    AsyncOpenAI = None  # type: ignore
    OpenAIAPIError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore

try:
    import google.generativeai as genai
    from google.api_core.exceptions import GoogleAPIError, ResourceExhausted
except ImportError:
    genai = None  # type: ignore
    ResourceExhausted = Exception  # type: ignore
    GoogleAPIError = Exception  # type: ignore

# Import schema
from gravity_core.schema import AgentOutput

logger = structlog.get_logger(__name__)

# Type variable for generic schema support
T = TypeVar("T", bound=BaseModel)


# =============================================================================
# Custom Exceptions
# =============================================================================


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class LLMValidationError(LLMClientError):
    """Raised when LLM output fails Pydantic validation."""

    def __init__(
        self,
        message: str,
        raw_response: str,
        validation_errors: list[dict],
    ):
        super().__init__(message, retryable=True)
        self.raw_response = raw_response
        self.validation_errors = validation_errors


class LLMProviderError(LLMClientError):
    """Raised for provider-specific API errors."""

    pass


class LLMRateLimitError(LLMClientError):
    """Raised when rate limited by provider."""

    def __init__(self, message: str, provider: str, retry_after: float | None = None):
        super().__init__(message, provider=provider, retryable=True)
        self.retry_after = retry_after


# =============================================================================
# Provider Enum
# =============================================================================


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    GEMINI = "gemini"


# =============================================================================
# LLM Client
# =============================================================================


class LLMClient:
    """
    Multi-provider LLM client with structured output enforcement.

    Features:
    - OpenAI (GPT-4, GPT-4o) and Google (Gemini) support
    - Pydantic schema validation for all responses
    - Automatic retries with exponential backoff
    - Provider fallback on failure
    - Detailed error handling and logging
    """

    # Model name prefixes for provider routing
    OPENAI_PREFIXES = ("gpt-", "o1-", "o3-")
    GEMINI_PREFIXES = ("gemini-",)

    # Default models
    DEFAULT_OPENAI_MODEL = "gpt-4o"
    DEFAULT_GEMINI_MODEL = "gemini-1.5-pro"

    def __init__(
        self,
        openai_api_key: str | None = None,
        gemini_api_key: str | None = None,
        default_provider: LLMProvider = LLMProvider.OPENAI,
        enable_fallback: bool = True,
        max_retries: int = 3,
        timeout: float = 120.0,
    ):
        """
        Initialize the LLM client.

        Args:
            openai_api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            gemini_api_key: Gemini API key (or from GOOGLE_API_KEY env var)
            default_provider: Default provider when model not specified
            enable_fallback: Enable automatic fallback to other provider
            max_retries: Maximum retry attempts for transient errors
            timeout: Request timeout in seconds
        """
        self.default_provider = default_provider
        self.enable_fallback = enable_fallback
        self.max_retries = max_retries
        self.timeout = timeout

        # Initialize OpenAI client
        self._openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._openai_client: AsyncOpenAI | None = None
        if self._openai_key and AsyncOpenAI:
            self._openai_client = AsyncOpenAI(
                api_key=self._openai_key,
                timeout=timeout,
            )
            logger.info("OpenAI client initialized")

        # Initialize Gemini client
        self._gemini_key = gemini_api_key or os.getenv("GOOGLE_API_KEY")
        self._gemini_configured = False
        if self._gemini_key and genai:
            genai.configure(api_key=self._gemini_key)
            self._gemini_configured = True
            logger.info("Gemini client initialized")

        # Validate at least one provider is available
        if not self._openai_client and not self._gemini_configured:
            logger.warning("No LLM providers configured - running in mock mode")

    @property
    def available_providers(self) -> list[LLMProvider]:
        """List of available (configured) providers."""
        providers = []
        if self._openai_client:
            providers.append(LLMProvider.OPENAI)
        if self._gemini_configured:
            providers.append(LLMProvider.GEMINI)
        return providers

    def _get_provider_for_model(self, model_name: str) -> LLMProvider:
        """Determine provider based on model name prefix."""
        model_lower = model_name.lower()

        if any(model_lower.startswith(p) for p in self.OPENAI_PREFIXES):
            return LLMProvider.OPENAI
        elif any(model_lower.startswith(p) for p in self.GEMINI_PREFIXES):
            return LLMProvider.GEMINI
        else:
            return self.default_provider

    def _get_fallback_provider(self, primary: LLMProvider) -> LLMProvider | None:
        """Get fallback provider if primary fails."""
        if not self.enable_fallback:
            return None

        if primary == LLMProvider.OPENAI and self._gemini_configured:
            return LLMProvider.GEMINI
        elif primary == LLMProvider.GEMINI and self._openai_client:
            return LLMProvider.OPENAI

        return None

    # =========================================================================
    # Main Generation Method
    # =========================================================================

    async def generate_structured_output(
        self,
        prompt: str,
        output_schema: type[T] = AgentOutput,  # type: ignore
        model_name: str | None = None,
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> T:
        """
        Generate structured output from an LLM provider.

        Enforces the Explainability Contract by validating all responses
        against the provided Pydantic schema.

        Args:
            prompt: The user/task prompt to send
            output_schema: Pydantic model class for response validation
            model_name: Specific model to use (determines provider)
            tools: Optional list of tool definitions for function calling
            system_prompt: Optional system prompt override
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Validated Pydantic model instance

        Raises:
            LLMValidationError: If response fails schema validation
            LLMProviderError: For API-level errors
            LLMRateLimitError: When rate limited
        """
        # Determine provider and model
        provider = self._get_provider_for_model(model_name or "")
        if model_name is None:
            model_name = (
                self.DEFAULT_OPENAI_MODEL
                if provider == LLMProvider.OPENAI
                else self.DEFAULT_GEMINI_MODEL
            )

        logger.info(
            "Generating structured output",
            provider=provider.value,
            model=model_name,
            schema=output_schema.__name__,
        )

        try:
            # Attempt primary provider
            return await self._generate_with_retry(
                provider=provider,
                model_name=model_name,
                prompt=prompt,
                output_schema=output_schema,
                tools=tools,
                system_prompt=system_prompt,
                temperature=temperature,
            )
        except (LLMProviderError, LLMRateLimitError) as e:
            # Try fallback provider if enabled
            fallback = self._get_fallback_provider(provider)
            if fallback:
                logger.warning(
                    "Primary provider failed, trying fallback",
                    primary=provider.value,
                    fallback=fallback.value,
                    error=str(e),
                )
                fallback_model = (
                    self.DEFAULT_OPENAI_MODEL
                    if fallback == LLMProvider.OPENAI
                    else self.DEFAULT_GEMINI_MODEL
                )
                return await self._generate_with_retry(
                    provider=fallback,
                    model_name=fallback_model,
                    prompt=prompt,
                    output_schema=output_schema,
                    tools=tools,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
            raise

    async def _generate_with_retry(
        self,
        provider: LLMProvider,
        model_name: str,
        prompt: str,
        output_schema: type[T],
        tools: list[dict] | None,
        system_prompt: str | None,
        temperature: float,
    ) -> T:
        """Generate with automatic retry on transient errors."""

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((LLMRateLimitError,)),
            reraise=True,
        )
        async def _attempt() -> T:
            if provider == LLMProvider.OPENAI:
                return await self._generate_openai(
                    model_name=model_name,
                    prompt=prompt,
                    output_schema=output_schema,
                    tools=tools,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
            else:
                return await self._generate_gemini(
                    model_name=model_name,
                    prompt=prompt,
                    output_schema=output_schema,
                    tools=tools,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )

        try:
            return await _attempt()
        except RetryError as e:
            # Extract the last exception from retry attempts
            raise e.last_attempt.exception() from e

    # =========================================================================
    # OpenAI Implementation
    # =========================================================================

    async def _generate_openai(
        self,
        model_name: str,
        prompt: str,
        output_schema: type[T],
        tools: list[dict] | None,
        system_prompt: str | None,
        temperature: float,
    ) -> T:
        """Generate structured output using OpenAI API."""
        if not self._openai_client:
            raise LLMProviderError(
                "OpenAI client not initialized",
                provider="openai",
            )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append(
                {
                    "role": "system",
                    "content": self._get_default_system_prompt(output_schema),
                }
            )
        messages.append({"role": "user", "content": prompt})

        # Get JSON schema for structured output
        json_schema = output_schema.model_json_schema()
        json_schema = self._sanitize_schema(json_schema)

        try:
            response = await self._openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.__name__,
                        "strict": False,  # Strict mode requires additionalProperties: false
                        "schema": json_schema,
                    },
                },
                tools=self._format_tools_for_openai(tools) if tools else None,
            )

            # Extract response content
            content = response.choices[0].message.content
            if not content:
                raise LLMProviderError(
                    "Empty response from OpenAI",
                    provider="openai",
                )

            # Validate against schema
            return self._validate_response(content, output_schema, "openai")

        except RateLimitError as e:
            raise LLMRateLimitError(
                str(e),
                provider="openai",
                retry_after=getattr(e, "retry_after", None),
            )
        except OpenAIAPIError as e:
            raise LLMProviderError(
                str(e),
                provider="openai",
                status_code=getattr(e, "status_code", None),
                retryable=getattr(e, "status_code", 500) >= 500,
            )

    def _format_tools_for_openai(self, tools: list[dict]) -> list[dict]:
        """Format tools for OpenAI function calling."""
        return [
            {
                "type": "function",
                "function": tool,
            }
            for tool in tools
        ]

    def _sanitize_schema(self, schema: dict) -> dict:
        """
        Sanitize JSON schema for OpenAI compatibility.

        Converts Pydantic V2 '$defs' to 'definitions' and updates references.
        This fixes 'ValueError: Unknown field for Schema: $defs' in older clients.
        """
        import json

        schema_str = json.dumps(schema)

        # Replace refs
        if "$defs" in schema_str:
            schema_str = schema_str.replace("#/$defs/", "#/definitions/")

        new_schema = json.loads(schema_str)

        # Rename key
        if "$defs" in new_schema:
            new_schema["definitions"] = new_schema.pop("$defs")

        return new_schema

    # =========================================================================
    # Gemini Implementation
    # =========================================================================

    async def _generate_gemini(
        self,
        model_name: str,
        prompt: str,
        output_schema: type[T],
        tools: list[dict] | None,
        system_prompt: str | None,
        temperature: float,
    ) -> T:
        """Generate structured output using Gemini API."""
        if not self._gemini_configured or not genai:
            raise LLMProviderError(
                "Gemini client not initialized",
                provider="gemini",
            )

        # Build full prompt with system context
        full_prompt = ""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n"
        else:
            full_prompt = f"{self._get_default_system_prompt(output_schema)}\n\n"
        full_prompt += prompt

        # Get JSON schema for structured output
        json_schema = output_schema.model_json_schema()
        json_schema = self._sanitize_schema(json_schema)

        try:
            model = genai.GenerativeModel(
                model_name,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=json_schema,
                ),
            )

            response = await model.generate_content_async(full_prompt)

            # Extract text content
            content = response.text
            if not content:
                raise LLMProviderError(
                    "Empty response from Gemini",
                    provider="gemini",
                )

            # Validate against schema
            return self._validate_response(content, output_schema, "gemini")

        except ResourceExhausted as e:
            raise LLMRateLimitError(
                str(e),
                provider="gemini",
            )
        except GoogleAPIError as e:
            raise LLMProviderError(
                str(e),
                provider="gemini",
                retryable=True,
            )

    # =========================================================================
    # Response Validation
    # =========================================================================

    def _validate_response(
        self,
        content: str,
        output_schema: type[T],
        provider: str,
    ) -> T:
        """Validate and parse LLM response against Pydantic schema."""
        try:
            # Clean the response first (handle dirty JSON)
            cleaned_content = self._clean_json_response(content)

            # Try to parse as JSON
            try:
                parsed = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                raise LLMValidationError(
                    f"Invalid JSON from {provider}: {e}",
                    raw_response=content,
                    validation_errors=[{"type": "json_decode", "msg": str(e)}],
                )

            # Validate against Pydantic schema
            return output_schema.model_validate(parsed)

        except ValidationError as e:
            errors = e.errors()
            logger.warning(
                "LLM output failed schema validation",
                provider=provider,
                schema=output_schema.__name__,
                errors=errors,
                raw_response=content[:500],
            )
            raise LLMValidationError(
                f"Schema validation failed: {len(errors)} errors",
                raw_response=content,
                validation_errors=[
                    {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
                    for err in errors
                ],
            )

    def _clean_json_response(self, content: str) -> str:
        """
        Clean common LLM output artifacts from JSON responses.

        Handles:
        - Markdown code fences (```json ... ```)
        - Trailing commas in objects/arrays
        - JavaScript-style comments (// and /* */)
        - Leading/trailing whitespace and text
        """
        import re

        cleaned = content.strip()

        # 1. Extract JSON from markdown code fences
        # Match ```json ... ``` or ``` ... ```
        fence_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        fence_match = re.search(fence_pattern, cleaned, re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # 2. Remove JavaScript-style line comments (// comment)
        # Only remove if not inside a string (simplified: lines ending with // comment)
        cleaned = re.sub(r"//[^\n]*$", "", cleaned, flags=re.MULTILINE)

        # 3. Remove JavaScript-style block comments (/* ... */)
        cleaned = re.sub(r"/\*[\s\S]*?\*/", "", cleaned)

        # 4. Remove trailing commas before } or ]
        # Match comma followed by whitespace and closing bracket
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)

        # 5. If still not starting with { or [, try to find the JSON object
        cleaned = cleaned.strip()
        if cleaned and cleaned[0] not in "{[":
            # Look for first { or [
            start_idx = -1
            for i, char in enumerate(cleaned):
                if char in "{[":
                    start_idx = i
                    break
            if start_idx >= 0:
                cleaned = cleaned[start_idx:]

        return cleaned

    def _get_default_system_prompt(self, output_schema: type[BaseModel]) -> str:
        """Generate default system prompt for structured output."""
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        return f"""You are an AI assistant that must respond with valid JSON matching this schema:

{schema_json}

CRITICAL REQUIREMENTS:
1. Your response MUST be valid JSON only - no markdown, no explanations outside JSON
2. All required fields MUST be present
3. The 'ui_title' should be emoji-prefixed and user-friendly
4. The 'ui_subtitle' should explain what you're doing in plain English
5. The 'technical_reasoning' should document your decision-making process
6. The 'confidence_score' must be between 0.0 and 1.0 (be honest about uncertainty)

Respond ONLY with the JSON object."""

    # =========================================================================
    # Simple Text Generation (for non-structured responses)
    # =========================================================================

    async def generate_text(
        self,
        prompt: str,
        model_name: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate unstructured text response.

        Useful for freeform tasks like code generation where
        structured output isn't needed.
        """
        provider = self._get_provider_for_model(model_name or "")
        if model_name is None:
            model_name = (
                self.DEFAULT_OPENAI_MODEL
                if provider == LLMProvider.OPENAI
                else self.DEFAULT_GEMINI_MODEL
            )

        if provider == LLMProvider.OPENAI and self._openai_client:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self._openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        elif provider == LLMProvider.GEMINI and self._gemini_configured and genai:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            model = genai.GenerativeModel(
                model_name,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            response = await model.generate_content_async(full_prompt)
            return response.text or ""

        raise LLMProviderError(
            f"No client available for provider {provider.value}",
            provider=provider.value,
        )

    # =========================================================================
    # Tool Calling Support
    # =========================================================================

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        model_name: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        tool_choice: str | dict = "auto",
    ) -> tuple[str | None, list[dict]]:
        """
        Generate response with potential tool calls.

        Args:
            tool_choice: "auto", "required", "none", or specific tool dict
        """
        provider = self._get_provider_for_model(model_name or "")
        if model_name is None:
            model_name = (
                self.DEFAULT_OPENAI_MODEL
                if provider == LLMProvider.OPENAI
                else self.DEFAULT_GEMINI_MODEL
            )

        if provider != LLMProvider.OPENAI or not self._openai_client:
            raise LLMProviderError(
                "Tool calling currently only supported with OpenAI",
                provider=provider.value,
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                tools=self._format_tools_for_openai(tools),
                tool_choice=tool_choice,
            )

            message = response.choices[0].message
            text_response = message.content
            tool_calls = []

            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments),
                        }
                    )

            return text_response, tool_calls

        except OpenAIAPIError as e:
            # Capture specific tool usage errors
            logger.error(
                "llm_tool_call_failed",
                model=model_name,
                tool_choice=str(tool_choice),
                error=str(e),
                status_code=getattr(e, "status_code", None),
            )
            # Raise or handle? Raise for now so the agent sees it failed.
            raise LLMProviderError(f"Tool call failed: {e}", provider="openai")
