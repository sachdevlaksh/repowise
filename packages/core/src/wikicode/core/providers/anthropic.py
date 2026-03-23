"""Anthropic provider for WikiCode.

Supports all Claude models. Prompt caching is applied automatically to system
prompts — Anthropic's API caches prompts > 1024 tokens and charges ~10% of
the normal input price on cache hits.

Recommended models (as of 2026):
    - claude-opus-4-6    — highest quality, most expensive
    - claude-sonnet-4-6  — best quality/cost ratio (default)
    - claude-haiku-4-5   — fastest, cheapest (good for low-value pages)
"""

from __future__ import annotations

import structlog
from anthropic import AsyncAnthropic
from anthropic import RateLimitError as _AnthropicRateLimitError
from anthropic import APIStatusError as _AnthropicAPIStatusError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
    RetryError,
)

from wikicode.core.providers.base import (
    BaseProvider,
    GeneratedResponse,
    ProviderError,
    RateLimitError,
)
from wikicode.core.rate_limiter import RateLimiter

log = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_MIN_WAIT = 1.0
_MAX_WAIT = 4.0


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider with automatic prompt caching.

    Args:
        api_key:      Anthropic API key. Reads ANTHROPIC_API_KEY env var if not set.
        model:        Model identifier. Defaults to claude-sonnet-4-6.
        rate_limiter: Optional pre-configured RateLimiter. If None, no rate limiting
                      is applied (useful when the caller manages concurrency via semaphore).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._rate_limiter = rate_limiter

    @property
    def provider_name(self) -> str:
        return "anthropic"

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
            "anthropic.generate.start",
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
                "anthropic",
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
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except _AnthropicRateLimitError as exc:
            raise RateLimitError("anthropic", str(exc), status_code=429) from exc
        except _AnthropicAPIStatusError as exc:
            raise ProviderError(
                "anthropic", str(exc), status_code=exc.status_code
            ) from exc

        cached = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        result = GeneratedResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_tokens=cached,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_creation_input_tokens": getattr(
                    response.usage, "cache_creation_input_tokens", 0
                )
                or 0,
                "cache_read_input_tokens": cached,
            },
        )
        log.debug(
            "anthropic.generate.done",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cached_tokens=result.cached_tokens,
            request_id=request_id,
        )
        return result
