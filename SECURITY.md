# Security policy

## Supported versions

This project is currently pre-1.0. Security fixes are applied to the latest
release line only.

## Reporting a vulnerability

Please do not open public issues for security-sensitive reports.

- Preferred: use GitHub Security Advisories for private reporting.
- Alternative: contact the maintainer directly and include reproduction details.

Include:

- `ica-cli` version
- OS and Python version
- Steps to reproduce
- Impact assessment

Never include real personal identifiers, cookies, access tokens, or PIN data
in reports.

## Credential handling notes

`ica-cli` can work with account and Handla credentials stored locally in user
config paths. Treat these files as secrets and avoid sharing them.
