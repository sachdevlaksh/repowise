"""Gemini provider for WikiCode using the native google-genai SDK.

Uses the same google-genai SDK as GeminiEmbedder for consistency.
Runs the synchronous SDK call in a thread pool to avoid blocking asyncio.

Recommended models:
    - gemini-3.1-flash-lite-preview  — fast + cheap (default)
    - gemini-3-flash-preview         — higher quality
"""

from __future__ import annotations

import asyncio
import os

import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
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


class GeminiProvider(BaseProvider):
    """Native Gemini provider using the google-genai SDK.

    Args:
        model:        Gemini model name. Defaults to gemini-3.1-flash-lite-preview.
        api_key:      Google API key. Falls back to GEMINI_API_KEY or GOOGLE_API_KEY env var.
        rate_limiter: Optional RateLimiter instance.
    """

    def __init__(
        self,
        model: str = "gemini-3.1-flash-lite-preview",
        api_key: str | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._model = model
        self._api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if not self._api_key:
            raise ProviderError(
                "gemini",
                "No API key found. Pass api_key= or set GEMINI_API_KEY / GOOGLE_API_KEY env var.",
            )
        self._rate_limiter = rate_limiter

    @property
    def provider_name(self) -> str:
        return "gemini"

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
            "gemini.generate.start",
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
                "gemini",
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
        # Capture self attrs for thread safety (avoids closing over self)
        model = self._model
        api_key = self._api_key

        def _call_sync() -> GeneratedResponse:
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]

            client = genai.Client(api_key=api_key)
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        # max_output_tokens intentionally omitted — Gemini flash
                        # models default to 65k tokens, which is far better for
                        # documentation generation than any low cap we'd impose.
                    ),
                )
            except Exception as exc:
                exc_str = str(exc)
                status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                if status_code == 429 or "429" in exc_str or "quota" in exc_str.lower():
                    raise RateLimitError("gemini", exc_str, status_code=429) from exc
                raise ProviderError("gemini", f"{type(exc).__name__}: {exc_str}") from exc

            usage = response.usage_metadata
            return GeneratedResponse(
                content=response.text or "",
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                cached_tokens=getattr(usage, "cached_content_token_count", 0) or 0,
                usage={
                    "prompt_token_count": getattr(usage, "prompt_token_count", 0) or 0,
                    "candidates_token_count": getattr(usage, "candidates_token_count", 0) or 0,
                    "total_token_count": getattr(usage, "total_token_count", 0) or 0,
                } if usage else {},
            )

        try:
            result = await asyncio.to_thread(_call_sync)
        except (RateLimitError, ProviderError):
            raise
        except Exception as exc:
            raise ProviderError("gemini", f"{type(exc).__name__}: {exc}") from exc

        log.debug(
            "gemini.generate.done",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=request_id,
        )
        return result
