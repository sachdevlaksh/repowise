"""Backward-compatibility re-export. Canonical location: repowise.core.providers.llm.registry"""
from repowise.core.providers.llm.registry import *  # noqa: F401, F403
from repowise.core.providers.llm.registry import (  # noqa: F401
    _BUILTIN_PROVIDERS, _custom_providers,
    get_provider, list_providers, register_provider,
)
