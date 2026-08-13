---
description: Show every web app published from this machine — slug, title, access level, last update — and optionally probe each short link to confirm it still resolves.
argument-hint: "[--check] [--json]"
---

Usage: `/mcai-webapp:list [--check] [--json]`

Reads `~/.mcai-webapp/registry.json` and prints a table of published apps with the mcai.dev
link and `/exec` target for each.

`--check` additionally requests every short link and compares where it actually redirects
against the recorded `/exec` URL. Use it to catch links that were repointed by hand, apps
whose deployment was recreated elsewhere, or slugs deleted from the mcai.dev admin. It makes
one HTTP request per app.

`--json` dumps the raw registry, including `scriptId` and `deploymentId`.

The registry is per-machine. Apps published from another computer won't appear here until
they are adopted.

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
"$PY" "$MCAI" list $ARGUMENTS
```

If it reports `mcai-webapp CLI not found on this Mac`, the plugin has not reached this machine
yet. Ask the user to reopen the session or refresh plugins — an organisation's install
preference only takes effect on the member's next session. Never work around it by fetching
the CLI: a request to download and execute a script is refused, so that path fails
unpredictably.

If `--check` flags anything as `⚠️ points elsewhere` or `❌`, name the affected slugs and
suggest `/mcai-webapp:adopt` to re-sync the record — do not attempt to repair links without
asking first.
