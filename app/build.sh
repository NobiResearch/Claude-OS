#!/bin/bash
# Builds "build/Claude OS.app", the native shell around `cos serve`, with
# "Claude OS Music Helper.app" (the only thing that ever holds an Accessibility grant)
# embedded in Contents/Helpers.
#
#   app/build.sh             build and sign build/Claude OS.app
#   app/build.sh --install   also copy it to ~/Applications/Claude OS.app
#   app/build.sh --open      also open it (the installed copy with --install)
#
# The bundle's Info.plist bakes in this checkout's absolute path and your current $PATH
# (apps started from Finder don't get your shell's PATH). Both are machine-specific, so
# they live only in the built bundle; build/ is git-ignored. Rebuild if the repo moves.
#
# Signing: macOS ties privacy grants (Accessibility, Location) to the code signature. An
# ad-hoc signature is new on every build, so grants reset; an Apple Development identity
# keeps them. The identity is chosen at build time and never written to any file:
#   COS_SIGN_IDENTITY=adhoc        ad hoc
#   COS_SIGN_IDENTITY=<sha1|name>  that identity
#   CLAUDE_OS_DAEMON set           ad hoc (a headless run must never meet a keychain prompt)
#   otherwise                      the first valid "Apple Development" identity, by SHA-1
#                                  (ad hoc if there is none)
set -euo pipefail

usage() { sed -n '2,21s/^# \{0,1\}//p' "$0"; }

INSTALL=0
OPEN=0
for arg in "$@"; do
    case "$arg" in
        --install) INSTALL=1 ;;
        --open) OPEN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "build.sh: unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

VERSION="$(sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' lib/cos/__init__.py)"
if [ -z "$VERSION" ]; then
    echo "build.sh: couldn't read __version__ from lib/cos/__init__.py" >&2
    exit 1
fi

echo "==> swift build (release)"
swift build -c release --package-path app
BIN_DIR="$(swift build -c release --package-path app --show-bin-path)"

APP="build/Claude OS.app"
HELPER="$APP/Contents/Helpers/Claude OS Music Helper.app"
echo "==> assembling $APP ($VERSION)"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$HELPER/Contents/MacOS" "$HELPER/Contents/Resources"
cp "$BIN_DIR/ClaudeOS" "$APP/Contents/MacOS/ClaudeOS"
cp "$BIN_DIR/ClaudeOSMusicHelper" "$HELPER/Contents/MacOS/ClaudeOSMusicHelper"

# The icon only changes when icon.swift does, so cache the .icns between builds.
ICNS="build/AppIcon.icns"
if [ ! -f "$ICNS" ] || [ app/icon.swift -nt "$ICNS" ]; then
    echo "==> drawing the icon"
    ICONSET="build/AppIcon.iconset"
    rm -rf "$ICONSET"
    swift app/icon.swift "$ICONSET"
    iconutil -c icns "$ICONSET" -o "$ICNS"
    rm -rf "$ICONSET"
fi
cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"
cp "$ICNS" "$HELPER/Contents/Resources/AppIcon.icns"

# plistlib does the XML escaping, so odd characters in paths can't break the plist.
/usr/bin/env python3 - "$APP/Contents/Info.plist" "$HELPER/Contents/Info.plist" "$VERSION" "$ROOT" "$PATH" <<'PY'
import plistlib
import sys

out, helper_out, version, root, path = sys.argv[1:6]
location = ("Claude OS shows the weather for where you are. "
            "Your location is rounded to about a kilometre and stays on this Mac.")
common = {
    "CFBundleIconFile": "AppIcon",
    "CFBundlePackageType": "APPL",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleShortVersionString": version,
    "CFBundleVersion": version,
    "LSMinimumSystemVersion": "13.0",
}
info = dict(common, **{
    "CFBundleName": "Claude OS",
    "CFBundleDisplayName": "Claude OS",
    "CFBundleIdentifier": "local.claude-os.desktop",
    "CFBundleExecutable": "ClaudeOS",
    "NSHighResolutionCapable": True,
    "NSPrincipalClass": "NSApplication",
    "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    "NSLocationUsageDescription": location,
    "NSLocationWhenInUseUsageDescription": location,
    "ClaudeOSRoot": root,
    "ClaudeOSPath": path,
})
# The helper is a command-line tool in an app's clothing: no Dock icon, no menu bar.
helper = dict(common, **{
    "CFBundleName": "Claude OS Music Helper",
    "CFBundleDisplayName": "Claude OS Music Helper",
    "CFBundleIdentifier": "local.claude-os.music-helper",
    "CFBundleExecutable": "ClaudeOSMusicHelper",
    "LSUIElement": True,
})
for path_out, plist in ((out, info), (helper_out, helper)):
    with open(path_out, "wb") as f:
        plistlib.dump(plist, f)
