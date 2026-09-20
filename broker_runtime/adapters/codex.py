"""OpenAI Codex OAuth upstream adapter for the local subscription proxy."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, FrozenSet, Optional

from broker_runtime.adapters.base import UpstreamAdapter, UpstreamCredential

logger = logging.getLogger(__name__)

_ALLOWED_PATHS: FrozenSet[str] = frozenset({"/responses", "/models"})


class OpenAICodexAdapter(UpstreamAdapter):
    """Proxy upstream backed by the active Hermes Codex OAuth credential."""

    auth_hint = "hermes auth add openai-codex --type oauth"

    def __init__(self, *, resolve_credentials=None, header_factory=None) -> None:
        self._lock = threading.Lock()
        if resolve_credentials is None:
            from hermes_cli.auth_codex import resolve_codex_runtime_credentials
            resolve_credentials = resolve_codex_runtime_credentials
        if header_factory is None:
            from agent.codex_headers import codex_cloudflare_headers
            header_factory = codex_cloudflare_headers
        self._resolve_credentials = resolve_credentials
        self._header_factory = header_factory

    @property
    def name(self) -> str:
        return "openai-codex"

    @property
    def display_name(self) -> str:
        return "OpenAI Codex OAuth"

    @property
    def allowed_paths(self) -> FrozenSet[str]:
        return _ALLOWED_PATHS

    def is_authenticated(self) -> bool:
        try:
            self._resolve(refresh_if_expiring=False)
        except Exception:
            return False
        return True

    def get_credential(self) -> UpstreamCredential:
        return self._resolve()

    def get_retry_credential(
        self, *, failed_credential: UpstreamCredential, status_code: int
    ) -> Optional[UpstreamCredential]:
        _ = failed_credential
        if status_code != 401:
            return None
        logger.info("proxy: Codex upstream rejected bearer; force-refreshing centrally")
        return self._resolve(force_refresh=True)

    def _resolve(self, **kwargs: Any) -> UpstreamCredential:
        with self._lock:
            try:
                resolved: Dict[str, Any] = self._resolve_credentials(**kwargs)
            except Exception as exc:
                raise RuntimeError(f"Failed to resolve OpenAI Codex credentials: {exc}") from exc
            bearer = str(resolved.get("api_key") or "").strip()
            base_url = str(resolved.get("base_url") or "").strip().rstrip("/")
            if not bearer or not base_url:
                raise RuntimeError(
                    "OpenAI Codex credential resolution returned no bearer or base URL. "
                    "Run `hermes auth add openai-codex --type oauth`."
                )
            headers = self._header_factory(bearer, base_url=base_url)
            return UpstreamCredential(
                bearer=bearer,
                base_url=base_url,
                expires_at=resolved.get("last_refresh"),
                extra_headers=headers,
            )


__all__ = ["OpenAICodexAdapter"]
