"""CLI for the standalone Catduck OAuth broker runtime."""

from __future__ import annotations

import argparse
import asyncio
import sys

from broker_runtime.adapters import ADAPTERS, get_adapter
from broker_runtime.server import AIOHTTP_AVAILABLE, DEFAULT_HOST, DEFAULT_PORT, run_server


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _loopback_host(host: str) -> bool:
    return str(host).strip().lower() in {"127.0.0.1", "localhost", "::1"}


def cmd_start(args) -> int:
    if not _loopback_host(args.host):
        _err("Refusing non-loopback broker bind. Use 127.0.0.1, localhost, or ::1.")
        return 2
    if not AIOHTTP_AVAILABLE:
        _err("The broker runtime requires aiohttp.")
        return 1
    try:
        adapter = get_adapter(args.provider)
    except ValueError as exc:
        _err(f"Error: {exc}")
        return 2
    if not adapter.is_authenticated():
        _err(f"Not logged into {adapter.display_name}. Run `{adapter.auth_hint}` first.")
        return 2
    _err(
        f"Starting {adapter.display_name} broker\n"
        f"  Listening on: http://{args.host}:{args.port}/v1\n"
        "  The client bearer is ignored and replaced with the root Hermes OAuth credential."
    )
    try:
        asyncio.run(run_server(adapter, host=args.host, port=args.port))
    except KeyboardInterrupt:
        _err("\nbroker: stopped")
    except OSError as exc:
        _err(f"broker: failed to bind {args.host}:{args.port}: {exc}")
        return 1
    return 0


def cmd_status(_args) -> int:
    for name in sorted(ADAPTERS):
        adapter = get_adapter(name)
        state = "ready" if adapter.is_authenticated() else "not logged in"
        print(f"{name}: {state}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="catduck-hermes-broker")
    subcommands = parser.add_subparsers(dest="command", required=True)

    start = subcommands.add_parser("start", help="run one loopback OAuth broker")
    start.add_argument("--provider", choices=sorted(ADAPTERS), required=True)
    start.add_argument("--host", default=DEFAULT_HOST)
    start.add_argument("--port", type=int, default=DEFAULT_PORT)
    start.set_defaults(func=cmd_start)

    status = subcommands.add_parser("status", help="show OAuth broker readiness")
    status.set_defaults(func=cmd_status)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
