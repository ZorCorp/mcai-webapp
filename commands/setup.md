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

`--api-key` is required on a **first** run: the CLI has no attached TTY, so it cannot prompt
and fails at once with `NO_MCAI_API_KEY` rather than hanging. On a re-run omit it — the key
already sits in `~/.mcai-webapp/.env` and is picked up from there. Only ask the user for the
key when setup has never succeeded on this Mac, and never ask them to paste one back that is
already stored.

Consent opens a browser **on the user's Mac** and the CLI then waits up to 180 seconds for the
callback. The consent URL is printed to stdout *before* that wait begins, so start the command
as a streaming process — Desktop Commander's `start_process` with `read_process_output` — and
read the URL while it waits. A tool that only returns after the process exits will deadlock:
the URL arrives after the 180 seconds have already run out.

If no browser appears, open the printed URL yourself with the Chrome connector, which reaches
the same Mac, or give the URL to the user to click. Either way the loopback server is already
listening on the Mac, so the callback completes normally.

Run this **on the user's Mac**, through whatever local-terminal capability is available — the
Desktop Commander connector in Cowork, the Bash tool in Claude Code. Both reach the same
machine. Never run it in a sandboxed shell: the OAuth token, the registry and the consent
loopback all live on the Mac, and a sandbox has none of them.

Locate the CLI first. It ships with the plugin and is already on disk — **never download it**:

```sh
MCAI=$(find "$HOME/Library/Application Support/Claude/local-agent-mode-sessions" \
            "$HOME/.claude/plugins/cache/zorskill/mcai-webapp" \
            -maxdepth 6 -path '*/scripts/mcai_webapp.py' 2>/dev/null | while IFS= read -r s; do
  d=${s%scripts/mcai_webapp.py}
  v=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
        "${d}.claude-plugin/plugin.json" 2>/dev/null | head -1)
  printf '%s\t%s\n' "${v:-0.0.0}" "$s"
done | sort -V | tail -1 | cut -f2)
[ -n "$MCAI" ] || { echo "mcai-webapp CLI not found on this Mac" >&2; exit 1; }
PY=$(sh "$(dirname "$MCAI")/ensure_python.sh") || exit 1
"$PY" "$MCAI" setup $ARGUMENTS
```

If it reports `mcai-webapp CLI not found on this Mac`, the plugin has not reached this machine
yet. Ask the user to reopen the session or refresh plugins — an organisation's install
preference only takes effect on the member's next session. Never work around it by fetching
the CLI: a request to download and execute a script is refused, so that path fails
unpredictably.

If consent opens in the wrong Chrome profile, tell them to set `MCAI_CHROME_PROFILE` (the
work profile is usually `Default`) and rerun.

Never echo the contents of `~/.mcai-webapp/token.json`, `.env`, or `client.json`, and never
repeat an API key back into the conversation.
