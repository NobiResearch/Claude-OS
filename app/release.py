"""The checks `app/build.sh --release` runs (decision 0015, step 3). A release is an app signed
with the human's name that strangers download, so every check refuses instead of guessing:

    release.py preflight                      may this checkout cut a release now?
    release.py profile <file> <bundle-id> <out-entitlements>
                                              is it a Developer ID profile for that App ID?
    release.py scan <app>                     does anything private hide in the bundle?

Each prints its problems and exits 1 if there are any."""

import os
import plistlib
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from cos import guard  # noqa: E402

# What the released app may ask macOS for, on top of the App ID's two keys. Calendar and
# Location are read in the app (Agenda.swift, Locator.swift); Apple Events reach the Music app.
ALLOWED = {
    "com.apple.security.personal-information.calendars": True,
    "com.apple.security.personal-information.location": True,
    "com.apple.security.automation.apple-events": True,
}
# Never in a signed release: each one weakens the hardened runtime.
FORBIDDEN = ("com.apple.security.get-task-allow", "com.apple.security.cs.disable-library-validation",
             "com.apple.security.cs.allow-dyld-environment-variables",
             "com.apple.security.cs.allow-unsigned-executable-memory", "com.apple.security.cs.allow-jit",
             "com.apple.security.cs.disable-executable-page-protection", "com.apple.security.cs.debugger",
             "get-task-allow")


def _git(*args):
    r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def preflight(env=None):
    """Problems with cutting a release here and now, or []."""
    env = os.environ if env is None else env
    problems = []
    for var in ("CLAUDE_OS_DAEMON", "COS_SANDBOXED", "CI"):
        if env.get(var):
            problems.append("%s is set: releases are built on the human's Mac, by hand" % var)
    status = _git("status", "--porcelain")
    if status is None:
        problems.append("couldn't read the checkout's state")
    elif status:
        problems.append("the checkout has uncommitted changes")
    head, main = _git("rev-parse", "HEAD"), _git("rev-parse", "--verify", "--quiet", "origin/main^{commit}")
    if not head or not main or head != main:
        problems.append("HEAD isn't origin/main: a release is built from what's merged")
    return problems


def profile_problems(profile, bundle_id):
    """(problems, application-identifier, team) for a decoded provisioning profile."""
    problems = []
    team = (profile.get("TeamIdentifier") or [""])[0]
    app_id = (profile.get("Entitlements") or {}).get("com.apple.application-identifier", "")
    if not profile.get("ProvisionsAllDevices") or profile.get("ProvisionedDevices"):
        problems.append("not a Developer ID profile: it lists devices instead of covering every Mac")
    if "OSX" not in (profile.get("Platform") or []):
        problems.append("not a macOS profile")
    if not team or app_id != "%s.%s" % (team, bundle_id):
        problems.append("it's for %s, not %s" % (app_id.split(".", 1)[-1] or "no App ID", bundle_id))
    patterns = guard.SECRET_PATTERNS + guard.personal_patterns()
    for key in ("Name", "AppIDName"):
        if any(rx.search(str(profile.get(key) or "")) for _, rx in patterns):
            problems.append("its %s holds something private: name the profile and the App ID neutrally" % key)
    return problems, app_id, team


def entitlements(app_id, team, extra=None):
    """The release's entitlements: the App ID's two keys, the allowlist, and nothing forbidden."""
    ents = {"com.apple.application-identifier": app_id, "com.apple.developer.team-identifier": team}
    ents.update(ALLOWED)
    for key in extra or {}:
        if key in FORBIDDEN or key not in ALLOWED:
            raise ValueError("%s isn't allowed in a release" % key)
    return ents


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else None


def bundle_texts(app):
    """(label, text) for everything a downloader gets that could hold a path or a name: the
    Info.plist, the executable's strings and symbols, and every resource."""
    texts = []
    plist = os.path.join(app, "Contents", "Info.plist")
    with open(plist, "rb") as f:
        info = plistlib.load(f)
    texts.append(("Info.plist", plistlib.dumps(info).decode("utf-8", "replace")))
    for dirpath, _, names in os.walk(app):
        for name in names:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, app)
            if rel == os.path.join("Contents", "Info.plist") or os.path.islink(full):
                continue
            strings = _run(["strings", "-a", full])
            texts.append((rel, strings if strings is not None else "<couldn't read>"))
            if rel.startswith(os.path.join("Contents", "MacOS")):
                symbols = _run(["nm", "-ap", full])
                texts.append((rel + " (symbols)", symbols or ""))
    return texts, info


def scan(app):
    """Problems in a built bundle, before it's signed: anything the Guardian would block in the
    repository, and the keys only a developer's own build may carry."""
    texts, info = bundle_texts(app)
    problems = ["couldn't read %s" % label for label, text in texts if text == "<couldn't read>"]
    patterns = guard.SECRET_PATTERNS + guard.personal_patterns()
    for label, text in texts:
        problems += ["%s: %s" % (where, why) for where, why in guard.check_text(label, text, patterns)]
    for key in ("ClaudeOSRoot", "ClaudeOSPath"):
        if key in info:
            problems.append("Info.plist has %s: that's for a developer's own build" % key)
    return problems


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    c = argv[0]
    if c == "preflight":
        problems = preflight()
    elif c == "profile" and len(argv) == 4:
        raw = _run(["security", "cms", "-D", "-i", argv[1]])
        if raw is None:
            problems = ["couldn't read the profile %s" % argv[1]]
        else:
            problems, app_id, team = profile_problems(plistlib.loads(raw.encode()), argv[2])
            if not problems:
                with open(argv[3], "wb") as f:
                    plistlib.dump(entitlements(app_id, team), f)
    elif c == "scan" and len(argv) == 2:
        problems = scan(argv[1])
    else:
        print(__doc__)
        return 2
    for p in problems:
        print("✗ %s" % p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
