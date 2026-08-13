---
description: Turn a prompt into a draft HTML page, open it locally for review, and iterate until the user approves — publishing is a separate, explicit step.
argument-hint: "<what the page should be> [--slug <slug>] [--out <file.html>]"
---

Usage: `/mcai-webapp:draft <description of the page> [--slug <slug>] [--out <file.html>]`

This is **step one** of the pipeline: prompt → draft → review → publish. It produces a local
HTML file and never touches Google or mcai.dev.

0. **If the page is a form, start from a template.** Four live in the plugin's
   `templates/form/` directory — `google` (Material), `apple` (HIG), `minimal` (Swiss),
   `corporate` (official document). Ask which look they want rather than picking one, then
   read that file and fill it in; they share a structure, so the choice is cosmetic and
   reversible.

   The responses land in a Google Sheet by way of a **Google Form** — a Sheet has no public
   write endpoint, so the page posts to a Form, which writes to its own linked Sheet. Ask
   the user for the Form's link, read its public page, and pull each question's
   `entry.XXXXXXXXX` id out of the `FB_PUBLIC_LOAD_DATA_` blob it embeds. **Show the
   question-to-field mapping and get it confirmed before publishing** — a swapped pair puts
   answers in the wrong column and nothing looks wrong afterwards.

   Tell them plainly that anyone can read the Form endpoint from the page source and post
   to it directly. That is fine for collecting internal responses and not fine if
   submissions have to be trustworthy or restricted.

   `templates/form/README.md` covers the rest. For anything that is not a form, carry on
   from step 1.

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
2. **Save it on the user's Mac.** In Cowork that means Desktop Commander's file-write tool —
   the built-in Write/Edit tools target the sandbox, so a file written with them disappears
   with the session and `publish`, which runs on the Mac, could never read it. In Claude Code
   the Write tool is already local.

   Use `--out` if given, else `<state dir>/drafts/<slug>.html`, where the state dir is
   `$MCAI_WEBAPP_HOME` when that is set and `~/.mcai-webapp` otherwise. Create it with
   `(umask 077 && mkdir -p "<state dir>/drafts")` — the same directory holds `token.json`
   and `.env`, so it must not end up world-listable.

   Avoid `~/Desktop`, `~/Documents` and `~/Downloads`: macOS puts all three behind Full Disk
   Access, and a terminal connector without that permission cannot write there. This path
   becomes the app's recorded source at publish time, so it must be permanent — never `/tmp`.

   Confirm the write landed by listing the file on the Mac before moving on.
3. **Open it for review** by running `open <file>` **on the Mac** — through the same local
   terminal, never a sandboxed shell, or the tab opens somewhere the user cannot see. Tell
   them what you built and what to look at.
4. **Iterate.** Edit the file **on the Mac**, through the same local tool used to write it,
   and ask the user to refresh the tab. Repeat until they approve. Editing a sandbox copy
   would leave the file the user is looking at untouched.
5. **On approval, ask two questions before handing off** to `/mcai-webapp:publish`:
   - **Access level** — never assume. `org` (Workspace domain only), `gmail` (any signed-in
     Google account), `anyone` (public, no sign-in), `private` (only the deployer).
     Anything with internal content (credentials, names, internal URLs) must not go out as
     `anyone` or `gmail` without an explicit, informed yes.
   - **Slug** — short and memorable; confirm rather than derive silently.

Then run:

`/mcai-webapp:publish <file.html> --title "..." --slug <slug> --access <level>`

Do not publish in the same breath as drafting. The review pause is the point of this command.
