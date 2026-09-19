"""Hermes model-provider profile for a local OpenAI Codex broker."""

from providers import register_provider
from providers.base import ProviderProfile

register_provider(
    ProviderProfile(
        name="codex-broker",
        aliases=("local-codex",),
        api_mode="codex_responses",
        display_name="Local Codex Broker",
        description="Loopback OpenAI Responses provider backed by a separate Codex OAuth broker",
        env_vars=("HERMES_CODEX_BROKER_KEY",),
        base_url="http://127.0.0.1:8645/v1",
        auth_type="api_key",
        supports_health_check=False,
        supports_model_listing=False,
        fallback_models=("gpt-5.6-luna", "gpt-5.6-terra"),
        default_aux_model="gpt-5.6-luna",
    )
)
