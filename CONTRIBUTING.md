# Contributing

Thanks for helping. Bug reports, recordings of what the game sends, fixes and ideas are all welcome.

## Reporting a problem

Open an [issue](https://github.com/bradqui/starglance/issues/new/choose) and fill in the form: your Starglance version, the game channel and patch, and what you were doing. For data that looks wrong after a game update, a recording helps most (README → *Capturing telemetry*).

Don't post invite links, tokens, API keys or your hub's address in issues. Security problems go through a private report instead: see [SECURITY.md](SECURITY.md).

## Changing code

The README's *Development* section covers setup. In short:

```
uv sync --python 3.12
uv run pytest -q
uv run ruff check . && uv run ruff format .
cd web && npm install && npm run check && npm run build
```

- Everything runs without the game: `uv run python -m starglance run --replay --open` plays real recordings.
- Read [docs/SPEC.md](docs/SPEC.md) first, especially its numbered decisions. A change that goes against one should say why, and add a new decision.
- Treat every field from the game as optional: CIG can change the stream in any patch. A behaviour change in the normalizer comes with a test against a recording.
- New recordings must be scrubbed of aUEC and player names before they're committed (`tests/test_fixtures.py` checks). Test names are made up (Rook, Ace, Kestrel...).
- Keep the repo generic: nothing about a particular org, server or person.
- Two rules that aren't negotiable:
  - **Nothing from the network reaches the game.** The agent's servers listen on 127.0.0.1, except the opt-in, view-only *Show on other devices*.
  - **What a player switches off never leaves their PC.**
- Don't copy code from projects without a license (for example `TheBanjolorian/7hills-link`). Implement from documented behaviour instead.

Work on a branch and open a pull request against `main`; nothing is pushed to `main` directly, and a pull request merges once its checks pass. CI runs the tests on Windows and Ubuntu, type-checks and builds the page, and builds and starts the hub image.

By contributing you agree that your contribution is licensed under the project's [MIT license](LICENSE), except changes to the logo artwork, which fall under [brand/LICENSE](brand/LICENSE).
