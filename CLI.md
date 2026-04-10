# ICA CLI — agent reference

Unofficial command-line tool for ICA (Sweden): shopping lists, recipes, and
Handla online cart. **JSON-first**: successful commands print one JSON object
per line on **stdout** (wrapped as `{"ok": true, "data": ...}`). Failures print
one JSON object on **stderr** with `error`, `code`, and optional fields.

Entry point after install: `ica` (see `pyproject.toml` → `[project.scripts]`).

---

## Global options

| Option | Effect |
|--------|--------|
| `-v` / `--verbose` | Debug logging on stderr |

Running `ica` with no arguments shows top-level help.

---

## Two separate sign-ins

ICA exposes different backends; this CLI uses **two** persisted sessions.

| Session | CLI | What it unlocks | Backend (conceptual) |
|---------|-----|-----------------|------------------------|
| **Account** | `ica login account` (+ env, see below) | `ica list …`, `ica recipe …` | OAuth + Bearer on ICA API gateway (`apimgw-pub.ica.se`) |
| **Elevated (Handla)** | `ica login elevated` or `ICA_CLI_HANDLA_COOKIE` | `ica cart …` | Browser session cookie + CSRF on `handlaprivatkund.ica.se` |

You may need **both** for full workflows (e.g. build a list via API and a cart
via Handla).

---

## Environment variables

### Account (API) session

| Variable | Role |
|----------|------|
| `ICA_CLI_PERSONAL_ID` | Swedish personal ID (personnummer); can replace saved username |
| `ICA_CLI_PIN` | PIN; required for initial login and when token refresh fails |

If `ICA_CLI_PIN` is unset but a valid saved OAuth access token exists in
`auth_state.json` and a username is known, API calls can still work.

### Elevated (Handla) session

| Variable | Role |
|----------|------|
| `ICA_CLI_HANDLA_STORE_ID` | Numeric store id (from Handla URL); required for cart commands and `login elevated` unless you pass `--store-id` |
| `ICA_CLI_HANDLA_COOKIE` | Raw `Cookie` header value for `handlaprivatkund.ica.se`; **overrides** the saved `handla_web.json` file |

### Config paths (optional overrides)

| Variable | Effect |
|----------|--------|
| `ICA_CLI_CONFIG_DIR` | Base directory for config files (default: XDG `~/.config/ica-cli` or `$XDG_CONFIG_HOME/ica-cli`) |
| `ICA_CLI_AUTH_STATE_PATH` | Full path to account OAuth JSON (default: `{config}/auth_state.json`) |
| `ICA_CLI_HANDLA_WEB_STATE_PATH` | Full path to Handla cookie JSON (default: `{config}/handla_web.json`) |

### Files under config directory (typical)

- `auth_state.json` — OAuth client + tokens (+ embedded `ica_cli_saved_username`)
- `handla_web.json` — `cookie_header` string for Handla
- `username.txt` — saved personal ID from interactive `login account`

---

## Install

```bash
pip install .
# Optional: Playwright-backed browser login for `ica login elevated`
pip install ".[handla-browser]"
# Playwright also needs browser binaries once:
playwright install chromium
```

---

## Command reference

### `ica login`

Typer **group** (not a single command). With **no subcommand**, prints an
explanation of `account` vs `elevated` and subcommand help, then exits 0.

#### `ica login account`

- Interactive prompts: personal ID, PIN.
- Persists OAuth state and username.
- Options: `-f` / `--format` — `json` (default) or `text` for the success line.

#### `ica login elevated`

- Opens Handla in a browser (requires optional dependency **playwright**).
- User completes login; CLI saves cookies to `handla_web.json`.
- Options: `--store-id` — store id if `ICA_CLI_HANDLA_STORE_ID` is not set.
- Output: JSON `{"ok": true, "data": {"saved": true}}`.

---

### `ica logout`

Typer group.

| Invocation | Effect |
|------------|--------|
| `ica logout` | Clears **both** account state file and Handla web state file |
| `ica logout account` | Clears account OAuth state only |
| `ica logout elevated` | Clears Handla cookie state only |

Options on these: `-f` / `--format` (`json` default).

---

### `ica list …`

Requires **account** session. Shopping lists use list and row **offlineId**
strings (UUID-like) from the API.

| Command | Arguments / options | Description |
|---------|---------------------|-------------|
| `ica list ls` | `-f` / `--format` `json`\|`text` | List all lists (`offlineId`, `title`) |
| `ica list show` | `LIST_ID` `-f` | One list with rows |
| `ica list create` | `TITLE` `-f` | Create list via ICA create endpoint; emits normalized output |
| `ica list add` | `LIST_ID` `LINE` `-f` | Add item; `LINE` e.g. `2 st mjölk` |
| `ica list check` | `LIST_ID` `ROW_ID` `-f` | Mark row bought (strikethrough) |
| `ica list uncheck` | `LIST_ID` `ROW_ID` `-f` | Unmark bought |
| `ica list remove` | `LIST_ID` `ROW_ID` `-f` | Delete row |
| `ica list delete` | `LIST_ID` `-f` | Delete list by list id |

