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

! python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcai_webapp.py" publish $ARGUMENTS

Relay the short link, the access level, and the `deploymentId` verbatim. If the redirect
could not be confirmed, say so plainly rather than declaring success — the app is deployed
either way, but the link needs checking at <https://mcai.dev/admin/>.

If it reports `SLUG_TAKEN_ON_MCAI`, do not retry with `--force`. Offer the user a different
slug, or `/mcai-webapp:adopt` if they meant to reuse the existing link.
