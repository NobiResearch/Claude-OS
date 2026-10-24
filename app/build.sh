#!/bin/bash
# Builds "build/Claude OS.app", the native shell around `cos serve`.
#
#   app/build.sh             build and ad-hoc sign build/Claude OS.app
#   app/build.sh --install   also copy it to ~/Applications/Claude OS.app
#   app/build.sh --open      also open it (the installed copy with --install)
#
# The bundle's Info.plist bakes in this checkout's absolute path and your current $PATH
# (apps started from Finder don't get your shell's PATH). Both are machine-specific, so
# they live only in the built bundle; build/ is git-ignored. Rebuild if the repo moves.
set -euo pipefail

usage() { sed -n '2,10s/^# \{0,1\}//p' "$0"; }

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
echo "==> assembling $APP ($VERSION)"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN_DIR/ClaudeOS" "$APP/Contents/MacOS/ClaudeOS"

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

# plistlib does the XML escaping, so odd characters in paths can't break the plist.
/usr/bin/env python3 - "$APP/Contents/Info.plist" "$VERSION" "$ROOT" "$PATH" <<'PY'
import plistlib
import sys

out, version, root, path = sys.argv[1:5]
info = {
    "CFBundleName": "Claude OS",
    "CFBundleDisplayName": "Claude OS",
    "CFBundleIdentifier": "local.claude-os.desktop",
    "CFBundleExecutable": "ClaudeOS",
    "CFBundleIconFile": "AppIcon",
    "CFBundlePackageType": "APPL",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleShortVersionString": version,
    "CFBundleVersion": version,
    "LSMinimumSystemVersion": "13.0",
    "NSHighResolutionCapable": True,
    "NSPrincipalClass": "NSApplication",
    "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    "ClaudeOSRoot": root,
    "ClaudeOSPath": path,
}
with open(out, "wb") as f:
    plistlib.dump(info, f)
PY
plutil -lint "$APP/Contents/Info.plist" >/dev/null

echo "==> signing (ad hoc)"
codesign --force --deep -s - "$APP"
codesign --verify --deep "$APP"

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
