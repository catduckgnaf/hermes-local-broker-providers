# Contributing

Keep this repository limited to standalone Hermes provider profiles for separately operated local brokers.

Do not add OAuth tokens, API keys, broker binaries, broker service code, or changes to Hermes core.

Before opening a pull request:

1. Run the Hermes plugin validator against both provider directories.
2. Confirm the provider modules import through a Hermes checkout.
3. Keep endpoint and model changes explicit in the provider profile and README.
4. Do not claim compatibility with a Hermes release unless it was tested.
