# mcai-webapp

Publish an HTML file as a Google Apps Script web app under your own Workspace account, and
give it a branded short link:

```
page.html  →  Apps Script web app  →  https://mcai.dev/<slug>
```

Org-only by default (Google sign-in, your domain only) or public with one flag. Updates
redeploy in place, so the URL never changes and the short link is created exactly once.

**No clasp. No Node. No MCP server.** Stdlib Python 3 plus two REST APIs.

## Install

```
/plugin marketplace add ZorCorp/zorskill
/plugin install mcai-webapp
```

## Quick start

```
/mcai-webapp:setup
/mcai-webapp:publish ./deck.html --title "Onboarding Deck" --slug orientation
```

```
✅ scriptId 1IuPni22wuE21O2D...
✅ version 1
✅ deploymentId AKfycbz9LoeLCml50t5h...
✅ https://mcai.dev/orientation → 301 → https://script.google.com/a/macros/hkmci.com/s/AKfy.../exec

  Short link   https://mcai.dev/orientation
  Web app      https://script.google.com/a/macros/hkmci.com/s/AKfy.../exec
  Access       your Workspace domain only
```

Then, forever after:

```
/mcai-webapp:update --slug orientation
```

Same URL, same short link, new content.

## Commands

| Command | Does |
|---|---|
| `/mcai-webapp:setup` | One-time OAuth + API key. Idempotent. |
| `/mcai-webapp:draft` | Prompt → reviewable local HTML. Never publishes. |
| `/mcai-webapp:publish` | New app: create, push, deploy, link, verify. |
| `/mcai-webapp:update` | New content into the existing deployment. |
| `/mcai-webapp:adopt` | Register a script deployed elsewhere. |
| `/mcai-webapp:list` | What's live; `--check` probes each link. |

## Prerequisites

