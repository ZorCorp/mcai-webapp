---
description: Push new content to an already-published web app, redeploying in place so the /exec URL and the mcai.dev short link stay unchanged.
argument-hint: "--slug <slug> [file.html] [--title \"...\"] [--message \"...\"]"
---

Usage: `/mcai-webapp:update --slug <slug> [file.html] [--title "..."] [--message "..."] [--access org|gmail|anyone|private]`

Pushes new content to an existing app and updates the **same** deployment. Because the
deployment id doesn't change, the `/exec` URL doesn't change, so the mcai.dev link keeps
working untouched.

The HTML file is optional — the path recorded at publish time is reused if omitted. Pass it
explicitly if the file moved or the app was adopted without one.

`--access org|gmail|anyone|private` changes the access level on the next version (the old
`--public` / `--org-only` flags still work as aliases). Everything else about the app stays
as it was. Widening access (org → gmail/anyone) deserves an explicit confirmation from the
user — say what will become visible to whom.

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
"$PY" "$MCAI" update $ARGUMENTS
```

If it reports `mcai-webapp CLI not found on this Mac`, the plugin has not reached this machine
yet. Ask the user to reopen the session or refresh plugins — an organisation's install
preference only takes effect on the member's next session. Never work around it by fetching
the CLI: a request to download and execute a script is refused, so that path fails
unpredictably.

The expected output includes `web app URL unchanged — the short link needs no edit`. If
instead it warns that the URL changed, surface that prominently: it means the deployment was
recreated rather than updated, the skill has repointed the bookmark automatically, and anyone
holding the old `/exec` URL now has a dead link.

If it reports `UNKNOWN_APP`, the registry has no record of that slug — the app may have been
published from a different machine. Use `/mcai-webapp:adopt` with the scriptId to register it
here first.
