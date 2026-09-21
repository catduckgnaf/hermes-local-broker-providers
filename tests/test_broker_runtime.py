"""Behavior contract for the standalone Catduck OAuth broker runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_runtime.adapters.base import UpstreamAdapter, UpstreamCredential
from broker_runtime.adapters.anthropic import AnthropicOAuthAdapter
from broker_runtime.adapters.codex import OpenAICodexAdapter
from broker_runtime.server import create_app
from broker_runtime.cli import _loopback_host


@dataclass
class _Entry:
    access_token: str
    runtime_api_key: str | None = None
    runtime_base_url: str | None = None
    base_url: str | None = None
    expires_at: str | None = None


class _Pool:
    def __init__(self, entry):
        self.entry = entry

    def has_credentials(self):
        return self.entry is not None

    def entries(self):
        return [self.entry] if self.entry else []

    def select(self):
        return self.entry

    def try_refresh_current(self):
        return self.entry

    def mark_exhausted_and_rotate(self, *, status_code, api_key_hint=None, **_kwargs):
        self.failed_key = api_key_hint
        return self.entry


def test_codex_adapter_resolves_headers_and_bearer():
    adapter = OpenAICodexAdapter(
        resolve_credentials=lambda **_: {
            "api_key": "codex-token",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "last_refresh": "2026-09-20T00:00:00Z",
        },
        header_factory=lambda token, *, base_url: {
            "chatgpt-account-id": "acct-123",
            "x-codex-test": f"{token}@{base_url}",
        },
    )
    cred = adapter.get_credential()
    assert cred.bearer == "codex-token"
    assert cred.base_url == "https://chatgpt.com/backend-api/codex"
    assert cred.extra_headers["chatgpt-account-id"] == "acct-123"


def test_codex_adapter_retries_only_401():
    calls = []

    def resolve(**kwargs):
        calls.append(kwargs)
        return {"api_key": "fresh", "base_url": "https://example.test/v1"}

    adapter = OpenAICodexAdapter(resolve_credentials=resolve, header_factory=lambda *_a, **_k: {})
    failed = UpstreamCredential(bearer="old", base_url="https://example.test/v1")
    assert adapter.get_retry_credential(failed_credential=failed, status_code=429) is None
    assert adapter.get_retry_credential(failed_credential=failed, status_code=401).bearer == "fresh"
    assert calls[-1] == {"force_refresh": True}


def test_anthropic_adapter_builds_oauth_headers():
    entry = _Entry(access_token="oauth-token", base_url="https://api.anthropic.com/v1")
    adapter = AnthropicOAuthAdapter(
        load_credentials=lambda: _Pool(entry),
        is_oauth_token=lambda token: token == "oauth-token",
        common_betas=lambda _url: ["common-beta"],
        oauth_betas=("oauth-beta",),
        claude_code_version=lambda: "9.9.9",
    )
    cred = adapter.get_credential()
    assert cred.bearer == "oauth-token"
    assert cred.extra_headers["anthropic-version"] == "2023-06-01"
    assert cred.extra_headers["anthropic-beta"] == "common-beta,oauth-beta"
    assert cred.extra_headers["user-agent"] == "claude-code/9.9.9 (external, cli)"
    assert cred.extra_headers["x-app"] == "cli"


def test_anthropic_adapter_rejects_api_key():
    adapter = AnthropicOAuthAdapter(
        load_credentials=lambda: _Pool(_Entry(access_token="sk-ant-api03-test")),
        is_oauth_token=lambda _token: False,
        common_betas=lambda _url: [],
        oauth_betas=(),
        claude_code_version=lambda: "1.0.0",
    )
    with pytest.raises(RuntimeError, match="requires an OAuth credential"):
        adapter.get_credential()


def test_anthropic_rotation_attributes_the_failed_bearer():
    pool = _Pool(_Entry(access_token="replacement"))
    adapter = AnthropicOAuthAdapter(
        load_credentials=lambda: pool,
        is_oauth_token=lambda _token: True,
        common_betas=lambda _url: [],
        oauth_betas=(),
        claude_code_version=lambda: "1.0.0",
    )
    failed = UpstreamCredential(bearer="failed-oauth", base_url="https://api.anthropic.com/v1")
    adapter.get_retry_credential(failed_credential=failed, status_code=429)
    assert pool.failed_key == "failed-oauth"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_loopback_hosts_are_accepted(host):
    assert _loopback_host(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com"])
def test_non_loopback_hosts_are_rejected(host):
    assert not _loopback_host(host)


class _StaticAdapter(UpstreamAdapter):
    name = "static"
    display_name = "Static test"
    allowed_paths = frozenset({"/messages"})

    def __init__(self, base_url: str):
        self.base_url = base_url

    def is_authenticated(self):
        return True

    def get_credential(self):
        return UpstreamCredential(
            bearer="broker-bearer",
            base_url=self.base_url,
            extra_headers={"x-app": "broker", "anthropic-version": "2023-06-01"},
        )


def test_server_applies_adapter_headers_after_filtering_client_headers():
    import asyncio
    from aiohttp import ClientSession, web

    async def run():
        captured: Dict[str, Any] = {}

        async def upstream(request):
            captured["authorization"] = request.headers.get("Authorization")
            captured["x-api-key"] = request.headers.get("x-api-key")
            captured["x-app"] = request.headers.get("x-app")
            captured["anthropic-version"] = request.headers.get("anthropic-version")
            return web.json_response({"ok": True})

        upstream_app = web.Application()
        upstream_app.router.add_post("/v1/messages", upstream)
        upstream_runner = web.AppRunner(upstream_app)
        await upstream_runner.setup()
        upstream_site = web.TCPSite(upstream_runner, "127.0.0.1", 0)
        await upstream_site.start()
        upstream_port = upstream_site._server.sockets[0].getsockname()[1]

        proxy_runner = web.AppRunner(create_app(_StaticAdapter(f"http://127.0.0.1:{upstream_port}/v1")))
        await proxy_runner.setup()
        proxy_site = web.TCPSite(proxy_runner, "127.0.0.1", 0)
        await proxy_site.start()
        proxy_port = proxy_site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as session:
                async with session.post(
                    f"http://127.0.0.1:{proxy_port}/v1/messages",
                    headers={
                        "Authorization": "Bearer attacker",
                        "x-api-key": "local-broker-key",
                        "x-app": "attacker",
                        "anthropic-version": "attacker",
                    },
                    json={"hello": "world"},
                ) as response:
                    assert response.status == 200
                    await response.read()
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()

        assert captured["authorization"] == "Bearer broker-bearer"
        assert captured["x-api-key"] is None
        assert captured["x-app"] == "broker"
        assert captured["anthropic-version"] == "2023-06-01"

    asyncio.run(run())


class _RetryAdapter(_StaticAdapter):
    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.retry_calls = 0

    def get_retry_credential(self, *, failed_credential, status_code):
        assert failed_credential.bearer == "broker-bearer"
        assert status_code == 401
        self.retry_calls += 1
        return UpstreamCredential(bearer="fresh-bearer", base_url=self.base_url)


def test_server_retries_once_with_replacement_credential():
    import asyncio
    from aiohttp import ClientSession, web

    async def run():
        seen = []

        async def upstream(request):
            seen.append(request.headers.get("Authorization"))
            if len(seen) == 1:
                return web.json_response({"error": "expired"}, status=401)
            return web.json_response({"ok": True})

        upstream_app = web.Application()
        upstream_app.router.add_post("/v1/messages", upstream)
        upstream_runner = web.AppRunner(upstream_app)
        await upstream_runner.setup()
        upstream_site = web.TCPSite(upstream_runner, "127.0.0.1", 0)
        await upstream_site.start()
        upstream_port = upstream_site._server.sockets[0].getsockname()[1]

        adapter = _RetryAdapter(f"http://127.0.0.1:{upstream_port}/v1")
        proxy_runner = web.AppRunner(create_app(adapter))
        await proxy_runner.setup()
        proxy_site = web.TCPSite(proxy_runner, "127.0.0.1", 0)
        await proxy_site.start()
        proxy_port = proxy_site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as session:
                async with session.post(
                    f"http://127.0.0.1:{proxy_port}/v1/messages", json={}
                ) as response:
                    assert response.status == 200
                    await response.read()
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()

        assert seen == ["Bearer broker-bearer", "Bearer fresh-bearer"]
        assert adapter.retry_calls == 1

    asyncio.run(run())


def test_proxy_sse_done_normalization():
    from broker_runtime.sse_done import DONE_SSE_FRAME, SseDoneTracker

    tracker = SseDoneTracker()
    tracker.feed(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n')
    assert tracker.should_append_done()
    assert DONE_SSE_FRAME == b"data: [DONE]\n\n"

    existing = SseDoneTracker()
    existing.feed(b"data: [DONE]\n\n")
    assert not existing.should_append_done()

    malformed = SseDoneTracker()
    malformed.feed(b"data: {BROKEN}\n\n")
    assert not malformed.should_append_done()


async def _start_site(app):
    from aiohttp import web

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


def _sse_upstream(chunks, *, abort=False):
    from aiohttp import web

    async def stream(request):
        await request.read()
        response = web.StreamResponse(
            status=200, headers={"Content-Type": "text/event-stream"}
        )
        await response.prepare(request)
        for chunk in chunks:
            await response.write(chunk)
        if abort:
            request.transport.close()
            return response
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_post("/v1/messages", stream)
    return app


@pytest.mark.parametrize(
    "chunks,expected_done",
    [
        (
            [
                b'data: {"choices":[{"delta":{},"finish_',
                b'reason":"stop"}]}\n\n',
            ],
            1,
        ),
        (
            [
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
                b"data: [DONE]\n\n",
            ],
            1,
        ),
    ],
)
def test_server_sse_forwarding_normalizes_done(chunks, expected_done):
    import asyncio
    from aiohttp import ClientSession

    async def run():
        upstream_runner, upstream_base = await _start_site(_sse_upstream(chunks))
        proxy_runner, proxy_base = await _start_site(
            create_app(_StaticAdapter(f"{upstream_base}/v1"))
        )
        try:
            async with ClientSession() as session:
                async with session.post(f"{proxy_base}/v1/messages", json={}) as response:
                    assert response.status == 200
                    assert "text/event-stream" in response.headers["Content-Type"]
                    body = await response.read()
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()
        assert body.count(b"data: [DONE]") == expected_done
        assert b'"finish_reason":"stop"' in body

    asyncio.run(run())


def test_server_sse_interruption_does_not_synthesize_done():
    import asyncio
    from aiohttp import ClientPayloadError, ClientSession

    async def run():
        chunks = [b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n']
        upstream_runner, upstream_base = await _start_site(
            _sse_upstream(chunks, abort=True)
        )
        proxy_runner, proxy_base = await _start_site(
            create_app(_StaticAdapter(f"{upstream_base}/v1"))
        )
        body = b""
        try:
            async with ClientSession() as session:
                try:
                    async with session.post(f"{proxy_base}/v1/messages", json={}) as response:
                        body = await response.read()
                except ClientPayloadError:
                    pass
        finally:
            await proxy_runner.cleanup()
            await upstream_runner.cleanup()
        assert b"data: [DONE]" not in body

    asyncio.run(run())