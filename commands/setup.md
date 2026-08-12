---
description: One-time credential setup — verify the mcai.dev API key, then Google OAuth consent for Apps Script. Idempotent and safe to re-run.
argument-hint: "[--api-key <key>] [--force]"
---

Usage: `/mcai-webapp:setup [--api-key <key>] [--force]`

Runs the whole first-run sequence: verify and save an mcai.dev API key, fetch the Google
OAuth client from mcai.dev with it, open a browser for consent (`script.projects` +
`script.deployments` only), and store the token at chmod 600.

Nothing to configure in GCP — the OAuth client is issued by mcai.dev against the same API
key this plugin already needs, so the user only ever has to bring that one key. Re-running is
harmless: an existing token is kept unless `--force`.

`--api-key` is optional; without it the script prompts. If the user has no key yet, send them
to <https://mcai.dev/admin/> → Settings → API Keys first.

! PY=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/ensure_python.sh") && "$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/mcai_webapp.py" setup $ARGUMENTS

If consent opens in the wrong Chrome profile, tell them to set `MCAI_CHROME_PROFILE` (the
work profile is usually `Default`) and rerun.

Never echo the contents of `~/.mcai-webapp/token.json`, `.env`, or `client.json`, and never
repeat an API key back into the conversation.
