"""cos guard — the Guardian's pre-commit check. This repository is public.

Blocks commits that would publish secrets or personal data: private state
files, credentials, API keys, and the literal path of this user's home
folder (which leaks their username). Run by githooks/pre-commit.
"""

import os
import re

from . import core

BLOCKED_PATHS = [
    re.compile(r"(^|/)\.claude-os(/|$)"),
    re.compile(r"(^|/)var/"),
    re.compile(r"(^|/)\.env(\.|$)"),
    re.compile(r"\.(pem|p12|p8|key|keychain|mobileprovision)$"),
    re.compile(r"(^|/)\.(envrc|netrc|npmrc|pypirc)$"),
    re.compile(r"(^|/)id_(rsa|ed25519|ecdsa)"),
    re.compile(r"(^|/)(journal|friction|memory)\.(jsonl?|md)$"),
    re.compile(r"(^|/)\.claude/settings\.local\.json$"),
]

SECRET_PATTERNS = [
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI-style key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{32,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
]


def personal_patterns():
    """Strings that identify this particular human, built at runtime so they never live in the repo."""
    pats = []
    home = os.path.expanduser("~")
    if home and home != "/":
        pats.append(("your home folder path", re.compile(re.escape(home), re.I)))
    email = core.run(["git", "config", "user.email"], cwd=str(core.ROOT), timeout=5).out
    if email and "noreply" not in email:
        pats.append(("your email address", re.compile(re.escape(email), re.I)))
    for line in (core.load_json(core.home("guard.json"), {}) or {}).get("extra", []):
        pats.append(("a private term from ~/.claude-os/guard.json", re.compile(re.escape(line), re.I)))
    return pats


def check_paths(paths):
    return [(p, "private or credential file") for p in paths if any(rx.search(p) for rx in BLOCKED_PATHS)]


def check_text(path, text, patterns):
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for what, rx in patterns:
            if rx.search(line):
                problems.append((path, "line %d: %s" % (lineno, what)))
    return problems


def _names(args):
    r = core.run(["git"] + args, cwd=str(core.ROOT), timeout=10)
    return [p for p in r.out.split("\0") if p.strip()]


def publishable():
    """Everything git would publish: tracked files plus untracked ones not ignored."""
    return _names(["ls-files", "-z", "--cached", "--others", "--exclude-standard"])


def staged():
    # -z keeps non-ASCII names unquoted; filter=d keeps type changes (symlink → file).
    return _names(["diff", "--cached", "--name-only", "-z", "--diff-filter=d"])


def staged_text(path):
    r = core.run(["git", "show", ":%s" % path], cwd=str(core.ROOT), timeout=10)
    return r.out if r.ok else ""


LOCAL_EMAIL = re.compile(r"@[^>\s]*\.(local|localdomain|lan|home|internal)>?$|\(none\)", re.I)


def identity_problems():
    """Git invents `user@Your-Mac.local` when user.email is unset, publishing the login and
    machine name in every commit. Block that."""
    problems = []
    for var in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        ident = core.run(["git", "var", var], cwd=str(core.ROOT), timeout=5).out
        m = re.search(r"<([^>]*)>", ident)
        if m and LOCAL_EMAIL.search("<%s>" % m.group(1)):
            problems.append(("(commit metadata)", "%s email is a machine-generated local address; "
                             "set `git config user.email` to your GitHub noreply address" % var.split("_")[1].lower()))
    return problems


def scan(paths, read):
    patterns = SECRET_PATTERNS + personal_patterns()
    problems = check_paths(paths)
    for p in paths:
        if p.endswith((".png", ".jpg", ".gif", ".ico", ".pdf", ".zip")):
            continue
        problems += check_text(p, read(p), patterns)
    return problems


def main(args):
    if args.all:
        paths = publishable()

        def read(p):
            try:
                with open(core.ROOT / p, errors="replace") as f:
                    return f.read()
            except OSError:
                return ""
    else:
        paths, read = staged(), staged_text
    problems = scan(paths, read)
    if not args.all:
        problems += identity_problems()
    if not problems:
        if not args.quiet:
            print("guard: clean (%d file%s checked)" % (len(paths), "" if len(paths) == 1 else "s"))
        return 0
    print("guard: blocked — this repository is public.")
    for path, why in problems:
        print("  %s: %s" % (path, why))
    print("Move private data to ~/.claude-os, or redact it. (Bypass only if you're sure: git commit --no-verify)")
    return 1
