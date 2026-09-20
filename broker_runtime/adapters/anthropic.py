"""Anthropic OAuth upstream adapter for the local subscription proxy."""

from __future__ import annotations

import logging
import threading
from typing import FrozenSet, Optional

from broker_runtime.adapters.base import UpstreamAdapter, UpstreamCredential

logger = logging.getLogger(__name__)

_POOL_PROVIDER = "anthropic"
_BASE_URL = "https://api.anthropic.com/v1"
_ALLOWED_PATHS: FrozenSet[str] = frozenset({"/messages", "/models"})


class AnthropicOAuthAdapter(UpstreamAdapter):
    """Proxy upstream backed by the shared Hermes Anthropic OAuth pool."""

    auth_hint = "hermes auth add anthropic --type oauth"

    def __init__(
        self,
        *,
        load_credentials=None,
        is_oauth_token=None,
        common_betas=None,
        oauth_betas=None,
        claude_code_version=None,
    ) -> None:
        self._lock = threading.Lock()
        if load_credentials is None:
            from agent.credential_pool import load_pool
            load_credentials = lambda: load_pool(_POOL_PROVIDER)
        if is_oauth_token is None:
            from agent.anthropic_credentials import _is_oauth_token
            is_oauth_token = _is_oauth_token
        if common_betas is None or oauth_betas is None or claude_code_version is None:
            from agent.anthropic_adapter import (
                _OAUTH_ONLY_BETAS,
                _common_betas_for_base_url,
                _get_claude_code_version,
            )
            common_betas = common_betas or _common_betas_for_base_url
            oauth_betas = oauth_betas or _OAUTH_ONLY_BETAS
            claude_code_version = claude_code_version or _get_claude_code_version
        self._load_credentials = load_credentials
        self._is_oauth_token = is_oauth_token
        self._common_betas = common_betas
        self._oauth_betas = tuple(oauth_betas)
        self._claude_code_version = claude_code_version
        self._pool = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def display_name(self) -> str:
        return "Anthropic OAuth"

    @property
    def allowed_paths(self) -> FrozenSet[str]:
        return _ALLOWED_PATHS

    def is_authenticated(self) -> bool:
        pool = self._load_pool()
        if pool is None or not pool.has_credentials():
            return False
        return any(
            self._is_oauth_token(str(getattr(entry, "runtime_api_key", None) or entry.access_token or ""))
            for entry in pool.entries()
        )

    def get_credential(self) -> UpstreamCredential:
        with self._lock:
            pool = self._load_pool()
            if pool is None or not pool.has_credentials():
                raise RuntimeError(
                    "No Anthropic OAuth credentials found. Run `hermes auth add anthropic --type oauth` first."
                )
            entry = pool.select()
            if entry is None:
                raise RuntimeError(
                    "No available Anthropic OAuth credential. Reset cooldowns or re-authenticate the root profile."
                )
            self._pool = pool
            return self._credential_from_entry(entry)

    def get_retry_credential(
        self, *, failed_credential: UpstreamCredential, status_code: int
    ) -> Optional[UpstreamCredential]:
        if status_code not in {401, 429}:
            return None
        with self._lock:
            pool = self._pool or self._load_pool()
            if pool is None:
                return None
            replacement = pool.try_refresh_current() if status_code == 401 else None
            if replacement is None:
                replacement = pool.mark_exhausted_and_rotate(
                    status_code=status_code,
                    api_key_hint=failed_credential.bearer,
                )
            if replacement is None:
                return None
            retry_cred = self._credential_from_entry(replacement)
            if retry_cred.bearer == failed_credential.bearer:
                return None
            logger.info("proxy: Anthropic upstream returned %s; retrying with refreshed or rotated OAuth", status_code)
            return retry_cred

    def _load_pool(self):
        try:
            return self._load_credentials()
        except Exception as exc:
            logger.warning("proxy: failed to load Anthropic OAuth credential pool: %s", exc)
            return None

    def _credential_from_entry(self, entry) -> UpstreamCredential:
        bearer = str(getattr(entry, "runtime_api_key", None) or entry.access_token or "").strip()
        if not bearer or not self._is_oauth_token(bearer):
            raise RuntimeError(
                "Anthropic broker requires an OAuth credential, not an API key. "
                "Run `hermes auth add anthropic --type oauth`."
            )
        base_url = str(getattr(entry, "runtime_base_url", None) or entry.base_url or _BASE_URL).strip().rstrip("/")
        if base_url == "https://api.anthropic.com":
            base_url = _BASE_URL
        betas = list(self._common_betas(base_url)) + list(self._oauth_betas)
        headers = {
            "anthropic-version": "2023-06-01",
            "anthropic-beta": ",".join(betas),
            "user-agent": f"claude-code/{self._claude_code_version()} (external, cli)",
            "x-app": "cli",
        }
        return UpstreamCredential(
            bearer=bearer,
            base_url=base_url or _BASE_URL,
            expires_at=entry.expires_at,
            extra_headers=headers,
        )


__all__ = ["AnthropicOAuthAdapter"]
