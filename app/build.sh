#!/bin/bash
# Builds "build/Ovenbird.app", the native shell around `cos serve`, with
# a built-in Apple Music player (MusicKit, "Media & Apple Music" permission).
#
#   app/build.sh             build and sign build/Ovenbird.app
#   app/build.sh --install   also copy it to ~/Applications/Ovenbird.app
#   app/build.sh --open      also open it (the installed copy with --install)
#
# The bundle's Info.plist bakes in this checkout's absolute path and your current $PATH
# (apps started from Finder don't get your shell's PATH). Both are machine-specific, so
# they live only in the built bundle; build/ is git-ignored. Rebuild if the repo moves.
#
# Signing: macOS ties privacy grants (Apple Music, Location) to the code signature. An
# ad-hoc signature is new on every build, so grants reset; an Apple Development identity
# keeps them. The identity is chosen at build time and never written to any file:
#   COS_SIGN_IDENTITY=adhoc        ad hoc
#   COS_SIGN_IDENTITY=<sha1|name>  that identity
#   CLAUDE_OS_DAEMON set           ad hoc (a headless run must never meet a keychain prompt)
#   otherwise                      the first valid "Apple Development" identity, by SHA-1
#                                  (ad hoc if there is none)
#
#   app/build.sh --release [--no-notarize]
#       the app strangers download (decision 0015): from a clean checkout at origin/main,
#       nothing machine-specific inside (no paths, a stripped binary, scanned before signing),
#       Developer ID with the hardened runtime, notarized and stapled, zipped in build/.
#       Needs COS_RELEASE_PROFILE (a Developer ID provisioning profile for the release App ID,
#       COS_RELEASE_BUNDLE_ID, default app.claude-os.desktop) and COS_NOTARY_PROFILE (a
#       `xcrun notarytool store-credentials` Keychain profile). Every check stops the build;
#       nothing falls back to ad hoc. Publishing it is a separate step, on the human's yes.
set -euo pipefail

usage() { sed -n '2,30s/^# \{0,1\}//p' "$0"; }

INSTALL=0
OPEN=0
RELEASE=0
NOTARIZE=1
for arg in "$@"; do
    case "$arg" in
        --install) INSTALL=1 ;;
        --open) OPEN=1 ;;
        --release) RELEASE=1 ;;
        --no-notarize) NOTARIZE=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "build.sh: unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done
if [ "$RELEASE" = 1 ] && [ "${1:-}" != "--release" ]; then
    # So the permission prompt's rules (`app/build.sh --release*`) always see it.
    echo "build.sh: write --release first: app/build.sh --release [--no-notarize]" >&2
    exit 2
fi
if [ "$RELEASE" = 1 ] && { [ "$INSTALL" = 1 ] || [ "$OPEN" = 1 ]; }; then
    echo "build.sh: a release is for downloading, not for installing over your own build" >&2
    exit 2
fi
if [ "$RELEASE" = 0 ] && [ "$NOTARIZE" = 0 ]; then
    echo "build.sh: --no-notarize only goes with --release" >&2
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

VERSION="$(sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' lib/cos/__init__.py)"
if [ -z "$VERSION" ]; then
    echo "build.sh: couldn't read __version__ from lib/cos/__init__.py" >&2
    exit 1
fi

COMMIT=""
if [ "$RELEASE" = 1 ]; then
    echo "==> release checks"
    /usr/bin/env python3 app/release.py preflight
    COMMIT="$(git rev-parse HEAD)"
fi

echo "==> swift build (release)"
swift build -c release --package-path app
BIN_DIR="$(swift build -c release --package-path app --show-bin-path)"

APP="build/Ovenbird.app"
# MusicKit only works for a bundle id registered (with the MusicKit service) in the signing
# team's developer account. Anyone building their own copy sets COS_BUNDLE_ID to theirs.
if [ "$RELEASE" = 1 ]; then
    BUNDLE_ID="${COS_RELEASE_BUNDLE_ID:-app.claude-os.desktop}"
else
    BUNDLE_ID="${COS_BUNDLE_ID:-local.claude-os.desktop}"
fi
echo "==> assembling $APP ($VERSION, $BUNDLE_ID)"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN_DIR/ClaudeOS" "$APP/Contents/MacOS/ClaudeOS"
if [ "$RELEASE" = 1 ]; then
    strip -S "$APP/Contents/MacOS/ClaudeOS"  # the debug map names object files by their full path
fi

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
/usr/bin/env python3 - "$APP/Contents/Info.plist" "$VERSION" "$ROOT" "$PATH" "$BUNDLE_ID" "$COMMIT" <<'PY'
import plistlib
import sys

out, version, root, path, bundle_id, commit = sys.argv[1:7]
location = ("Ovenbird shows the weather for where you are. "
            "Your location is rounded to about a kilometre and stays on this Mac.")
