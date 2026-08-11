#!/usr/bin/env python3
"""mcai-webapp — publish an HTML file as a Google Apps Script web app and front it
with an mcai.dev short link.

Stdlib only. No clasp, no Node, no MCP server. Two REST APIs:
  - script.googleapis.com/v1   (Apps Script: projects, content, versions, deployments)
  - mcai.dev/api/bookmarks.php (MasterLink: the short link)

Commands:
  setup    one-time credential setup (OAuth + mcai.dev API key)
  doctor   check that everything is configured and reachable
  publish  create a new web app and its short link
  update   push new content to an existing app, redeploying in place
  adopt    register an already-deployed script into the local registry
  list     show every app this machine has published

State lives in ~/.mcai-webapp (override with MCAI_WEBAPP_HOME):
  token.json     OAuth token          chmod 600, never printed
  .env           MCAI_API_KEY=...     chmod 600, never printed
  registry.json  non-secret app records
"""

import argparse
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

SCOPES = [
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.deployments",
]
GAS_API = "https://script.googleapis.com/v1/"
MCAI_BASE = os.environ.get("MCAI_BASE_URL", "https://mcai.dev").rstrip("/")
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/auth"

HOME = os.path.expanduser(os.environ.get("MCAI_WEBAPP_HOME", "~/.mcai-webapp"))
TOKEN_FILE = os.path.join(HOME, "token.json")
ENV_FILE = os.path.join(HOME, ".env")
REGISTRY_FILE = os.path.join(HOME, "registry.json")

ACCESS_DOMAIN = "DOMAIN"
ACCESS_PUBLIC = "ANYONE_ANONYMOUS"
ACCESS_GMAIL = "ANYONE"
ACCESS_PRIVATE = "MYSELF"

# CLI word → Apps Script manifest webapp.access value
ACCESS_CHOICES = {
    "org": ACCESS_DOMAIN,
    "gmail": ACCESS_GMAIL,
    "anyone": ACCESS_PUBLIC,
    "private": ACCESS_PRIVATE,
}
ACCESS_WORDS = {v: k for k, v in ACCESS_CHOICES.items()}
ACCESS_LABELS = {
    ACCESS_DOMAIN: "org — your Workspace domain only",
    ACCESS_GMAIL: "gmail — anyone signed into a Google account",
    ACCESS_PUBLIC: "anyone — public, no sign-in",
    ACCESS_PRIVATE: "private — only the deploying account",
}


def resolve_access(args, default):
    """--access wins; --public/--org-only kept as aliases; otherwise the default."""
    if getattr(args, "access", None):
        return ACCESS_CHOICES[args.access]
    if getattr(args, "public", False):
        return ACCESS_PUBLIC
    if getattr(args, "org_only", False):
        return ACCESS_DOMAIN
    return default


# ─────────────────────────────── errors & output ───────────────────────────────

class Fail(Exception):
    """A named, actionable failure. Message is printed; exit code 1."""


def die(name, message, fix=None):
    raise Fail(f"{name}: {message}" + (f"\n  → {fix}" if fix else ""))


def info(msg):
    print(msg, flush=True)


def ok(msg):
    print(f"✅ {msg}", flush=True)


def warn(msg):
    print(f"⚠️  {msg}", flush=True)


# ─────────────────────────────── small helpers ───────────────────────────────

def ensure_home():
    os.makedirs(HOME, mode=0o700, exist_ok=True)


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s) or "app"


