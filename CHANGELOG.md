# Changelog

All notable changes to `mcai-webapp` are documented here. Versioning is semver;
new capability → minor, fix/docs → patch.

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
