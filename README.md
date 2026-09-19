# Hermes Local Broker Providers

Standalone Hermes model provider plugins for users who run local loopback brokers for:

* OpenAI Codex OAuth through `codex-broker`
* Anthropic OAuth through `anthropic-broker`

## Why this exists

Hermes profiles are intentionally isolated, which is useful for specialist agents but makes provider authentication repetitive at fleet scale. I run a large set of specialist profiles and was spending too much time handling repeated OAuth and reauthentication problems across the fleet. A local broker gives those profiles one stable Hermes facing endpoint while the broker handles the provider credential and refresh lifecycle in one place.

This project is shared as a practical starting point for other Hermes users with the same problem. Contributions, additional broker compatibility, documentation improvements, and alternative deployment approaches are welcome. Please open an issue or pull request with the use case and the provider or broker involved.

These plugins only register Hermes provider profiles. They do **not** include, start, authenticate, or proxy either broker. The broker remains a separate process owned and operated by the user.

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

It does not patch Hermes core files, replace the proxy implementation, or depend on Catduck's local adapter branch. If a future Hermes release changes the provider registration contract, the plugin may need a compatibility update, but Hermes updates cannot overwrite the plugin itself.

This repository is a shareable provider profile, not a complete broker distribution. Users still need a compatible Codex broker or Anthropic broker implementation and their own provider authorization.

## Development check

From a Hermes source checkout, validate the plugin with the Hermes plugin validator if available:

```bash
hermes plugins validate ./plugins/model-providers/codex-broker
hermes plugins validate ./plugins/model-providers/anthropic-broker
```

The provider modules are intentionally not importable from this repository alone because `providers` is supplied by Hermes at runtime.

## License

MIT. See [LICENSE](LICENSE).
