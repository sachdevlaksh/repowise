"""Ollama provider for WikiCode.

Ollama enables fully offline, local LLM inference. It exposes an OpenAI-compatible
API endpoint, so this provider uses the OpenAI client internally.

No API key required for local deployments. This makes WikiCode usable in:
    - Air-gapped environments
    - High-security codebases that cannot send code to cloud APIs
    - Cost-sensitive projects

Popular models (pull with `ollama pull <model>`):
    - llama3.2          — good general-purpose, 3B/11B variants
    - codellama         — code-focused, good for doc generation
    - deepseek-coder-v2 — strong on code understanding
    - qwen2.5-coder     — excellent multilingual code model

Usage:
    provider = OllamaProvider(model="codellama", base_url="http://localhost:11434/v1")
"""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI
from openai import APIStatusError as _OpenAIAPIStatusError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    RetryError,
)

from wikicode.core.providers.base import (
    BaseProvider,
    GeneratedResponse,
    ProviderError,
)
from wikicode.core.rate_limiter import RateLimiter

log = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_MIN_WAIT = 1.0
_MAX_WAIT = 8.0  # Ollama can be slow on first load, allow more wait time

_DEFAULT_BASE_URL = "http://localhost:11434/v1"


class OllamaProvider(BaseProvider):
    """Ollama provider for local, offline LLM inference.

    Uses Ollama's OpenAI-compatible endpoint. No API key required.

    Args:
        model:        Ollama model name (e.g., 'llama3.2', 'codellama').
                      Must be pulled first: `ollama pull <model>`
        base_url:     Ollama API base URL. Defaults to http://localhost:11434/v1
        rate_limiter: Optional RateLimiter (useful when running multiple
                      concurrent requests against a resource-constrained machine).
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = _DEFAULT_BASE_URL,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        # Ollama's OpenAI-compatible endpoint accepts any non-empty api_key
        self._client = AsyncOpenAI(api_key="ollama", base_url=base_url)
        self._model = model
        self._rate_limiter = rate_limiter

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        request_id: str | None = None,
    ) -> GeneratedResponse:
        if self._rate_limiter:
            await self._rate_limiter.acquire(estimated_tokens=max_tokens)

        log.debug(
            "ollama.generate.start",
            model=self._model,
            max_tokens=max_tokens,
            request_id=request_id,
        )

        try:
            return await self._generate_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                request_id=request_id,
            )
        except RetryError as exc:
            raise ProviderError(
                "ollama",
                f"All {_MAX_RETRIES} retries exhausted: {exc}",
            ) from exc

    @retry(
        retry=retry_if_exception_type(ProviderError),
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential_jitter(initial=_MIN_WAIT, max=_MAX_WAIT),
        reraise=True,
    )
    async def _generate_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        request_id: str | None,
    ) -> GeneratedResponse:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except _OpenAIAPIStatusError as exc:
            raise ProviderError(
                "ollama", str(exc), status_code=exc.status_code
            ) from exc

        usage = response.usage
        result = GeneratedResponse(
            content=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cached_tokens=0,
            usage={
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
            },
        )
        log.debug(
            "ollama.generate.done",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=request_id,
        )
        return result