def write_private(path, text):
    """Write a secret file atomically at chmod 600."""
    ensure_home()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def write_json(path, obj):
    ensure_home()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def http_json(method, url, body=None, headers=None, timeout=60):
    """Return (status, parsed_json_or_text). Never raises on HTTP status."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    # mcai.dev's host WAF blocks the default Python-urllib User-Agent with an HTML 403
    req.add_header("User-Agent", "mcai-webapp/0.1")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, raw
    except urllib.error.URLError as e:
        die("NETWORK_ERROR", f"{method} {url} failed: {e.reason}")


# ─────────────────────────────── credentials ───────────────────────────────

def find_client_secret():
    """Locate a Google Desktop OAuth client. Nothing ships with this plugin."""
    explicit = os.environ.get("MCAI_CLIENT_SECRET")
    if explicit:
        p = os.path.expanduser(explicit)
        if not os.path.exists(p):
            die("CLIENT_SECRET_NOT_FOUND", f"MCAI_CLIENT_SECRET points at {p}, which does not exist")
        return p

    gws_dir = os.environ.get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR")
    if gws_dir:
        p = os.path.join(os.path.expanduser(gws_dir), "client_secret.json")
        if os.path.exists(p):
            return p

    candidates = sorted(
        glob.glob(os.path.expanduser("~/.config/gws*/client_secret.json"))
    )
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        die(
            "MULTIPLE_CLIENT_SECRETS",
            "found several gws profiles: " + ", ".join(candidates),
            "pick one with  export MCAI_CLIENT_SECRET=<path>",
        )

    die(
        "NO_CLIENT_SECRET",
        "no Google Desktop OAuth client found",
        "create a Desktop OAuth client in your own GCP project, download the JSON, "
        "then  export MCAI_CLIENT_SECRET=/path/to/client_secret.json\n"
        "     (gws CLI users: it is normally ~/.config/gws-<profile>/client_secret.json — "
        "note that oauth-client.json in the same folder is a different, inactive client)",
    )


def load_client():
    path = find_client_secret()
    with open(path) as f:
        data = json.load(f)
    node = data.get("installed") or data.get("web")
    if not node:
        die("BAD_CLIENT_SECRET", f"{path} has no 'installed' key — is it a Desktop OAuth client?")
    if "client_id" not in node or "client_secret" not in node:
        die("BAD_CLIENT_SECRET", f"{path} is missing client_id/client_secret")
    return node


def open_in_browser(url):
    """Open the consent URL, preferring a named Chrome profile when configured."""
    profile = os.environ.get("MCAI_CHROME_PROFILE")
    if profile and sys.platform == "darwin":
        subprocess.run(
            ["open", "-na", "Google Chrome", "--args",
             f"--profile-directory={profile}", url],
            check=False,
        )
        return
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def run_oauth_flow():
    """Loopback installed-app flow. 'prompt' is deliberately omitted — prompt=none
    fails with immediate_failed on Desktop clients even when consent already exists."""
    client = load_client()
    holder = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if "code" in q:
                holder["code"] = q["code"][0]
                self.wfile.write("<h2>Done - you can close this tab.</h2>".encode())
            else:
                holder["error"] = q.get("error", ["unknown"])[0]
                self.wfile.write("<h2>Auth error - see the terminal.</h2>".encode())
            done.set()

        def log_message(self, *_a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    redirect = f"http://localhost:{port}"

    params = {
        "client_id": client["client_id"],
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
    }
    hint = os.environ.get("MCAI_GOOGLE_ACCOUNT")
    if hint:
        params["login_hint"] = hint

    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    info("Opening Google consent in your browser. If nothing happens, paste this URL yourself:")
    info(url)
    open_in_browser(url)

    if not done.wait(timeout=180):
        server.shutdown()
        die("AUTH_TIMEOUT", "no callback received within 180s",
            "make sure you completed consent in the browser profile signed in to your work account")
    server.shutdown()

    if "error" in holder:
        die("AUTH_ERROR", holder["error"],
            "if this says access_denied, your admin may block this OAuth client")

    body = urllib.parse.urlencode({
        "code": holder["code"],
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }).encode()
    try:
        with urllib.request.urlopen(TOKEN_URL, body, timeout=60) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        die("TOKEN_EXCHANGE_FAILED", e.read().decode("utf-8", "replace")[:500])

    if "refresh_token" not in tok:
        die("NO_REFRESH_TOKEN",
            "Google returned no refresh token",
            "revoke this app at myaccount.google.com/permissions and run setup again")

    write_private(TOKEN_FILE, json.dumps(tok))
    return tok


def access_token():
    """Exchange the stored refresh token for a fresh access token."""
    if not os.path.exists(TOKEN_FILE):
        die("NOT_AUTHENTICATED", "no OAuth token on this machine", "run /mcai-webapp:setup")
    client = load_client()
    with open(TOKEN_FILE) as f:
        tok = json.load(f)
    body = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": tok["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    try:
        with urllib.request.urlopen(TOKEN_URL, body, timeout=60) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        die("TOKEN_REFRESH_FAILED", detail,
            "the stored token is stale or revoked — run /mcai-webapp:setup again")


def read_env():
    if not os.path.exists(ENV_FILE):
        return {}
    out = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()   # last wins, so appends override
    return out


def mcai_key():
    key = os.environ.get("MCAI_API_KEY") or read_env().get("MCAI_API_KEY")
    if not key:
        die("NO_MCAI_API_KEY", "no mcai.dev API key configured",
            "run /mcai-webapp:setup, or generate one at " + MCAI_BASE + "/admin/ → Settings → API Keys")
    return key


# ─────────────────────────────── Apps Script API ───────────────────────────────

def gas(method, path, token, body=None):
    status, payload = http_json(
        method, GAS_API + path, body,
        headers={"Authorization": "Bearer " + token},
    )
    if status >= 400:
        text = json.dumps(payload)[:600] if isinstance(payload, (dict, list)) else str(payload)[:600]
        if "has not enabled the Apps Script API" in text or "script.google.com/home/usersettings" in text:
            die("APPS_SCRIPT_API_DISABLED",
                "the per-user Apps Script API toggle is off",
                "open https://script.google.com/home/usersettings as your work account, "
                "turn the Apps Script API on, wait a minute, then retry")
        if status == 403:
            die("PERMISSION_DENIED", text,
                "check you consented with script.projects + script.deployments scopes")
        die("APPS_SCRIPT_API_ERROR", f"HTTP {status} on {method} {path} — {text}")
    return payload


def manifest_for(access):
    return {
        "timeZone": os.environ.get("MCAI_TIMEZONE", "Asia/Hong_Kong"),
        "exceptionLogging": "STACKDRIVER",
        "runtimeVersion": "V8",
        "webapp": {"access": access, "executeAs": "USER_DEPLOYING"},
    }


def code_gs(title):
    """Apps Script strips <head> tags from served HTML, so the title and viewport
    have to be reapplied through HtmlService."""
    safe = title.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "function doGet() {\n"
        "  return HtmlService.createHtmlOutputFromFile('index')\n"
        f"    .setTitle('{safe}')\n"
        "    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0');\n"
        "}\n"
    )


def push_content(token, script_id, title, html, access):
    """PUT replaces every file in the project — always send the full set."""
    files = [
        {"name": "appsscript", "type": "JSON",
         "source": json.dumps(manifest_for(access), indent=2)},
        {"name": "Code", "type": "SERVER_JS", "source": code_gs(title)},
        {"name": "index", "type": "HTML", "source": html},
    ]
    gas("PUT", f"projects/{script_id}/content", token, {"files": files})


def web_app_url(token, script_id, deployment_id):
    dep = gas("GET", f"projects/{script_id}/deployments/{deployment_id}", token)
    for ep in dep.get("entryPoints", []):
        if ep.get("entryPointType") == "WEB_APP":
            url = ep.get("webApp", {}).get("url")
            if url:
                return url
    die("NO_WEB_APP_ENTRY_POINT",
        "the deployed version has no web app entry point",
        "the pushed appsscript.json is missing its lowercase \"webapp\" block")


# ─────────────────────────────── MasterLink API ───────────────────────────────

def mcai(method, path, body=None, key=None):
    status, payload = http_json(
        method, f"{MCAI_BASE}/api/{path}", body,
        headers={"X-API-Key": key or mcai_key()},
    )
    if status == 401:
        die("MCAI_UNAUTHORIZED", "mcai.dev rejected the API key",
            "generate a new one at " + MCAI_BASE + "/admin/ → Settings → API Keys, then rerun setup")
    if status >= 400:
        text = json.dumps(payload)[:400] if isinstance(payload, (dict, list)) else str(payload)[:400]
        die("MCAI_API_ERROR", f"HTTP {status} on {method} {path} — {text}")
    return payload


def probe_mcai_key(key):
    """Verify a key without creating anything: PUT against an id that cannot exist.
    Auth is checked before the row lookup, so 401 means bad key and anything else
    means the key was accepted."""
    status, _ = http_json(
        "PUT", f"{MCAI_BASE}/api/bookmarks.php?id=-1",
        {"description": "mcai-webapp key probe"},
        headers={"X-API-Key": key},
    )
    return status != 401


def slug_taken(slug):
    status, payload = http_json("GET", f"{MCAI_BASE}/api/bookmarks.php")
    if status >= 400 or not isinstance(payload, dict):
        return None  # cannot tell; let the create call decide
    for b in payload.get("bookmarks", []):
        if b.get("slug") == slug:
            return b
    return None


def create_short_link(slug, name, target_url, description, icon, category_id):
    body = {
        "name": name,
        "slug": slug,
        "target_url": target_url,
        "link_type": "redirect",
        "icon_type": "library",
        "icon_value": icon,
        "is_visible": True,
    }
    if description:
        body["description"] = description
    if category_id is not None:
        body["category_id"] = category_id
    return mcai("POST", "bookmarks.php", body)


def verify_short_link(slug, expect):
    """Follow nothing — just confirm mcai.dev/<slug> 301s to the web app."""
    url = f"{MCAI_BASE}/{slug}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_a, **_k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, method="GET",
                         headers={"User-Agent": "mcai-webapp/0.1"}), timeout=30) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")
    except urllib.error.URLError:
        return None, None


# ─────────────────────────────── registry ───────────────────────────────

def load_registry():
    if not os.path.exists(REGISTRY_FILE):
        return {"version": 1, "apps": {}}
    try:
        with open(REGISTRY_FILE) as f:
            reg = json.load(f)
    except json.JSONDecodeError:
        die("REGISTRY_CORRUPT", f"{REGISTRY_FILE} is not valid JSON",
            "fix or delete it — deleting loses your deploymentId records, so back it up first")
    reg.setdefault("version", 1)
    reg.setdefault("apps", {})
    return reg


def save_registry(reg):
    write_json(REGISTRY_FILE, reg)


def get_app(reg, slug):
    app = reg["apps"].get(slug)
    if not app:
        known = ", ".join(sorted(reg["apps"])) or "(none)"
        die("UNKNOWN_APP", f"no app registered under slug '{slug}'",
            f"known slugs: {known}. Use /mcai-webapp:adopt to register an existing script.")
    return app


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ─────────────────────────────── commands ───────────────────────────────

def cmd_setup(args):
    ensure_home()
    info("mcai-webapp setup\n")

    if sys.version_info < (3, 8):
        die("PYTHON_TOO_OLD", f"need Python 3.8+, found {sys.version.split()[0]}")
    ok(f"python {sys.version.split()[0]}")

    path = find_client_secret()
    ok(f"OAuth client: {path.replace(os.path.expanduser('~'), '~')}")

    if os.path.exists(TOKEN_FILE) and not args.force:
        ok("OAuth token already present (use --force to re-authorise)")
    else:
        info("\nA browser window will open for Google consent.")
        info("Sign in with your WORK account and click Continue.\n")
        run_oauth_flow()
        ok("OAuth token saved (chmod 600)")

    key = args.api_key or os.environ.get("MCAI_API_KEY") or read_env().get("MCAI_API_KEY")
    if not key:
        info(f"\nGenerate an API key at {MCAI_BASE}/admin/ → Settings → API Keys.")
        try:
            key = input("Paste the mcai.dev API key: ").strip()
        except EOFError:
            key = ""
        if not key:
            die("NO_MCAI_API_KEY", "no key entered",
                f"rerun with  --api-key <key>  once you have one from {MCAI_BASE}/admin/")

    if probe_mcai_key(key):
        existing = read_env()
        existing["MCAI_API_KEY"] = key
        write_private(ENV_FILE, "".join(f"{k}={v}\n" for k, v in existing.items()))
        ok("mcai.dev API key verified and saved (chmod 600)")
    else:
        die("MCAI_UNAUTHORIZED", "mcai.dev rejected that key",
            f"check it at {MCAI_BASE}/admin/ → Settings → API Keys")

    info("\n🎉 Setup complete. Publish something with:")
    info('   /mcai-webapp:publish ./page.html --title "My Page" --slug mypage')


def cmd_doctor(_args):
    problems = 0
    info("mcai-webapp doctor\n")

    try:
        path = find_client_secret()
        ok(f"OAuth client: {path.replace(os.path.expanduser('~'), '~')}")
    except Fail as e:
        print(f"❌ {e}")
        problems += 1

    if os.path.exists(TOKEN_FILE):
        try:
            access_token()
            ok("OAuth token refreshes cleanly")
        except Fail as e:
            print(f"❌ {e}")
            problems += 1
    else:
        print("❌ NOT_AUTHENTICATED: no token — run /mcai-webapp:setup")
        problems += 1

    try:
        if probe_mcai_key(mcai_key()):
            ok("mcai.dev API key accepted")
        else:
            print("❌ MCAI_UNAUTHORIZED: mcai.dev rejected the stored key")
            problems += 1
    except Fail as e:
        print(f"❌ {e}")
        problems += 1

    reg = load_registry()
    ok(f"registry: {len(reg['apps'])} app(s) recorded")

    info("")
    if problems:
        info(f"{problems} problem(s) — fix the ❌ lines above, then rerun.")
        sys.exit(1)
    ok("all checks passed")


def cmd_publish(args):
    html_path = os.path.abspath(os.path.expanduser(args.html))
    if not os.path.exists(html_path):
        die("HTML_NOT_FOUND", f"{html_path} does not exist")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    title = args.title or os.path.splitext(os.path.basename(html_path))[0]
    slug = args.slug or slugify(title)
    access = resolve_access(args, ACCESS_DOMAIN)

    reg = load_registry()
    if slug in reg["apps"] and not args.force:
        die("SLUG_ALREADY_PUBLISHED", f"'{slug}' is already in the local registry",
            f"use /mcai-webapp:update --slug {slug} to push new content")

    existing = slug_taken(slug)
    if existing and not args.force:
        die("SLUG_TAKEN_ON_MCAI",
            f"{MCAI_BASE}/{slug} already exists (bookmark id {existing.get('id')})",
            "choose another --slug, or adopt the existing link with /mcai-webapp:adopt")

    key = mcai_key()          # fail before creating anything in Google
    token = access_token()

    info(f"Creating Apps Script project “{title}” …")
    proj = gas("POST", "projects", token, {"title": title})
    script_id = proj["scriptId"]
    ok(f"scriptId {script_id}")

    info("Pushing content …")
    push_content(token, script_id, title, html, access)

    ver = gas("POST", f"projects/{script_id}/versions", token,
              {"description": args.message or "Initial publish"})
    version_number = ver["versionNumber"]
    ok(f"version {version_number}")

    info("Deploying …")
    dep = gas("POST", f"projects/{script_id}/deployments", token, {
        "versionNumber": version_number,
        "manifestFileName": "appsscript",
        "description": f"{ACCESS_WORDS[access]} web app v{version_number}",
    })
    deployment_id = dep["deploymentId"]
    exec_url = web_app_url(token, script_id, deployment_id)
    ok(f"deploymentId {deployment_id}")

    info(f"Creating {MCAI_BASE}/{slug} …")
    created = create_short_link(
        slug, args.link_name or title, exec_url,
        args.description, args.icon, args.category_id,
    )

    reg["apps"][slug] = {
        "slug": slug,
        "title": title,
        "scriptId": script_id,
        "deploymentId": deployment_id,
        "execUrl": exec_url,
        "shortUrl": f"{MCAI_BASE}/{slug}",
        "access": access,
        "bookmarkId": created.get("id"),
        "source": html_path,
        "version": version_number,
        "createdAt": now(),
        "updatedAt": now(),
    }
    save_registry(reg)

    status, location = verify_short_link(slug, exec_url)
    info("")
    if status in (301, 302) and location:
        ok(f"{MCAI_BASE}/{slug} → {status} → {location}")
    else:
        warn(f"could not confirm the redirect (got {status}). The app is deployed; "
             f"check the link at {MCAI_BASE}/admin/")

    info("")
    info(f"  Short link   {MCAI_BASE}/{slug}")
    info(f"  Web app      {exec_url}")
    info(f"  Access       {ACCESS_LABELS[access]}")
    info(f"  scriptId     {script_id}")
    info(f"  deploymentId {deployment_id}")
    info("")
    info(f"Update it later with:  /mcai-webapp:update --slug {slug}")


def cmd_update(args):
    reg = load_registry()
    app = get_app(reg, args.slug)

    html_path = os.path.abspath(os.path.expanduser(args.html)) if args.html else app.get("source")
    if not html_path or not os.path.exists(html_path):
        die("HTML_NOT_FOUND",
            f"source file {html_path} is missing",
            "pass the file explicitly:  /mcai-webapp:update --slug " + args.slug + " ./page.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    title = args.title or app["title"]
    access = resolve_access(args, app.get("access", ACCESS_DOMAIN))

    token = access_token()
    script_id, deployment_id = app["scriptId"], app["deploymentId"]

    info("Pushing content …")
    push_content(token, script_id, title, html, access)

    ver = gas("POST", f"projects/{script_id}/versions", token,
              {"description": args.message or f"Update {now()}"})
    version_number = ver["versionNumber"]
    ok(f"version {version_number}")

    info(f"Redeploying in place (deployment {deployment_id}) …")
    gas("PUT", f"projects/{script_id}/deployments/{deployment_id}", token, {
        "deploymentConfig": {
            "scriptId": script_id,
            "versionNumber": version_number,
            "manifestFileName": "appsscript",
            "description": args.message or f"v{version_number}",
        }
    })

    new_url = web_app_url(token, script_id, deployment_id)
    if new_url != app["execUrl"]:
        warn("THE WEB APP URL CHANGED — this should not happen on an in-place redeploy.")
        warn(f"  was: {app['execUrl']}")
        warn(f"  now: {new_url}")
        if app.get("bookmarkId"):
            info(f"Repointing {MCAI_BASE}/{app['slug']} at the new URL …")
            mcai("PUT", f"bookmarks.php?id={app['bookmarkId']}", {"target_url": new_url})
            ok("short link repointed")
        else:
            warn(f"No bookmarkId recorded — update {MCAI_BASE}/{app['slug']} by hand.")
        app["execUrl"] = new_url
    else:
        ok("web app URL unchanged — the short link needs no edit")

    app["title"] = title
    app["access"] = access
    app["source"] = html_path
    app["version"] = version_number
    app["updatedAt"] = now()
    save_registry(reg)

    info("")
    info(f"  Short link {app['shortUrl']}   (unchanged)")
    info(f"  Version    {version_number}")


def cmd_adopt(args):
    token = access_token()
    script_id = args.script_id

    deployment_id = args.deployment_id
    if not deployment_id:
        listing = gas("GET", f"projects/{script_id}/deployments", token)
        web_deps = [
            d for d in listing.get("deployments", [])
            if any(ep.get("entryPointType") == "WEB_APP" for ep in d.get("entryPoints", []))
        ]
        if not web_deps:
            die("NO_WEB_APP_DEPLOYMENT", f"script {script_id} has no web app deployment")
        if len(web_deps) > 1:
            lines = "\n".join(
                f"    {d['deploymentId']}  {d.get('deploymentConfig', {}).get('description', '')}"
                for d in web_deps
            )
            die("MULTIPLE_DEPLOYMENTS",
                f"script {script_id} has {len(web_deps)} web app deployments",
                "pass the right one with --deployment-id:\n" + lines)
        deployment_id = web_deps[0]["deploymentId"]

    exec_url = web_app_url(token, script_id, deployment_id)
    ok(f"found web app {exec_url}")

    slug = args.slug
    reg = load_registry()
    existing = slug_taken(slug)
    bookmark_id = None

    if existing:
        bookmark_id = existing.get("id")
        if existing.get("target_url") != exec_url:
            info(f"Repointing existing {MCAI_BASE}/{slug} at this web app …")
            mcai("PUT", f"bookmarks.php?id={bookmark_id}", {"target_url": exec_url})
        ok(f"reusing short link {MCAI_BASE}/{slug}")
    else:
        info(f"Creating {MCAI_BASE}/{slug} …")
        created = create_short_link(
            slug, args.title or slug, exec_url, args.description, args.icon, args.category_id
        )
        bookmark_id = created.get("id")

    reg["apps"][slug] = {
        "slug": slug,
        "title": args.title or slug,
        "scriptId": script_id,
        "deploymentId": deployment_id,
        "execUrl": exec_url,
        "shortUrl": f"{MCAI_BASE}/{slug}",
        "access": resolve_access(args, ACCESS_DOMAIN),
        "bookmarkId": bookmark_id,
        "source": os.path.abspath(os.path.expanduser(args.html)) if args.html else None,
        "version": None,
        "createdAt": now(),
        "updatedAt": now(),
    }
    save_registry(reg)
    ok(f"adopted '{slug}' into the registry")
    if not args.html:
        warn("no --html recorded, so /mcai-webapp:update will need the file passed explicitly")


def cmd_list(args):
    reg = load_registry()
    apps = reg["apps"]
    if not apps:
        info("Nothing published from this machine yet.")
        info('Try:  /mcai-webapp:publish ./page.html --title "My Page" --slug mypage')
        return

    if args.json:
        print(json.dumps(reg, indent=2))
        return

    rows = []
    for slug in sorted(apps):
        a = apps[slug]
        access = ACCESS_WORDS.get(a.get("access"), "org")
        state = ""
        if args.check:
            status, location = verify_short_link(slug, a.get("execUrl"))
            if status in (301, 302) and location == a.get("execUrl"):
                state = "✅ ok"
            elif status in (301, 302):
                state = "⚠️ points elsewhere"
            elif status is None:
                state = "❌ unreachable"
            else:
                state = f"❌ {status}"
        rows.append((slug, a.get("title", ""), access, a.get("updatedAt", ""), state))

    headers = ["Slug", "Title", "Access", "Updated", "Link"] if args.check else \
              ["Slug", "Title", "Access", "Updated"]
    widths = [len(h) for h in headers]
    trimmed = [r[:len(headers)] for r in rows]
    for r in trimmed:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    def line(cells):
        return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    print(line(headers))
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for r in trimmed:
        print(line(r))

    print()
    for slug in sorted(apps):
        print(f"{MCAI_BASE}/{slug}  →  {apps[slug].get('execUrl')}")


# ─────────────────────────────── CLI ───────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="mcai-webapp", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="one-time credential setup")
    s.add_argument("--api-key", help="mcai.dev API key (otherwise prompted)")
    s.add_argument("--force", action="store_true", help="re-run the OAuth flow even if a token exists")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("doctor", help="check credentials and connectivity")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("publish", help="create a new web app and short link")
    s.add_argument("html", help="path to the HTML file to publish")
    s.add_argument("--title", help="web app title (default: the filename)")
    s.add_argument("--slug", help="mcai.dev slug (default: slugified title)")
    s.add_argument("--description", help="description shown on the mcai.dev card")
    s.add_argument("--link-name", help="bookmark name on mcai.dev (default: the title)")
    s.add_argument("--access", choices=sorted(ACCESS_CHOICES),
                   help="who can open it: org (Workspace domain, default), "
                        "gmail (any Google account), anyone (no sign-in), private (only you)")
    s.add_argument("--public", action="store_true",
                   help="deprecated alias for --access anyone")
    s.add_argument("--icon", default="lucide:app-window", help="lucide icon for the mcai.dev card")
    s.add_argument("--category-id", type=int, help="mcai.dev category id")
    s.add_argument("--message", help="version description")
    s.add_argument("--force", action="store_true", help="publish even if the slug looks taken")
    s.set_defaults(func=cmd_publish)

    s = sub.add_parser("update", help="push new content, redeploying in place")
    s.add_argument("--slug", required=True, help="slug of the app to update")
    s.add_argument("html", nargs="?", help="HTML file (default: the one recorded at publish time)")
    s.add_argument("--title", help="change the web app title")
    s.add_argument("--message", help="version description")
    s.add_argument("--access", choices=sorted(ACCESS_CHOICES),
                   help="switch access level: org, gmail, anyone, or private")
    s.add_argument("--public", action="store_true", help="deprecated alias for --access anyone")
    s.add_argument("--org-only", action="store_true", help="deprecated alias for --access org")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("adopt", help="register an already-deployed script")
    s.add_argument("--script-id", required=True)
    s.add_argument("--deployment-id", help="auto-detected when the script has exactly one web app deployment")
    s.add_argument("--slug", required=True, help="mcai.dev slug to create or reuse")
    s.add_argument("--title")
    s.add_argument("--description")
    s.add_argument("--html", help="local source file, so future updates can find it")
    s.add_argument("--access", choices=sorted(ACCESS_CHOICES),
                   help="record its access level: org (default), gmail, anyone, or private")
    s.add_argument("--public", action="store_true", help="deprecated alias for --access anyone")
    s.add_argument("--icon", default="lucide:app-window")
    s.add_argument("--category-id", type=int)
    s.set_defaults(func=cmd_adopt)

    s = sub.add_parser("list", help="show every app published from this machine")
    s.add_argument("--check", action="store_true", help="probe each short link and report its status")
    s.add_argument("--json", action="store_true", help="dump the raw registry")
    s.set_defaults(func=cmd_list)

    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except Fail as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