Use `list ls` then `list show` to discover ids before mutating.
`list create` may return a different id shape from mobile `offlineId`.

---

### `ica recipe …`

Requires **account** session.

| Command | Arguments / options | Description |
|---------|---------------------|-------------|
| `ica recipe get` | `SPEC` | `SPEC`: numeric id, `slug-123`, or full `ica.se` recipe URL |
| | `-m` / `--markdown` | Print Markdown recipe to stdout |
| | `-o` / `--output` PATH | Write Markdown to file |
| | `-f` | With markdown/output, can still emit JSON meta to stdout |
| `ica recipe favorites` | `-f` | List favorite recipes (API payload) |

Default `recipe get` without `-m`/`-o`: full recipe JSON under `data`.

---

### `ica cart …`

Requires **elevated** session (saved cookie or `ICA_CLI_HANDLA_COOKIE`).
Requires store id via `ICA_CLI_HANDLA_STORE_ID` or `--store-id` on each
command.

| Command | Arguments / options | Description |
|---------|---------------------|-------------|
| `ica cart show` | `--store-id`, `-f` | GET active cart JSON |
| `ica cart add` | `PRODUCT_UUID` `-d`/`--delta` N `--store-id` `-f` | Increase line quantity (default delta +1) |
| `ica cart remove` | `PRODUCT_UUID` `--store-id` `-f` | Decrease quantity by 1; at 0 removes line |

---

### `ica product …`

Anonymous Handla product search. Requires store id via
`ICA_CLI_HANDLA_STORE_ID` or `--store-id`.

| Command | Arguments / options | Description |
|---------|---------------------|-------------|
| `ica product search` | `QUERY` `--store-id` `-f` | Compact product search for agents (`name`, `productId`, optional `unitOfMeasure`) |

When search returns `202 Accepted`, the CLI retries with bounded backoff for up
to 300 seconds total wait. Retry progress is written to `stderr` so JSON output
on `stdout` remains machine-safe.

---

## Output and errors

### Success

```json
{"ok": true, "data": <payload>}
```

`data` is the API response or a small dict like `{"message": "...", "saved": true}`.

### Failure (stderr)

```json
{
  "error": "<human message>",
  "code": "<machine code>",
  "http_status": <optional int>,
  "details": <optional object>
}
```

Process exits with non-zero status (see `ica_cli/exit_codes.py`):

| Code | Name | Typical `code` field |
|------|------|----------------------|
| 0 | SUCCESS | — |
| 1 | USAGE | `bad_recipe_spec`, `missing_handla_store_id`, `handla_browser_login_failed`, … |
| 2 | AUTH | `missing_credentials`, `missing_handla_web_session`, `auth_failed` |
| 3 | UPSTREAM | `upstream_http`, `handla_cart_http`, `handla_search_http`, `handla_csrf_failed`, `recipe_not_found` |
| 4 | NETWORK | `network_error` |

Other `code` values used in CLI: `row_not_found`.

---

## Agent playbooks

### A. Only shopping lists / recipes (no cart)

1. `ica login account` (interactive) **or** set `ICA_CLI_PERSONAL_ID` and
   `ICA_CLI_PIN` and ensure `auth_state.json` exists from a prior login.
2. `ica list ls -f json` → parse `data` for list ids.
3. `ica list show <list_id> -f json` → parse rows.
4. `ica recipe get <id-or-url> -f json` as needed.

### B. Handla cart

1. Set `ICA_CLI_HANDLA_STORE_ID` (or pass `--store-id` everywhere).
2. `ica login elevated` (needs `pip install .[handla-browser]` + Playwright)  
   **or** set `ICA_CLI_HANDLA_COOKIE` from browser DevTools for Handla.
3. `ica product search "mjölk" -f json` → find `productId` UUIDs.
4. `ica cart add <uuid> -d 1 -f json`
5. `ica cart show -f json` to inspect cart.

### C. Discover login help

Run `ica login` with no subcommand to print the two-session summary and Typer
help.

---

## Limitations and stability

- **Unofficial**; ICA may change APIs or HTML at any time.
- Handla flows depend on CSRF tokens parsed from store pages; breakage surfaces
  as `handla_csrf_failed` or HTTP errors.
- `ica login elevated` is headed-browser automation; not suitable for headless
  CI without adapting the flow.

---

## Source map

| Area | Module |
|------|--------|
| CLI wiring | `ica_cli/cli.py` |
| Account OAuth | `ica_cli/authenticator.py`, `ica_cli/ica_api.py` |
| Credentials resolution | `ica_cli/credentials_util.py` |
| Handla HTTP client | `ica_cli/handla_cart.py` |
| Browser login | `ica_cli/handla_browser_login.py` |
| Persisted cookie file | `ica_cli/handla_web_store.py` |
| Paths | `ica_cli/paths.py` |
