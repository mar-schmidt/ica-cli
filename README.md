# ica-cli

Unofficial Python CLI for ICA shopping lists, recipes, and Handla cart
workflows. Output is JSON-first for reliable scripting and agent use.

## Important disclaimer

- This project is unofficial and not affiliated with or endorsed by ICA.
- ICA and related marks are trademarks of their respective owners.
- You are responsible for complying with ICA terms and acceptable use.

## Install

### Option A: install from GitHub (recommended for now)

```bash
pip install "git+https://github.com/mar-schmidt/ica-cli.git"
```

### Option B: clone and install locally

```bash
git clone git@github.com:mar-schmidt/ica-cli.git
cd ica-cli
pip install .
```

### Optional browser login support

`ica login elevated` uses Playwright.

```bash
pip install ".[handla-browser]"
playwright install chromium
```

## Quickstart

1. Log in for account APIs:

```bash
ica login account
```

2. List shopping lists:

```bash
ica list ls -f json
```

3. Search products for Handla:

```bash
ica product search "mjolk" --store-id "<store_id>" -f json
```

## Credentials and security

- Credentials are stored locally in your user config directory.
- Never commit real auth cookies, tokens, or personal identifiers.
- See [CLI reference](./CLI.md) for config paths and session details.
- See [Security policy](./SECURITY.md) for vulnerability reporting.

## Command reference

Full command docs are in [CLI.md](./CLI.md).

## Development

```bash
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution details.

## Releases

- Use semantic tags while in `0.x` (for example `v0.2.0`).
- Publish release notes on GitHub for each tag.
