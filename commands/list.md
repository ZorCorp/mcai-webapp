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

! python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcai_webapp.py" list $ARGUMENTS

If `--check` flags anything as `⚠️ points elsewhere` or `❌`, name the affected slugs and
suggest `/mcai-webapp:adopt` to re-sync the record — do not attempt to repair links without
asking first.
