"""Hermes model-provider profile for a local Anthropic broker."""

from providers import register_provider
from providers.base import ProviderProfile

register_provider(
    ProviderProfile(
        name="anthropic-broker",
        aliases=("local-anthropic", "claude-broker"),
        api_mode="anthropic_messages",
        display_name="Local Anthropic Broker",
        description="Loopback Anthropic Messages provider backed by a separate Anthropic OAuth broker",
        env_vars=("HERMES_ANTHROPIC_BROKER_KEY",),
        base_url="http://127.0.0.1:8646/v1",
        auth_type="api_key",
        supports_health_check=False,
        supports_model_listing=False,
        fallback_models=("claude-opus-latest", "claude-sonnet-latest", "claude-haiku-latest"),
        default_aux_model="claude-haiku-latest",
    )
)
