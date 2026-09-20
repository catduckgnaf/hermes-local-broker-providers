"""OAuth broker upstream adapters."""

from broker_runtime.adapters.anthropic import AnthropicOAuthAdapter
from broker_runtime.adapters.base import UpstreamAdapter, UpstreamCredential
from broker_runtime.adapters.codex import OpenAICodexAdapter

ADAPTERS = {
    "anthropic": AnthropicOAuthAdapter,
    "openai-codex": OpenAICodexAdapter,
}


def get_adapter(name: str) -> UpstreamAdapter:
    key = (name or "").strip().lower()
    try:
        return ADAPTERS[key]()
    except KeyError as exc:
        available = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"Unknown broker provider: {name!r}. Available: {available}") from exc


__all__ = ["ADAPTERS", "UpstreamAdapter", "UpstreamCredential", "get_adapter"]