calendar = "Ovenbird shows today's events on your desktop and in your morning brief. It only reads; it never changes your calendar."
reminders = "Ovenbird shows the reminders that are due on your desktop and in your morning brief. It only reads them."
info = {
    "CFBundleIconFile": "AppIcon",
    "CFBundlePackageType": "APPL",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleShortVersionString": version,
    "CFBundleVersion": version,
    "LSMinimumSystemVersion": "14.0",
    "CFBundleName": "Ovenbird",
    "CFBundleDisplayName": "Ovenbird",
    "CFBundleIdentifier": bundle_id,
    "CFBundleExecutable": "ClaudeOS",
    "NSHighResolutionCapable": True,
    "NSPrincipalClass": "NSApplication",
    "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    "NSLocationUsageDescription": location,
    "NSLocationWhenInUseUsageDescription": location,
    "NSAppleMusicUsageDescription": "Ovenbird plays the Apple Music songs you ask for.",
    "NSCalendarsFullAccessUsageDescription": calendar,
    "NSCalendarsUsageDescription": calendar,
    "NSRemindersFullAccessUsageDescription": reminders,
    "NSRemindersUsageDescription": reminders,
    # claude-os://music/play?id=… lets `cos` drive the built-in player (see Player.swift).
    "CFBundleURLTypes": [{"CFBundleURLName": "Ovenbird", "CFBundleURLSchemes": ["claude-os"]}],
}
if commit:
    # A release: nothing machine-specific. The app finds its code and PATH at runtime, and
    # knows which commit it was built from.
    info["ClaudeOSCommit"] = commit
    info["NSAppleEventsUsageDescription"] = "Ovenbird controls the Music app when you ask it to play something there."
else:
    info["ClaudeOSRoot"] = root
    info["ClaudeOSPath"] = path
with open(out, "wb") as f:
    plistlib.dump(info, f)
PY
plutil -lint "$APP/Contents/Info.plist" >/dev/null

# --- release (decision 0015) -----------------------------------------------------------
if [ "$RELEASE" = 1 ]; then
    echo "==> scanning the bundle for anything private (before it's signed)"
    /usr/bin/env python3 app/release.py scan "$APP"

    # Developer ID only: the identity named in COS_SIGN_IDENTITY, or the first one listed.
    IDENTITIES="$(security find-identity -v -p codesigning 2>/dev/null || true)"
    SIGN_ID="${COS_SIGN_IDENTITY:-$(printf '%s\n' "$IDENTITIES" | awk '/"Developer ID Application: / && !found { print $2; found = 1 }')}"
    # A whole SHA-1, on a Developer ID Application line: never "-" (ad hoc) or a fragment.
    if ! [[ "$SIGN_ID" =~ ^[0-9A-F]{40}$ ]] ||
       ! printf '%s\n' "$IDENTITIES" | awk -v id="$SIGN_ID" '$2 == id && /"Developer ID Application: / { ok = 1 } END { exit !ok }'; then
        echo "build.sh: a release is signed with a Developer ID Application identity, and there's none to use" >&2
        exit 1
    fi

    if [ -z "${COS_RELEASE_PROFILE:-}" ]; then
        echo "build.sh: set COS_RELEASE_PROFILE to the release's Developer ID provisioning profile" >&2
        exit 1
    fi
    echo "==> checking the provisioning profile"
    /usr/bin/env python3 app/release.py profile "$COS_RELEASE_PROFILE" "$BUNDLE_ID" build/release-entitlements.plist
    # -X: a downloaded profile carries the address it came from in its extended attributes.
    cp -X "$COS_RELEASE_PROFILE" "$APP/Contents/embedded.provisionprofile"

    echo "==> signing with Developer ID ${SIGN_ID:0:8}…, the hardened runtime and a secure timestamp"
    codesign --force --options runtime --timestamp --entitlements build/release-entitlements.plist \
        --sign "$SIGN_ID" "$APP"
    codesign --verify --strict --deep "$APP"
    SIGNATURE="$(codesign -dv --verbose=2 "$APP" 2>&1)"
    TEAM="$(/usr/libexec/PlistBuddy -c 'Print :com.apple.developer.team-identifier' build/release-entitlements.plist)"
    if [[ "$SIGNATURE" != *"(runtime)"* ]]; then
        echo "build.sh: no hardened runtime in the signature" >&2
        exit 1
    fi
    if [[ "$SIGNATURE" != *"Authority=Developer ID Application: "* ]] || [[ "$SIGNATURE" != *"TeamIdentifier=$TEAM"* ]]; then
        echo "build.sh: the signature isn't Developer ID for the profile's team" >&2
        exit 1
    fi

    ZIP="build/Ovenbird-$VERSION.zip"
    # No extended attributes: macOS tags every file the build makes, and ditto would store the
    # tags as ._ files, which unzip leaves inside the app, where they break its signature.
    zip_app() {
        rm -f "$ZIP"
        ditto -c -k --norsrc --noextattr --keepParent "$APP" "$ZIP"
        if zipinfo -1 "$ZIP" | grep -E '(^|/)(__MACOSX|\._)' >/dev/null; then
            echo "build.sh: the zip has macOS metadata files in it" >&2
            exit 1
        fi
    }
    zip_app
    if [ "$NOTARIZE" = 1 ]; then
        if [ -z "${COS_NOTARY_PROFILE:-}" ]; then
            echo "build.sh: set COS_NOTARY_PROFILE to your notarytool Keychain profile (or add --no-notarize for a local check)" >&2
            exit 1
        fi
        echo "==> notarizing (Apple checks it; a few minutes)"
        xcrun notarytool submit "$ZIP" --keychain-profile "$COS_NOTARY_PROFILE" --wait
        xcrun stapler staple "$APP"
        zip_app
        spctl -a -vv "$APP" 2>&1 | grep -E '^(build|source)' | sed -E 's/(Developer ID Application: ).*/\1<the certificate holder>/' || true
        echo "==> built $ZIP: Developer ID, notarized and stapled (commit ${COMMIT:0:7})"
    else
        echo "==> built $ZIP: Developer ID, NOT notarized: a local check, not for publishing"
    fi
    exit 0
