"""WikiCode provider package.

All LLM providers implement BaseProvider. Use get_provider() from the registry
to instantiate a provider by name — this is the preferred entry point.

    from wikicode.core.providers import get_provider

    provider = get_provider("anthropic", api_key="sk-...", model="claude-sonnet-4-6")
    response = await provider.generate(system_prompt="...", user_prompt="...")
"""

from wikicode.core.providers.base import (
    BaseProvider,
    GeneratedResponse,
    ProviderError,
    RateLimitError,
)
from wikicode.core.providers.registry import get_provider, list_providers, register_provider

__all__ = [
    "BaseProvider",
    "GeneratedResponse",
    "ProviderError",
    "RateLimitError",
    "get_provider",
    "list_providers",
    "register_provider",
]
