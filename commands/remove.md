---
description: Take a published web app down — delete its mcai.dev short link and undeploy the Apps Script web app. Always confirms the exact app first.
argument-hint: "--slug <slug>"
---

Usage: `/mcai-webapp:remove --slug <slug>`

Irreversible. Never guess which app: show the user the slug, title and `/exec` URL
(`/mcai-webapp:list`) and get an explicit yes for **that** app before deleting anything.

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
"$PY" "$MCAI" remove $ARGUMENTS            # dry run: prints the plan, changes nothing
```

If it reports `mcai-webapp CLI not found on this Mac`, the plugin has not reached this machine
yet. Ask the user to reopen the session or refresh plugins — an organisation's install
preference only takes effect on the member's next session. Never work around it by fetching
the CLI: a request to download and execute a script is refused, so that path fails
unpredictably.

## Steps

1. **Dry run** — the command above. It prints what will be undeployed, deleted and kept,
   and changes nothing.

2. **Confirm** with the user, naming the slug and title.

3. **Delete the short link.** Prefer the **masterlink connector** when its tools are available
   (`masterlink_list_bookmarks`, `masterlink_delete_bookmark`):
   - Take `bookmarkId` from the dry run, or `masterlink_list_bookmarks` with `search=<slug>`.
   - Check the returned bookmark's `slug` equals the requested slug before deleting; if
     two candidates match, stop and ask.
   - `masterlink_delete_bookmark` with that id.
   - Then run step 4 with `--skip-link` so the CLI does not touch the bookmark again.

   No connector? Skip this step and omit `--skip-link`: the CLI deletes the bookmark through
   the mcai.dev API. If that fails it warns and carries on — then delete it in
   mcai.dev/admin/.

4. **Undeploy and forget** — same terminal, same `$PY` / `$MCAI`:

   ```sh
   "$PY" "$MCAI" remove --slug <slug> --skip-link --yes   # drop --skip-link if step 3 was skipped
   ```

   This deletes the Apps Script deployment (the `/exec` URL stops working) and removes the
   slug from `registry.json`. It stops on an Apps Script error before touching anything else,
   so a failed undeploy leaves the registry intact and a rerun is safe.

The Apps Script **project** is deliberately left in the user's Drive — deleting it needs a
Drive scope this skill does not request. Tell the user they can trash it from
script.google.com if they want it gone for good.

If it reports `UNKNOWN_APP`, the app was published from another machine or by someone else.
To remove just a short link that is not in the registry, use `masterlink_delete_bookmark`
directly (after the same by-name confirmation).
