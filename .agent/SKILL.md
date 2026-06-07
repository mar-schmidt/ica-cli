---
name: ica-cli
version: 0.2.0
description: >
  Use this skill for the ICA CLI to manage Swedish shopping lists, recipes, and
  Handla cart workflows with JSON-first output. Trigger when the user asks about
  ICA shopping lists, recipes, Handla cart, product search, or ICA login/auth.
author: mar-schmidt
repo: https://github.com/mar-schmidt/ica-cli
install:
  pip: pip install "git+https://github.com/mar-schmidt/ica-cli.git"
  pip_browser: pip install "git+https://github.com/mar-schmidt/ica-cli.git#egg=ica-cli[handla-browser]"
requires:
  - python: ">=3.11"
compatibility:
  - claude-desktop
  - cursor
  - continue
  - generic-mcp
tags:
  - shopping
  - ica
  - recipes
  - handla
  - cli
---

# Skill: ica-cli

## When to use

Use this skill when a user wants to:

- log in to ICA and manage session state (account and/or Handla elevated)
- list, create, add items to, or delete ICA shopping lists
- fetch or render ICA recipes
- search products in a Handla store
- view or modify an active Handla cart

## What this CLI does

`ica` is a JSON-first unofficial CLI for ICA Sweden. It provides two
independent sessions — one for the ICA account API and one for the Handla web
store — each persisted locally for headless usage.

Primary command areas:

- `ica login ...` / `ica logout ...` for session management
- `ica list ...` for shopping list CRUD (account session required)
- `ica recipe ...` for fetching and rendering recipes (account session required)
- `ica product search ...` for anonymous product lookup (store id required)
- `ica cart ...` for Handla cart operations (elevated session required)

## Installation

```bash
pip install "git+https://github.com/mar-schmidt/ica-cli.git"
ica --help
```

For `ica login elevated` (browser-backed Handla login):

```bash
pip install "git+https://github.com/mar-schmidt/ica-cli.git#egg=ica-cli[handla-browser]"
playwright install chromium
```

## Two separate sign-ins

ICA exposes different backends. This CLI uses **two** persisted sessions.

| Session | Command | Unlocks | Backend |
|---------|---------|---------|---------|
| **Account** | `ica login account` | `ica list`, `ica recipe` | OAuth + Bearer on `apimgw-pub.ica.se` |
| **Elevated (Handla)** | `ica login elevated` or `ICA_CLI_HANDLA_COOKIE` | `ica cart` | Browser cookie + CSRF on `handlaprivatkund.ica.se` |

A full workflow (build a list then populate a cart) requires both.

## Environment variables

### Account session

| Variable | Role |
|----------|------|
| `ICA_CLI_PERSONAL_ID` | Swedish personal ID (personnummer); can replace saved username |
| `ICA_CLI_PIN` | PIN; required for initial login and when token refresh fails |

### Elevated (Handla) session

| Variable | Role |
|----------|------|
| `ICA_CLI_HANDLA_STORE_ID` | Numeric store id from the Handla URL; required for cart and product commands unless `--store-id` is passed |
| `ICA_CLI_HANDLA_COOKIE` | Raw `Cookie` header value for `handlaprivatkund.ica.se`; overrides the saved `handla_web.json` file |

### Config path overrides

| Variable | Effect |
|----------|--------|
| `ICA_CLI_CONFIG_DIR` | Base directory for config files (default: `~/.config/ica-cli`) |
| `ICA_CLI_AUTH_STATE_PATH` | Full path to account OAuth JSON (default: `{config}/auth_state.json`) |
| `ICA_CLI_HANDLA_WEB_STATE_PATH` | Full path to Handla cookie JSON (default: `{config}/handla_web.json`) |

Config files written under the config directory:

- `auth_state.json` — OAuth tokens and saved username
- `handla_web.json` — Handla cookie header string
- `username.txt` — personal ID from interactive `login account`

## Output and error contract

### Success (stdout)

```json
{"ok": true, "data": <payload>}
```

### Failure (stderr)

```json
{
  "error": "<human message>",
  "code": "<machine code>",
  "http_status": <optional int>,
  "details": <optional object>
}
```

### Exit codes

| Code | Meaning | Typical `code` field |
|------|---------|----------------------|
| 0 | Success | — |
| 1 | Usage / validation | `bad_recipe_spec`, `missing_handla_store_id`, `handla_browser_login_failed`, `row_not_found` |
| 2 | Auth | `missing_credentials`, `missing_handla_web_session`, `auth_failed` |
| 3 | Upstream API | `upstream_http`, `handla_cart_http`, `handla_search_http`, `handla_csrf_failed`, `recipe_not_found`, `handla_search_retry_timeout`, `handla_search_invalid_response` |
| 4 | Network | `network_error` |

## Global options

| Option | Effect |
|--------|--------|
| `-v` / `--verbose` | Debug logging on stderr |

## Auth commands

### `ica login account`

Interactive; prompts for personal ID and PIN. Persists OAuth state.

```bash
ica login account
```

### `ica login elevated`

Opens Handla in a browser (requires `[handla-browser]` extra + Playwright).
Saves cookies to `handla_web.json`.

```bash
ica login elevated --store-id <store_id>
```

`--store-id` is required if `ICA_CLI_HANDLA_STORE_ID` is not set.

Running `ica login` with no subcommand prints a summary of the two sessions
and exits 0.

### `ica logout`

```bash
ica logout               # clears both account and elevated sessions
ica logout account       # clears account OAuth state only
ica logout elevated      # clears Handla cookie state only
```

## Shopping list commands

Require **account** session. IDs are `offlineId` UUID-like strings from the API.

