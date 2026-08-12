#!/bin/sh
# Print the path of a usable Python 3.8+, installing one if necessary.
#
# macOS ships /usr/bin/python3 as a stub that belongs to the Xcode Command Line
# Tools. On a machine without CLT, invoking it pops the "install developer
# tools" dialog — 1.3 GB the user did not ask for. So that candidate is only
# tried when xcode-select confirms CLT is actually present.
#
# Everything this script prints to stdout is the interpreter path. Diagnostics
# go to stderr.

set -eu

PY_VERSION=3.14.7
PY_SHA256=70c5239ad2d62925d2947e46921d0ddd3d35be3d2f0a2d50db33da507dbcb419
PY_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-macos11.pkg"

log() { printf '%s\n' "$*" >&2; }

usable() {
    [ -x "$1" ] || return 1
    # find_python() runs inside $( ), so anything the candidate writes to
    # stdout here (a pyenv/asdf/conda shim's startup banner, a wrapper's
    # notice, etc.) would otherwise be captured and glued onto the front of
    # the path this script prints. Discard both streams — only the exit
    # status of this probe matters. Also redirect stdin from /dev/null: this
    # script has no TTY (invoked from a Python subprocess), so a wrapper that
    # reads stdin would otherwise hang here forever with no timeout.
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' </dev/null >/dev/null 2>&1
}

find_python() {
    for p in /Library/Frameworks/Python.framework/Versions/*/bin/python3; do
        usable "$p" && { printf '%s' "$p"; return 0; }
    done
    for p in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        usable "$p" && { printf '%s' "$p"; return 0; }
    done
    # Only safe once CLT is confirmed present — see the header comment. Never
    # probe /usr/bin/python3 before this check: doing so on a machine without
    # CLT triggers the "install command line developer tools" system dialog.
    if xcode-select -p >/dev/null 2>&1; then
        usable /usr/bin/python3 && { printf '%s' /usr/bin/python3; return 0; }
    fi
    return 1
}

if FOUND=$(find_python); then
    printf '%s\n' "$FOUND"
    exit 0
fi

log "No usable Python 3.8+ found. Installing Python ${PY_VERSION} from python.org."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM
PKG="$TMP/python.pkg"

curl -fsSL "$PY_URL" -o "$PKG" || {
    log "PYTHON_DOWNLOAD_FAILED: could not download $PY_URL"
    log "  → check the network or a proxy, then retry"
    exit 1
}

ACTUAL=$(shasum -a 256 "$PKG" | awk '{print $1}')
if [ "$ACTUAL" != "$PY_SHA256" ]; then
    log "PYTHON_CHECKSUM_MISMATCH: expected $PY_SHA256, got $ACTUAL"
    log "  → the download was corrupted or tampered with; nothing was installed"
    exit 1
fi

# osascript, not sudo: this script is invoked without a TTY (from a Python
# subprocess), so sudo has no terminal to prompt on and would just hang or
# fail. osascript's "with administrator privileges" raises the native macOS
# authentication dialog instead, which works headless-from-stdin.
if ! osascript -e "do shell script \"installer -pkg '$PKG' -target /\" \
     with prompt \"mcai-webapp needs to install Python 3\" \
     with administrator privileges" >/dev/null 2>&1; then
    log "INSTALL_CANCELLED or NOT_ADMIN: the Python installer did not run"
    log "  → an administrator can install it manually:"
    log "     sudo installer -pkg <python-${PY_VERSION}-macos11.pkg> -target /"
    exit 1
fi

if FOUND=$(find_python); then
    printf '%s\n' "$FOUND"
    exit 0
fi

log "PYTHON_INSTALL_FAILED: installer finished but no usable Python was found"
exit 1
