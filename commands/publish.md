---
description: Publish an HTML file as a Google Apps Script web app and create its mcai.dev short link — access org / gmail / anyone / private, org-only by default.
argument-hint: "<file.html> --title \"...\" --slug <slug> [--access org|gmail|anyone|private] [--description \"...\"]"
---

Usage: `/mcai-webapp:publish <file.html> --title "Title" --slug <slug> [--access org|gmail|anyone|private] [--description "..."] [--icon lucide:name] [--category-id N]`

Creates a **new** Apps Script project, pushes the HTML, deploys it as a web app, registers
`mcai.dev/<slug>` as a 301 redirect, and verifies the redirect resolves. Records
`scriptId` / `deploymentId` / `execUrl` so later updates keep the same URL.

Access defaults to **org** (`DOMAIN`). The four levels are `org` (Workspace domain only),
`gmail` (any signed-in Google account), `anyone` (public, no sign-in), and `private` (only
the deployer). Confirm which the user wants before running if they haven't said — a page
with internal information must not go out as `anyone` or `gmail`. `--public` still works as
an alias for `--access anyone`.

Pick a short, memorable slug. Without `--slug` it is derived from the title, which gets ugly
fast (`new-joiner-day-1-setup`) and produces just `app` for CJK titles.

This is for new apps only. If the app already exists, use `/mcai-webapp:update` — publishing
again would create a second, unrelated project.

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
"$PY" "$MCAI" publish $ARGUMENTS
```

If it reports `mcai-webapp CLI not found on this Mac`, the plugin has not reached this machine
yet. Ask the user to reopen the session or refresh plugins — an organisation's install
preference only takes effect on the member's next session. Never work around it by fetching
the CLI: a request to download and execute a script is refused, so that path fails
unpredictably.

Relay the short link, the access level, and the `deploymentId` verbatim. If the redirect
could not be confirmed, say so plainly rather than declaring success — the app is deployed
either way, but the link needs checking at <https://mcai.dev/admin/>.

If it reports `SLUG_TAKEN_ON_MCAI`, do not retry with `--force`. Offer the user a different
slug, or `/mcai-webapp:adopt` if they meant to reuse the existing link.
