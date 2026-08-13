# Form templates

Four starting points for a form page. Same structure and behaviour in each — only the
visual system differs, so switching style is a swap, not a rewrite.

| File | Reads as |
|---|---|
| `google.html` | Material — outlined fields, notched floating labels, one blue accent |
| `apple.html` | HIG — grouped inset rows, large title, system font, pill button |
| `minimal.html` | Swiss — black on white, rules instead of boxes, tracked uppercase labels |
| `corporate.html` | Official document — serif headings, muted navy, numbered sections |

## How the responses reach a spreadsheet

A Google Sheet has no public write endpoint, so a page cannot write to one directly. These
templates post to a **Google Form**, which is designed to accept submissions from strangers
and writes them into its own linked Sheet. No Apps Script permissions, no authorisation
step, nothing for the reader to sign in to.

Before publishing, replace two things:

1. `FORM_ACTION` — the Form's `.../formResponse` URL (the `viewform` URL with the last
   path segment swapped).
2. Every `entry.XXXXXXXXX` — one per question, taken from that Form.

The entry ids are not guessable. Read them from the Form's public page: it embeds a
`FB_PUBLIC_LOAD_DATA_` blob that pairs each question's text with its id. Always show the
question-to-field mapping to the author before publishing — a swapped pair puts answers in
the wrong column, and nothing about it looks wrong afterwards.

## Two things worth knowing

**Submission cannot be confirmed.** Google Forms sends no CORS headers, so the response is
opaque. A resolved `fetch` means the request left the browser, not that a row was written.
The templates say "recorded" on that basis; there is no way to do better from a page like
this.

**The endpoint is public.** Anyone can read `FORM_ACTION` from the page source and post to
it directly, bypassing the form. Fine for collecting internal responses; not fine if you
need submissions to be trustworthy, rate-limited, or restricted to your organisation. That
needs server-side code, which these templates deliberately do not use.

## Constraints they already satisfy

- **No external requests.** Everything is inline — Apps Script serves one file, and any
  CDN, webfont, or remote image is an extra origin that may be blocked or slow.
- **Light only.** Deliberately, and consistently across all four: the author previews on
  their own machine, and a reader whose OS is dark should not be looking at a version
  nobody checked. Add a `prefers-color-scheme` block if you decide otherwise.
- `<title>` and viewport are present. Apps Script strips head tags when serving, and the
  skill re-applies both at publish time, but keep them for local preview.
