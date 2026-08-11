---
description: One-time credential setup — Google OAuth consent for Apps Script, then store the mcai.dev API key. Idempotent and safe to re-run.
argument-hint: "[--api-key <key>] [--force]"
---

Usage: `/mcai-webapp:setup [--api-key <key>] [--force]`

Runs the whole first-run sequence: find a Google Desktop OAuth client, open a browser for
consent (`script.projects` + `script.deployments` only), store the token at chmod 600, then
verify and save an mcai.dev API key.

Nothing ships with this plugin — the user brings their own OAuth client and their own key.
gws CLI users already have a client at `~/.config/gws-<profile>/client_secret.json` and it is
found automatically. Re-running is harmless: an existing token is kept unless `--force`.

`--api-key` is optional; without it the script prompts. If the user has no key yet, send them
to <https://mcai.dev/admin/> → Settings → API Keys first.

! python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcai_webapp.py" setup $ARGUMENTS

If it reports `APPS_SCRIPT_API_DISABLED`, tell the user to open
<https://script.google.com/home/usersettings> **as their work account**, turn the Apps Script
API on, wait about a minute, and rerun — that toggle is per-user and off by default.

If consent opens in the wrong Chrome profile, tell them to set `MCAI_CHROME_PROFILE` (the
work profile is usually `Default`) and rerun.

Never echo the contents of `~/.mcai-webapp/token.json` or `.env`, and never repeat an API key
back into the conversation.
