---
name: mcai-webapp
description: "Turn a prompt or an HTML file into a hosted web page behind a branded mcai.dev short link: draft the page from a prompt, review it locally, publish it as a Google Apps Script web app under the user's own Google Workspace account with a chosen access level (org / gmail / anyone / private), and keep updating it in place afterwards. Self-service: just an mcai.dev API key; no clasp, no Node, no MCP server, just stdlib Python and two REST APIs. Redeploys happen in place so the /exec URL and the short link never change. Use when someone wants a page, deck, dashboard, or form created and put online behind a mcai.dev link, wants to update one they already published, or wants to audit what is currently live. Commands: /mcai-webapp:setup, /mcai-webapp:draft, /mcai-webapp:publish, /mcai-webapp:update, /mcai-webapp:adopt, /mcai-webapp:list."
license: MIT
allowed-tools:
  - Bash(*)
  - Read(*)
  - Write(*)
metadata:
  version: "0.1.0"
  repository: https://github.com/ZorCorp/mcai-webapp
---

# mcai-webapp

Turns a prompt or a local HTML file into a hosted web app with a short, branded URL:

```
prompt  →  draft.html  →  user review  →  Apps Script web app  →  https://mcai.dev/<slug>
```

The pipeline has deliberate, distinct steps: **draft** (generate the HTML), **review**
(user approves it in their own browser), **publish** (deploy with an explicitly chosen
access level and create the short link), and **update** (push new content in place, same
URL, for the life of the app). Starting from an existing HTML file just skips the draft
step.

Hosting is Google Apps Script under the user's own Workspace account, so an org-only app is
protected by Google sign-in with no extra infrastructure. The short link is a 301 redirect
served by MasterLink at mcai.dev.

**Scope:** this skill publishes a single HTML page. It does not write Apps Script business
logic, use OAuth scopes beyond deployment, or touch Google Sheets, Gmail, or Drive data.

## Prerequisites

- **Python 3.8+** — stdlib only. If the machine has none, `setup` installs a pinned,
  checksum-verified interpreter from python.org automatically.
- **An mcai.dev API key** from <https://mcai.dev/admin/> → Settings → API Keys. Nothing else
  to set up: the Google OAuth client itself is issued by mcai.dev against this same key, so
  no one creates one in GCP by hand.
- **The Apps Script API enabled for the account** at
  <https://script.google.com/home/usersettings>. This is a per-user toggle and is off by
  default. The skill detects the resulting error and says so.

## Commands

| Command | Does |
|---|---|
| `/mcai-webapp:setup` | One-time: verify and store the mcai.dev API key, then OAuth consent. Idempotent. |
| `/mcai-webapp:draft` | Prompt → self-contained HTML file, opened locally for review. Never publishes. |
| `/mcai-webapp:publish` | New app — create project, push, deploy, create the short link, verify it. |
| `/mcai-webapp:update` | Push new content to an existing app, redeploying in place. |
| `/mcai-webapp:adopt` | Register a script someone already deployed, and give it a short link. |
| `/mcai-webapp:list` | Table of everything published from this machine; `--check` probes each link. |

`doctor` is also available directly (`PY=$(sh scripts/ensure_python.sh) && "$PY" scripts/mcai_webapp.py doctor`)
and reports on every credential without changing anything.

## How it works

1. `POST /v1/projects` with the real title — no placeholder, so no Drive rename afterwards.
2. `PUT /v1/projects/{id}/content` with three files. This call **replaces the whole project**,
   so all three go every time:
   - `appsscript` (JSON) — the manifest, carrying the `webapp` block
   - `Code` (SERVER_JS) — a `doGet` that serves `index`
   - `index` (HTML) — the user's file, byte for byte
3. `POST /v1/projects/{id}/versions` — an immutable snapshot.
4. First publish only: `POST /v1/projects/{id}/deployments`. Every later update:
   `PUT /v1/projects/{id}/deployments/{deploymentId}`.
5. Read `entryPoints[].webApp.url` from the deployment.
6. `POST mcai.dev/api/bookmarks.php` with `link_type: redirect` and the requested `slug`.
7. `GET mcai.dev/<slug>` and confirm a 301 to the web app.

### Why updates never break the link

`deployments.create` mints a **new** deployment id and therefore a new `/exec` URL, orphaning
the short link. `deployments.update` points the **existing** deployment at a new version, so
the URL is byte-identical. The skill records `deploymentId` at publish time and only ever
uses the update path afterwards — which is why the mcai.dev link is created exactly once and
then left alone.

If an update ever does return a changed URL, the skill repoints the bookmark automatically
and prints a loud warning.

### Access levels

Set declaratively in the manifest; the REST API has no per-deployment access parameter.

| Flag | `webapp.access` | Who can open it |
|---|---|---|
| `--access org` *(default)* | `DOMAIN` | Only accounts in the deployer's Workspace domain |
| `--access gmail` | `ANYONE` | Anyone signed into any Google account |
| `--access anyone` | `ANYONE_ANONYMOUS` | Anyone, no sign-in |
| `--access private` | `MYSELF` | Only the deploying account |

`--public` remains as a deprecated alias for `--access anyone`. Always confirm the level
with the user before publishing; widening it later (`update --access …`) deserves the same
confirmation.

`executeAs` is always `USER_DEPLOYING`, so visitors never see a consent screen and no OAuth
verification is required.

An org-only app returns a domain-scoped URL — `script.google.com/a/macros/<domain>/s/…/exec`,
not the plain `/macros/s/…` form. Both are handled.