PY
plutil -lint "$APP/Contents/Info.plist" "$HELPER/Contents/Info.plist" >/dev/null

# --- signing -------------------------------------------------------------------------
# SIGN_ID is what codesign gets ("-" is ad hoc); SIGN_LABEL is what we print, and never
# includes the certificate's name (that's the human's name).
SIGN_AUTO=0
if [ -n "${COS_SIGN_IDENTITY:-}" ]; then
    case "$COS_SIGN_IDENTITY" in
        adhoc|-) SIGN_ID="-" ;;
        *) SIGN_ID="$COS_SIGN_IDENTITY" ;;
    esac
elif [ -n "${CLAUDE_OS_DAEMON:-}" ]; then
    SIGN_ID="-"
else
    # Lines look like:  1) <40 hex> "Apple Development: <name> (<team>)"
    # (`find-identity` only lists certificates; it never touches a private key or prompts.)
    IDENTITIES="$(security find-identity -v -p codesigning 2>/dev/null || true)"
    SIGN_ID="$(printf '%s\n' "$IDENTITIES" | awk '/"Apple Development: / && !found { print $2; found = 1 }')"
    if [[ "$SIGN_ID" =~ ^[0-9A-F]{40}$ ]]; then
        SIGN_AUTO=1
    else
        SIGN_ID="-"
    fi
fi

if [ "$SIGN_ID" = "-" ]; then
    SIGN_LABEL="ad hoc"
elif [ "$SIGN_AUTO" = 1 ]; then
    SIGN_LABEL="Apple Development identity ${SIGN_ID:0:8}…"
elif [[ "$SIGN_ID" =~ ^[0-9A-Fa-f]{40}$ ]]; then
    SIGN_LABEL="identity ${SIGN_ID:0:8}… (COS_SIGN_IDENTITY)"
else
    SIGN_LABEL="the identity named in COS_SIGN_IDENTITY"
fi

# Inside out: the nested helper first, then the app that seals it. No --deep: each bundle
# is signed explicitly. A real identity never asks a timestamp server (offline builds work).
sign_bundles() {
    local args=(--force --sign "$1")
    [ "$1" = "-" ] || args+=(--timestamp=none)
    codesign "${args[@]}" "$HELPER" || return 1
    codesign "${args[@]}" "$APP" || return 1
}

echo "==> signing with $SIGN_LABEL"
if ! sign_bundles "$SIGN_ID"; then
    if [ "$SIGN_AUTO" != 1 ]; then
        echo "build.sh: codesign failed with $SIGN_LABEL" >&2
        exit 1
    fi
    # A locked keychain or a declined prompt shouldn't stop the build.
    echo "build.sh: codesign failed with $SIGN_LABEL; falling back to ad hoc" >&2
    SIGN_ID="-"
    sign_bundles "$SIGN_ID"
fi
codesign --verify --strict "$HELPER"
codesign --verify --strict --deep "$APP"
if [ "$SIGN_ID" = "-" ]; then
    echo "⚠ ad-hoc signed: macOS permissions (Accessibility, Location) reset on every rebuild" >&2
else
    echo "==> signed with $SIGN_LABEL"
fi

TARGET="$APP"
if [ "$INSTALL" = 1 ]; then
    DEST="$HOME/Applications/Claude OS.app"
    echo "==> installing to ~/Applications/Claude OS.app"
    mkdir -p "$HOME/Applications"
    rm -rf "$DEST"
    ditto "$APP" "$DEST"
    TARGET="$DEST"
    echo "    (if Claude OS was running, quit and reopen it to use the new build)"
fi

echo "==> built $APP"
if [ "$OPEN" = 1 ]; then
    open "$TARGET"
fi
