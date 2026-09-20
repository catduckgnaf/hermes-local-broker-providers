# Hermes Local Broker Providers

Standalone Hermes model provider plugins for users who run local loopback brokers for:

* OpenAI Codex OAuth through `codex-broker`
* Anthropic OAuth through `anthropic-broker`

## Why this exists

Hermes profiles are intentionally isolated, which is useful for specialist agents but makes provider authentication repetitive at fleet scale. I run a large set of specialist profiles and was spending too much time handling repeated OAuth and reauthentication problems across the fleet. A local broker gives those profiles one stable Hermes facing endpoint while the broker handles the provider credential and refresh lifecycle in one place.

This project is shared as a practical starting point for other Hermes users with the same problem. Contributions, additional broker compatibility, documentation improvements, and alternative deployment approaches are welcome. Please open an issue or pull request with the use case and the provider or broker involved.

The repository contains two layers:

* Hermes model provider profiles under `plugins/model-providers/`
* An optional standalone loopback broker runtime under `broker_runtime/`

The provider plugins never expose or copy OAuth credentials. The optional runtime resolves the root Hermes profile's existing OAuth credentials per request and forwards only to the corresponding provider API.

## Included providers

| Provider | Hermes API mode | Default endpoint | Aliases |
| --- | --- | --- | --- |
| `codex-broker` | `codex_responses` | `http://127.0.0.1:8645/v1` | `local-codex` |
| `anthropic-broker` | `anthropic_messages` | `http://127.0.0.1:8646/v1` | `local-anthropic`, `claude-broker` |

The endpoints are intentionally loopback only. Do not expose these brokers to a LAN or the public Internet without adding authentication and transport security at the broker layer.

## Installation

This repository is intentionally not installed into the author's Hermes profile. For a user who wants to try it, copy the provider directories into the profile's model provider plugin directory:

```bash
mkdir -p "${HERMES_HOME:-$HOME/.hermes}/plugins/model-providers"
cp -R plugins/model-providers/codex-broker \
  "${HERMES_HOME:-$HOME/.hermes}/plugins/model-providers/"
cp -R plugins/model-providers/anthropic-broker \
  "${HERMES_HOME:-$HOME/.hermes}/plugins/model-providers/"
```

Use the profile specific `HERMES_HOME` when installing for a nondefault profile. Restart Hermes or start a new session so lazy provider discovery runs again.

## Optional broker runtime

Install the repository into the existing Hermes virtual environment. This makes Hermes's credential resolution modules available without modifying the source checkout:

```bash
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/pip" install \
  git+https://github.com/catduckgnaf/hermes-local-broker-providers.git
```

Run one loopback service per provider with that same interpreter:

```bash
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/catduck-hermes-broker" \
  start --provider openai-codex --host 127.0.0.1 --port 8645
"${HERMES_HOME:-$HOME/.hermes}/hermes-agent/venv/bin/catduck-hermes-broker" \
  start --provider anthropic --host 127.0.0.1 --port 8646
```

The runtime imports Hermes's credential resolvers lazily, so it must run from a compatible Hermes virtual environment. It does not modify the Hermes source checkout or depend on the old local adapter branch. The CLI refuses non-loopback binds. The client bearer is ignored and replaced with the centrally resolved OAuth credential.

## Configuration

Select one of the providers in the normal Hermes model configuration or picker:

```text
codex-broker/gpt-5.6-luna
anthropic-broker/claude-opus-latest
```

The exact model names are broker dependent. Change the fallback model list in the provider's `__init__.py` if your broker exposes different names.

If your broker uses different ports, edit `base_url` before copying the plugin. This repository does not silently read behavioral settings from `.env`; credentials belong there, while endpoint choices remain explicit provider configuration.

## Compatibility

The plugin uses Hermes's public model provider registration surface:

```python
from providers import register_provider
from providers.base import ProviderProfile
```

It does not patch Hermes core files or depend on Catduck's local adapter branch. The optional runtime packages the narrow loopback proxy behavior separately while continuing to use Hermes's credential-resolution modules. If a future Hermes release changes provider registration or credential resolution, this package may need a compatibility update, but Hermes updates cannot overwrite it.

This repository provides the provider profiles plus an optional broker runtime. Users still need their own provider authorization in the root Hermes profile.

## Development check

From a Hermes source checkout, validate the plugin with the Hermes plugin validator if available:

```bash
hermes plugins validate ./plugins/model-providers/codex-broker
hermes plugins validate ./plugins/model-providers/anthropic-broker
```

The provider modules are intentionally not importable from this repository alone because `providers` is supplied by Hermes at runtime.

## License

MIT. See [LICENSE](LICENSE).
