# ica-cli playbook examples

## Shopping list: add items from a recipe

```bash
# 1. Get list of lists
ica list ls -f json | jq '.data[] | {offlineId, title}'

# 2. Show a specific list
ica list show <LIST_ID> -f json | jq '.data.rows[] | {offlineId, productName}'

# 3. Add items
ica list add <LIST_ID> "1 kg pasta" -f json
ica list add <LIST_ID> "2 burkar krossade tomater" -f json

# 4. Mark items as bought while shopping
ica list check <LIST_ID> <ROW_ID> -f json

# 5. Clean up
ica list delete <LIST_ID> -f json
```

## Handla cart: search and add products

```bash
export ICA_CLI_HANDLA_STORE_ID=12345

# 1. Ensure elevated session is active
ica login elevated

# 2. Search for products
ica product search "oatly havre" --store-id $ICA_CLI_HANDLA_STORE_ID -f json \
  | jq '.data[] | {name, productId}'

# 3. Add to cart
ica cart add <PRODUCT_UUID> -d 2 -f json

# 4. Check cart
ica cart show -f json | jq '.data'
```

## Recipe: fetch and save as Markdown

```bash
# By numeric id
ica recipe get 712978 -o ~/recipes/lasagna.md

# By ica.se URL
ica recipe get "https://www.ica.se/recept/klassisk-lasagne-712978/" -o ~/recipes/lasagna.md

# Print inline
ica recipe get 712978 -m
```

## Keepalive: maintain Handla session with cron

```bash
# Add to crontab: run every 2 minutes quietly
*/2 * * * * ICA_CLI_HANDLA_STORE_ID=12345 ica cart keepalive --quiet
```

## Headless account auth via env

```bash
export ICA_CLI_PERSONAL_ID=YYYYMMDD-XXXX
export ICA_CLI_PIN=1234

# If auth_state.json already exists and token is valid, commands work directly.
# For initial login or token refresh failures, run interactively once:
ica login account
```