## Configuration

State lives in `~/.mcai-webapp/` (override with `MCAI_WEBAPP_HOME`).

| File | Contents | Mode |
|---|---|---|
| `token.json` | OAuth access + refresh token | 600 |
| `.env` | `MCAI_API_KEY=…` | 600 |
| `client.json` | cached OAuth client | 600 |
| `registry.json` | slug → scriptId, deploymentId, execUrl, source path | 644 |

| Env var | Purpose | Default |
|---|---|---|
| `MCAI_CLIENT_SECRET` | Override path to your own OAuth client JSON | mcai.dev issues one automatically |
| `MCAI_GOOGLE_ACCOUNT` | `login_hint` for the consent screen | none |
| `MCAI_CHROME_PROFILE` | Chrome profile directory for consent, e.g. `Default` | system default browser |
| `MCAI_API_KEY` | mcai.dev key, overriding `.env` | from `.env` |
| `MCAI_TIMEZONE` | Manifest timezone | `Asia/Hong_Kong` |
| `MCAI_BASE_URL` | MasterLink base URL | `https://mcai.dev` |

## Hard don'ts

- **Don't run `publish` twice for the same app.** It creates a second, unrelated project and
  a second deployment. Use `update`.
- **Don't delete `~/.mcai-webapp/registry.json`.** It holds the `deploymentId`s; without them
  every future change becomes a new URL and every short link breaks. Recover with `adopt`.
- **Don't print `token.json`, `.env`, or `client.json`,** and don't paste their values into chat.
- **Don't use an Embed-type mcai.dev link for an org-only app.** It sits behind Google login
  and will render a login wall inside the iframe. The skill only ever creates Redirect links.
- **Don't publish anything sensitive as `--access anyone` (or `gmail`).** `ANYONE_ANONYMOUS`
  means exactly that, and Apps Script web app URLs are unauthenticated and
  guessable-by-sharing; `ANYONE` still exposes it to every Google account on earth.

## Troubleshooting

| Symptom | Action |
|---|---|
| `NO_OAUTH_CLIENT` | mcai.dev has no OAuth client configured yet. An admin must paste one at mcai.dev/admin/ → Settings. |
| `OAUTH_CLIENT_FETCH_FAILED` | mcai.dev returned an error (HTTP 4xx/5xx) while fetching the client. Retry; if it persists, check mcai.dev's status. |
| `NETWORK_ERROR` | Couldn't reach mcai.dev at all — offline, DNS, or a firewall. Check the network and retry. |
| `APPS_SCRIPT_API_DISABLED` | Turn on the toggle at <https://script.google.com/home/usersettings>, wait ~1 min, retry. |
| `AUTH_ERROR: access_denied` | A Workspace admin policy is blocking this OAuth client. Ask the admin to allowlist it, or use an internal client from your own GCP project. |
| `AUTH_TIMEOUT` | Consent wasn't completed in 3 min, or it opened in the wrong Chrome profile. Set `MCAI_CHROME_PROFILE` (work profile is usually `Default`) and retry. |
| `NO_REFRESH_TOKEN` | Google withheld it because consent already existed. Revoke at <https://myaccount.google.com/permissions> and rerun setup. |
| `TOKEN_REFRESH_FAILED` | Token revoked or expired. Rerun `/mcai-webapp:setup --force`. |
| `MCAI_UNAUTHORIZED` | Bad or rotated mcai.dev key. Generate a new one and rerun setup. |
| `SLUG_TAKEN_ON_MCAI` | That short link exists already. Pick another `--slug`, or `adopt` it. |
| `NO_WEB_APP_ENTRY_POINT` | The deployed manifest lost its lowercase `webapp` block. Rerun `update`. |
| `PYTHON_DOWNLOAD_FAILED` | Couldn't download the Python installer from python.org. Check the network or a proxy, then retry. |
| `PYTHON_CHECKSUM_MISMATCH` | The downloaded Python installer didn't match its expected checksum. Retry, or check for a proxy tampering with the download. |
| `INSTALL_CANCELLED` / `NOT_ADMIN` | The Python installer needs admin rights. Ask an administrator to run it, or install Python 3.8+ yourself. |
| `PYTHON_INSTALL_FAILED` | The installer ran but no usable Python turned up afterwards. Install Python 3.8+ manually and retry. |
| Web app shows a login wall unexpectedly | It's `DOMAIN` access and the browser is signed into a personal account. Open it in the work Chrome profile. |
| Non-Latin title produces the slug `app` | `slugify` only keeps `[a-z0-9]`. Pass `--slug` explicitly for CJK titles. |

`setup` always contacts mcai.dev to fetch the OAuth client (never the local cache), so on an
already-configured machine `setup` fails if mcai.dev is unreachable — that's the mechanism by
which a centrally rotated client reaches machines set up before the rotation. Every other
command reads the cached `client.json` and doesn't need mcai.dev to be reachable.

If `client.json` becomes corrupt it is silently refetched — it's the tool's own write, so a
bad copy is treated as a cache miss, not an error. `MCAI_CLIENT_SECRET`, by contrast, is an
explicit override: a missing or invalid file there is a hard failure
(`CLIENT_SECRET_NOT_FOUND` / `BAD_OAUTH_CLIENT`), never a silent fallback.

## Done

A successful publish prints the short link, the `/exec` URL, the access level, and both
identifiers, and confirms the 301. The app is live and `update` will keep the same URL for
the rest of its life.