fi

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

# --- provisioning profile (MusicKit) ---------------------------------------------------
# MusicKit mints its developer token for apps it can identify: an application-identifier
# entitlement, backed by an embedded profile for an App ID with the MusicKit service. The
# profile is personal (team id, device), so it lives in ~/.claude-os, never in the repo.
PROFILE="${COS_PROVISIONING_PROFILE:-$HOME/.claude-os/ClaudeOS.provisionprofile}"
ENTITLEMENTS=""
if [ -f "$PROFILE" ] && [ "$SIGN_ID" != "-" ]; then
    if security cms -D -i "$PROFILE" > build/profile.plist 2>/dev/null &&
       /usr/bin/env python3 - build/profile.plist "$BUNDLE_ID" build/entitlements.plist <<'PY'
import plistlib
import sys

profile = plistlib.load(open(sys.argv[1], "rb"))
team = (profile.get("TeamIdentifier") or [""])[0]
app_id = (profile.get("Entitlements") or {}).get("com.apple.application-identifier", "")
if app_id != "%s.%s" % (team, sys.argv[2]):
    sys.exit("build.sh: the provisioning profile is for %s, not %s" % (app_id.split(".", 1)[-1], sys.argv[2]))
with open(sys.argv[3], "wb") as f:
    plistlib.dump({"com.apple.application-identifier": app_id, "com.apple.developer.team-identifier": team}, f)
PY
    then
        cp "$PROFILE" "$APP/Contents/embedded.provisionprofile"
        ENTITLEMENTS="build/entitlements.plist"
        echo "==> embedding the provisioning profile (MusicKit)"
    else
        echo "⚠ couldn't use $PROFILE; building without it (MusicKit won't work)" >&2
    fi
    rm -f build/profile.plist
fi

# A real identity never asks a timestamp server, so offline builds work. Ad hoc can't
# carry restricted entitlements (macOS would refuse to launch it), so it never gets them.
sign_bundles() {
    local args=(--force --sign "$1")
    if [ "$1" != "-" ]; then
        args+=(--timestamp=none)
        [ -n "$ENTITLEMENTS" ] && args+=(--entitlements "$ENTITLEMENTS")
    else
        rm -f "$APP/Contents/embedded.provisionprofile"
    fi
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
codesign --verify --strict --deep "$APP"
if [ "$SIGN_ID" = "-" ]; then
    echo "⚠ ad-hoc signed: macOS permissions (Apple Music, Location) reset on every rebuild, and MusicKit won't work" >&2
else
    echo "==> signed with $SIGN_LABEL"
fi

TARGET="$APP"
if [ "$INSTALL" = 1 ]; then
    DEST="$HOME/Applications/Ovenbird.app"
    echo "==> installing to ~/Applications/Ovenbird.app"
    mkdir -p "$HOME/Applications"
    # Replace only our own app (like core._is_claude_os_app): "Ovenbird" is a common word.
    if [ -e "$DEST" ]; then
        exe=$(/usr/libexec/PlistBuddy -c "Print :CFBundleExecutable" "$DEST/Contents/Info.plist" 2>/dev/null || true)
        scheme=$(/usr/libexec/PlistBuddy -c "Print :CFBundleURLTypes:0:CFBundleURLSchemes:0" "$DEST/Contents/Info.plist" 2>/dev/null || true)
        if [ "$exe" != "ClaudeOS" ] || [ "$scheme" != "claude-os" ]; then
            echo "✗ ~/Applications/Ovenbird.app is another app, not this one: move it elsewhere and run again" >&2
            exit 1
        fi
    fi
    rm -rf "$DEST"
    ditto "$APP" "$DEST"
    TARGET="$DEST"
    echo "    (if Ovenbird was running, quit and reopen it to use the new build)"
fi

echo "==> built $APP"
if [ "$OPEN" = 1 ]; then
    open "$TARGET"
fi
