---
description: Turn a prompt into a draft HTML page, open it locally for review, and iterate until the user approves — publishing is a separate, explicit step.
argument-hint: "<what the page should be> [--slug <slug>] [--out <file.html>]"
---

Usage: `/mcai-webapp:draft <description of the page> [--slug <slug>] [--out <file.html>]`

This is **step one** of the pipeline: prompt → draft → review → publish. It produces a local
HTML file and never touches Google or mcai.dev.

1. **Generate** a single, fully self-contained HTML file from the user's prompt:
   - Everything inline — CSS and JS in the file, no CDN links, no external fonts, no
     fetch/XHR. Apps Script serves one HTML file, byte for byte, inside an iframe on
     `script.googleusercontent.com`; anything external is a liability.
   - Include `<meta name="viewport" content="width=device-width, initial-scale=1.0">` and a
     real `<title>` — but know that Apps Script strips head meta tags; the skill's `doGet`
     re-adds the viewport and title at publish time, so keep them in the file anyway for
     local preview fidelity.
   - If the page keeps state (checkboxes, progress), use `localStorage` with a versioned
     key like `<slug>_v1`.
2. **Save** it where the user can find it: `--out` if given, else `./<slug>.html` in the
   current directory, else a slugified name from the prompt. This path becomes the app's
   recorded source at publish time, so put it somewhere permanent — never in `/tmp`.
3. **Open it for review** with `open <file>` (macOS default browser) and tell the user what
   you built and what to look at.
4. **Iterate.** Edit the file on feedback and ask them to refresh. Repeat until they approve.
5. **On approval, ask two questions before handing off** to `/mcai-webapp:publish`:
   - **Access level** — never assume. `org` (Workspace domain only), `gmail` (any signed-in
     Google account), `anyone` (public, no sign-in), `private` (only the deployer).
     Anything with internal content (credentials, names, internal URLs) must not go out as
     `anyone` or `gmail` without an explicit, informed yes.
   - **Slug** — short and memorable; confirm rather than derive silently.

Then run:

`/mcai-webapp:publish <file.html> --title "..." --slug <slug> --access <level>`

Do not publish in the same breath as drafting. The review pause is the point of this command.
