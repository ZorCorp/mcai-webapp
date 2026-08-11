# Publishing mcai-webapp to ZorCorp/zorskill

Run these from a shell (or paste the prompt at the bottom into Claude Code). The plugin
source is complete at `~/Dev/mcaidemo/mcai-webapp/` — these steps only move it to GitHub and
register it in the marketplace.

**Follow zorskill-dev, not the zorskill README.** The README's Steps 4–6 (hand-editing
`marketplace.json` and the Skills table) are stale and explicitly forbidden by
`zorskill/CLAUDE.md`. Let the tooling do it.

---

## 1 · Create the empty repo

```bash
gh api orgs/ZorCorp/repos -X POST \
  -f name=mcai-webapp \
  -f description="Publish an HTML file as a Google Apps Script web app with an mcai.dev short link" \
  -F private=false
```

Verify:

```bash
gh api repos/ZorCorp/mcai-webapp --jq '.full_name'
# → ZorCorp/mcai-webapp
```

## 2 · Register it in the marketplace

```
/zorskill-dev:new mcai-webapp --description "Publish an HTML file as a Google Apps Script web app under your own Workspace account and give it a branded mcai.dev short link — org-only or public. No clasp, no Node, no MCP server. Updates redeploy in place so the URL never changes."
```

This clones the (empty) repo as a submodule at `plugins/mcai-webapp`, scaffolds skeleton
files, adds the `marketplace.json` entry, and stages the change in zorskill. It does **not**
push to the plugin repo — that's step 3.

> ⚠️ The scaffolder writes its own skeleton `plugin.json` and `SKILL.md`. **Ours are the real
> ones** — overwrite the skeletons in step 3, don't merge them.

## 3 · Fill the plugin repo with the real source

Replace `<submodule-path>` with wherever `/zorskill-dev:new` put it (typically
`/tmp/zorskill-update/plugins/mcai-webapp` or your local zorskill clone).

```bash
SRC=~/Dev/mcaidemo/mcai-webapp
DST=<submodule-path>

# our files win over the scaffold
rsync -av --exclude '.git' --exclude 'PUBLISH.md' "$SRC"/ "$DST"/

cd "$DST"
git add -A
git commit -m "feat: initial release — publish HTML as an Apps Script web app with an mcai.dev short link"
git push origin HEAD:main
```

Sanity check before pushing:

```bash
test -f .claude-plugin/plugin.json && jq -r '.name + " " + .version' .claude-plugin/plugin.json
grep -c 'zorskill-release' CLAUDE.md      # must be 2 (BEGIN + END markers)
ls commands/                              # adopt list publish setup update
python3 -m py_compile scripts/mcai_webapp.py && echo "engine compiles"
```

## 4 · Commit the marketplace side

```bash
cd <your zorskill clone>
git add .gitmodules plugins/mcai-webapp .claude-plugin/marketplace.json README.md
git commit -m "feat: add mcai-webapp"
git push origin main
```

## 5 · Cut the release

From the **plugin** repo:

```bash
cd <submodule-path>
gh workflow run release.yml -f version=0.1.0
```

The workflow bumps `plugin.json`, commits `chore: release v0.1.0`, and tags `v0.1.0`. The
marketplace drift scanner carries it in within ~30 min. To skip the wait:

```
/zorskill-dev:release mcai-webapp 0.1.0
```

## 6 · Verify

```
/zorskill-dev:check
```

Then, from a clean machine:

```
/plugin marketplace add ZorCorp/zorskill
/plugin install mcai-webapp
/mcai-webapp:setup
```

---

## Before you release: prove the update path

`0.1.0` ships on the assumption that `deployments.update` preserves the `/exec` URL. That's
what Google's docs and clasp's source say, but the handover session never actually
redeployed — so it has not been tested against your account.

Register the app you already deployed:

```bash
python3 ~/Dev/mcaidemo/mcai-webapp/scripts/mcai_webapp.py adopt \
  --script-id 1IuPni22wuE21O2D8067d24eVKWVY_UWQdcf1Nc6NgHQ_iivzgtGOYETk \
  --slug orientation \
  --title "Master Concept — New Joiner Day 1 Setup" \
  --html <path to the deck html>
```

Then change one visible character in the HTML and:

```bash
python3 ~/Dev/mcaidemo/mcai-webapp/scripts/mcai_webapp.py update --slug orientation
```

**Expected:** `✅ web app URL unchanged — the short link needs no edit`, and
`mcai.dev/orientation` still serves the deck with your edit visible.

If it instead warns that the URL changed, don't release — the whole stable-link design needs
rethinking and the bug is in the `deployments.update` call.

---

## Paste-into-Claude-Code prompt

```
Publish the plugin at ~/Dev/mcaidemo/mcai-webapp to the ZorCorp zorskill marketplace,
following ~/Dev/mcaidemo/mcai-webapp/PUBLISH.md exactly.

Before step 5, run the "prove the update path" section at the bottom and show me the
output — do not cut the release until I confirm the URL stayed the same.

Use the zorskill-dev tooling for marketplace registration. Do not hand-edit
marketplace.json or the zorskill README.
```
