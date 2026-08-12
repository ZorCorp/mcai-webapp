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

! PY=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/ensure_python.sh") && "$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/mcai_webapp.py" update $ARGUMENTS

The expected output includes `web app URL unchanged — the short link needs no edit`. If
instead it warns that the URL changed, surface that prominently: it means the deployment was
recreated rather than updated, the skill has repointed the bookmark automatically, and anyone
holding the old `/exec` URL now has a dead link.

If it reports `UNKNOWN_APP`, the registry has no record of that slug — the app may have been
published from a different machine. Use `/mcai-webapp:adopt` with the scriptId to register it
here first.