```bash
ica list ls                              # list all shopping lists
ica list show <LIST_ID>                  # show one list with rows
ica list create "Middagslista"           # create a new list
ica list add <LIST_ID> "2 st mjölk"      # add an item
ica list check <LIST_ID> <ROW_ID>        # mark row as bought
ica list uncheck <LIST_ID> <ROW_ID>      # unmark bought
ica list remove <LIST_ID> <ROW_ID>       # delete a row
ica list delete <LIST_ID>               # delete the list
```

All commands accept `-f json` (default) or `-f text`.

Discover ids with `list ls` then `list show` before mutating.

## Recipe commands

Require **account** session.

```bash
ica recipe get <SPEC>                    # fetch recipe JSON
ica recipe get <SPEC> -m                 # print Markdown to stdout
ica recipe get <SPEC> -o recipe.md       # write Markdown to file
ica recipe favorites                     # list favorite recipes
```

`SPEC` accepts: numeric id, `slug-123` format, or a full `ica.se` recipe URL.

When `-m` or `-o` is used, the CLI also emits a small JSON meta object on
stdout (unless suppressed).

## Product search

Anonymous endpoint — no login required, only a store id.

```bash
ica product search "mjölk" --store-id <store_id>
```

Returns compact JSON list with `name`, `productId`, and optional
`unitOfMeasure` per product.

When the search returns `202 Accepted`, the CLI retries with bounded backoff for
up to 300 seconds. Retry progress is written to stderr; stdout stays JSON-safe.

## Cart commands

Require **elevated** session. Require store id via `ICA_CLI_HANDLA_STORE_ID`
or `--store-id` on each command.

```bash
ica cart show --store-id <store_id>                         # GET active cart
ica cart add <PRODUCT_UUID> -d 2 --store-id <store_id>      # increase quantity
ica cart remove <PRODUCT_UUID> --store-id <store_id>        # decrease quantity by 1
ica cart keepalive --store-id <store_id>                    # refresh session cookie
```

`cart add` default delta is `+1`. Pass `-d N` to set an explicit positive delta.

`cart remove` always decrements by 1; the line disappears from the cart at 0.

`cart keepalive` is a lightweight GET that refreshes Handla cookies and the
server idle session. Use it in periodic jobs when elevated login expires often.
The `--quiet` / `-q` flag suppresses stdout (useful for cron).

## Agent playbooks

### A. Shopping lists only (no cart)

1. `ica login account` — interactive sign-in (or set `ICA_CLI_PERSONAL_ID` +
   `ICA_CLI_PIN` if a valid `auth_state.json` already exists).
2. `ica list ls -f json` — parse `data` array for `offlineId` and `title`.
3. `ica list show <list_id> -f json` — parse `rows` for `offlineId` and
   `productName`.
4. Mutate with `ica list add`, `check`, `uncheck`, `remove` as needed.

### B. Handla cart workflow

1. Set `ICA_CLI_HANDLA_STORE_ID` (or pass `--store-id` on every command).
2. `ica login elevated` (requires `[handla-browser]` + Playwright) **or** set
   `ICA_CLI_HANDLA_COOKIE` from browser DevTools for
   `handlaprivatkund.ica.se`.
3. `ica product search "mjölk" --store-id <id> -f json` — pick `productId`
   UUIDs from the returned list.
4. `ica cart add <uuid> -d 1 --store-id <id> -f json`
5. `ica cart show --store-id <id> -f json` — inspect cart state.

### C. Recipe to markdown

1. `ica login account`
2. `ica recipe get <id-or-url> -o recipe.md` — writes Markdown file and emits
   JSON meta on stdout.

## Error recovery

| Error code | Cause | Recovery |
|------------|-------|----------|
| `missing_credentials` | No account session | Run `ica login account` or set env vars |
| `missing_handla_web_session` | No elevated session | Run `ica login elevated` or set `ICA_CLI_HANDLA_COOKIE` |
| `missing_handla_store_id` | No store id | Set `ICA_CLI_HANDLA_STORE_ID` or pass `--store-id` |
| `auth_failed` | OAuth refresh failed | Re-run `ica login account` |
| `handla_csrf_failed` | CSRF token parse failure | Re-run `ica login elevated` or refresh `ICA_CLI_HANDLA_COOKIE` |
| `handla_search_retry_timeout` | 202 still after 300 s | Retry the search |
| `row_not_found` | Row id not in list | Re-fetch list with `list show` and use a valid `offlineId` |
| `recipe_not_found` | Recipe id does not exist | Verify the id or URL |
| `bad_recipe_spec` | Spec could not be resolved to an id | Use a numeric id, `slug-123`, or a full `ica.se` URL |
| `upstream_http` | ICA API returned an error status | Check `http_status` and `details` in the error payload |
| `network_error` | Connection failure | Check network access |

## What NOT to do

- Do not call cart commands without resolving `--store-id` first.
- Do not call `cart add` or `cart remove` without a valid `productId` from
  `product search`.
- Do not skip `ica login account` and expect list or recipe commands to work
  without a valid `auth_state.json`.
- Do not parse human text output when JSON fields exist.
- Do not assume a session persists across machines; auth state is local.

## Limitations

- Unofficial project; ICA may change APIs or HTML at any time.
- Handla flows depend on CSRF tokens parsed from store pages; breakage surfaces
  as `handla_csrf_failed` or HTTP errors.
- `ica login elevated` is headed-browser automation; not suitable for headless
  CI without adapting the flow.
- `ICA_CLI_HANDLA_COOKIE` is a manual fallback when Playwright is unavailable.

## Additional references

- Playbook examples: `examples/playbooks.md`
