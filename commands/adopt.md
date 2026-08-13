---
description: Register an already-deployed Apps Script web app into the local registry and give it an mcai.dev short link, so it can be updated in place from here.
argument-hint: "--script-id <id> --slug <slug> [--deployment-id <id>] [--html <file>]"
---

Usage: `/mcai-webapp:adopt --script-id <id> --slug <slug> [--deployment-id <id>] [--title "..."] [--html <file>] [--access org|gmail|anyone|private]`

For apps that already exist — deployed by hand, by another machine, or before this skill was
installed. Finds the web app deployment, reads its `/exec` URL, creates or repoints
`mcai.dev/<slug>`, and writes the record so `/mcai-webapp:update` works from now on.

`--deployment-id` is only needed when the script has more than one web app deployment; with
exactly one it is detected automatically. If several exist the script lists them and stops —
picking the wrong one would repoint the short link at a stale version.

Pass `--html` if a local copy of the source exists. Without it, every future update has to
name the file explicitly.

If the slug already exists on mcai.dev it is reused and repointed, not duplicated.

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
"$PY" "$MCAI" adopt $ARGUMENTS
```

If it reports `mcai-webapp CLI not found on this Mac`, the plugin has not reached this machine
yet. Ask the user to reopen the session or refresh plugins — an organisation's install
preference only takes effect on the member's next session. Never work around it by fetching
the CLI: a request to download and execute a script is refused, so that path fails
unpredictably.

Report which deployment was adopted and whether the short link was created fresh or repointed
at a new target — repointing changes where an already-circulated link goes, so the user
should know it happened.
