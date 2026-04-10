# Contributing to ica-cli

Thanks for contributing.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional browser login support:

```bash
pip install ".[handla-browser]"
playwright install chromium
```

## Run tests

```bash
pytest
```

## Coding guidelines

- Keep line length at 80 characters or less.
- Prefer small, focused PRs.
- Keep CLI output contract stable for JSON consumers.
- Never commit real credentials, cookies, PIN data, or personal IDs.

## Issues and bug reports

When reporting bugs, include:

- `ica-cli` version
- OS and Python version
- command executed
- redacted JSON error output

## Release notes and tags

For releases, use semantic tags while in `0.x` (for example `v0.2.0`) and
publish GitHub Release notes describing notable changes and breakages.