- **Python 3.8+** — stdlib only.
- **A Google Desktop OAuth client.** Nothing ships with this plugin, by design. If you use
  the [gws CLI](https://github.com/googleworkspace/cli) you already have one at
  `~/.config/gws-<profile>/client_secret.json` and it's found automatically. Otherwise create
  a Desktop client in your own GCP project and set `MCAI_CLIENT_SECRET` to the downloaded
  JSON.

  > Careful: `oauth-client.json` sitting next to it in the same folder is a *different,
  > inactive* client. Minting against it fails. Use `client_secret.json`.

- **The Apps Script API turned on** at <https://script.google.com/home/usersettings>. Per-user
  toggle, off by default, and the resulting error only appears *after* you authorise — which
  is confusing, so the skill names it explicitly.
- **An mcai.dev API key** — <https://mcai.dev/admin/> → Settings → API Keys.

Only two OAuth scopes are requested: `script.projects` and `script.deployments`. The skill
cannot read your mail, Drive, or Sheets.

## Access levels

| Flag | Manifest value | Who can open it |
|---|---|---|
| `--access org` *(default)* | `DOMAIN` | Accounts in your Workspace domain only |
| `--access gmail` | `ANYONE` | Anyone signed into any Google account |
| `--access anyone` | `ANYONE_ANONYMOUS` | Anyone, no sign-in |
| `--access private` | `MYSELF` | Only the deploying account |

`--public` is kept as a deprecated alias for `--access anyone`.

Access is set in the pushed `appsscript.json` manifest — the REST API has no per-deployment
access parameter, so the manifest at the deployed version is what governs.

`executeAs` is always `USER_DEPLOYING`. Visitors never authorise anything, so there is no
consent screen, no unverified-app warning, and no 100-user cap.

Org-only apps return a domain-scoped URL (`script.google.com/a/macros/<domain>/s/…/exec`).
That's normal.

## Why the short link never breaks

Two ways to redeploy Apps Script, and only one is safe:

| Call | Deployment id | `/exec` URL |
|---|---|---|
| `deployments.create` | **new** | **new** — orphans the short link |
| `deployments.update` | same | **same** |

This skill records the `deploymentId` on first publish and only ever uses the update path.
That's the whole trick, and it's why `publish` and `update` are separate commands rather than
one idempotent verb.

If an update ever does return a different URL, the skill repoints the mcai.dev bookmark and
prints a loud warning.

## Files

`~/.mcai-webapp/` (override with `MCAI_WEBAPP_HOME`):

| File | Contents | Mode |
|---|---|---|
| `token.json` | OAuth token | 600 |
| `.env` | `MCAI_API_KEY=…` | 600 |
| `registry.json` | slug → scriptId, deploymentId, execUrl, source | 644 |

`registry.json` is the only irreplaceable one — it holds the deployment ids. Back it up. If
you lose it, `/mcai-webapp:adopt` can rebuild an entry from a scriptId.

## Configuration

| Var | Purpose | Default |
|---|---|---|
| `MCAI_CLIENT_SECRET` | Path to the Desktop OAuth client JSON | auto-found under `~/.config/gws*/` |
| `MCAI_GOOGLE_ACCOUNT` | `login_hint` on the consent screen | none |
| `MCAI_CHROME_PROFILE` | Chrome profile for consent, e.g. `Default` | system default browser |
| `MCAI_API_KEY` | mcai.dev key, overriding `.env` | from `.env` |
| `MCAI_TIMEZONE` | Manifest timezone | `Asia/Hong_Kong` |
| `MCAI_WEBAPP_HOME` | State directory | `~/.mcai-webapp` |
| `MCAI_BASE_URL` | MasterLink base URL | `https://mcai.dev` |

## Troubleshooting

| Symptom | Action |
|---|---|
| `NO_CLIENT_SECRET` | Set `MCAI_CLIENT_SECRET` to your Desktop OAuth client JSON. |
| `MULTIPLE_CLIENT_SECRETS` | Several gws profiles — pick one via `MCAI_CLIENT_SECRET`. |
| `BAD_CLIENT_SECRET` | No `installed` key. You're pointing at `oauth-client.json`; use `client_secret.json`. |
| `APPS_SCRIPT_API_DISABLED` | Enable at <https://script.google.com/home/usersettings>, wait ~1 min, retry. |
| `AUTH_ERROR: access_denied` | Admin policy blocks this OAuth client. Ask for an allowlist, or use an Internal client from your own GCP project. |
| `AUTH_TIMEOUT` | Consent opened in the wrong Chrome profile. Set `MCAI_CHROME_PROFILE=Default` and retry. |
| `NO_REFRESH_TOKEN` | Revoke at <https://myaccount.google.com/permissions>, then rerun setup. |
| `TOKEN_REFRESH_FAILED` | `/mcai-webapp:setup --force`. |
| `MCAI_UNAUTHORIZED` | Key rotated or wrong. Generate a new one, rerun setup. |
| `SLUG_TAKEN_ON_MCAI` | Pick another slug, or `adopt` the existing link. |
| `UNKNOWN_APP` | Published from another machine — `adopt` it here first. |
| `NO_WEB_APP_ENTRY_POINT` | The manifest lost its lowercase `webapp` block. Rerun `update`. |
| Unexpected login wall | `DOMAIN` app opened in a personal Google profile. Use the work profile. |
| CJK title → slug `app` | Slugs are `[a-z0-9-]` only. Pass `--slug` explicitly. |

## Hard don'ts

- **Don't `publish` an app twice.** It builds a second, unrelated project. Use `update`.
- **Don't delete `registry.json`.** It holds the deployment ids that keep URLs stable.
- **Don't echo `token.json` or `.env`.** Both are chmod 600 for a reason.
- **Don't use an Embed link for an org-only app.** Google login can't render in an iframe.
  The skill only creates Redirect links.
- **Don't `--access anyone` (or `gmail`) anything internal.** `ANYONE_ANONYMOUS` is genuinely anyone.

## Limitations

- One HTML file per app. No multi-file bundles, no server-side Apps Script logic.
- Deployments cannot be deleted, only archived, and cannot change owner. If the deploying
  account is removed, the web app dies with it.
- The registry is per-machine.

---

**ZorCorp** · [github.com/ZorCorp](https://github.com/ZorCorp)
