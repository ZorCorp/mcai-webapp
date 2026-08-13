# Changelog

All notable changes to `mcai-webapp` are documented here. Versioning is semver;
new capability → minor, fix/docs → patch.

## [0.3.0]

- Every command now runs on the user's own Mac through a local terminal — the Desktop
  Commander connector in Cowork, the Bash tool in Claude Code. The `!` execution lines are
  gone, and with them the assumption that the host would run them somewhere useful.
  In Cowork that host is a throwaway Linux sandbox, where the OAuth loopback cannot receive
  Google's redirect from the user's browser, credentials do not survive the session, and the
  macOS Python bootstrap does not apply. One path now serves both hosts.
- The CLI is located by version from the plugin's own install directory, covering both the
  org-managed path used by Claude Desktop and Cowork and Claude Code's plugin cache. It is
  never downloaded: a request to fetch and execute a script is refused outright, so a design
  that depended on it would fail unpredictably.
- `setup` no longer prompts for the mcai.dev API key. A terminal connector has no attached
  TTY, so the prompt reached nobody and simply hung; `--api-key` is now required and its
  absence fails immediately.

## [0.2.0]

- The Google OAuth client now comes from mcai.dev over the existing API key, so
  users no longer create one in GCP. Consent and refresh tokens stay on the
  local machine — mcai.dev never sees them.
- A rotated client *secret* is picked up automatically: a refresh failure refetches the
  client once and retries. A rotated client *id* cannot self-heal this way — Google binds
  the refresh token to the id that obtained it — so that still requires
  `/mcai-webapp:setup --force`.
- `setup` verifies the mcai.dev key before opening a browser, so a bad key fails
  immediately instead of after a consent round trip.
- New `scripts/ensure_python.sh` installs a pinned, checksum-verified Python
  from python.org when the machine has none, without triggering the 1.3 GB Xcode
  Command Line Tools dialog. Pinned version: 3.14.7.
- Removed the `~/.config/gws*` client auto-discovery, along with the
  `MULTIPLE_CLIENT_SECRETS` and `BAD_CLIENT_SECRET` failures it caused.

## [0.1.0] - 2026-07-29
- Initial release. Publishes an HTML file as a Google Apps Script web app via the Apps Script
  REST API (`script.googleapis.com/v1`) and registers an mcai.dev short link against it in one
  step. No clasp, no Node, no MCP server — stdlib Python 3 plus the two REST APIs.
- Five commands: `setup`, `publish`, `update`, `adopt`, `list`.
- Updates go through `deployments.update` on the saved `deploymentId`, so the `/exec` URL is
  stable across redeploys and the mcai.dev link is created exactly once.
- Access level is set declaratively in the pushed `appsscript.json` manifest (`DOMAIN` for
  org-only, `ANYONE_ANONYMOUS` for public); there is no per-deployment access parameter in
  the REST API.
- Self-service credentials: discovers an existing Google Desktop OAuth client
  (`client_secret.json`, gws CLI profile or `MCAI_CLIENT_SECRET`), runs a loopback OAuth flow
  for `script.projects` + `script.deployments`, and stores the token at chmod 600. Nothing
  ships with the plugin.
