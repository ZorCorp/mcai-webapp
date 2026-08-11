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

! python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcai_webapp.py" adopt $ARGUMENTS

Report which deployment was adopted and whether the short link was created fresh or repointed
at a new target — repointing changes where an already-circulated link goes, so the user
should know it happened.
