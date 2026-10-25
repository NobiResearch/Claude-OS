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


def text_problems(texts):
    """[(label, text)] -> problems: the Guardian over words about to be published outside the
    repository's files (a pull request's title and body)."""
    patterns = SECRET_PATTERNS + personal_patterns()
    return [p for label, text in texts for p in check_text(label, text, patterns)]


def push_ranges(lines, base):
    """git's pre-push input ("<local ref> <local sha> <remote ref> <remote sha>" per line) ->
    [(sha, base)]: what each pushed ref publishes. Deletions publish nothing; a new branch, or
    one whose remote tip isn't known here (after a force push), is checked from `base`."""
    out = []
    for line in lines.splitlines():
        parts = line.split()
        if len(parts) != 4 or set(parts[1]) == {"0"}:
            continue
        remote = parts[3]
        out.append((parts[1], base if set(remote) == {"0"} else remote))
    return out


def push_problems(ranges, cwd=None):
    """Everything the push would publish, commit by commit (files and messages, like the
    night shift's own pushes), plus each commit's author and committer address: on a public
    repository only noreply addresses. Anything git can't answer blocks the push."""
    from . import evolve
    root = str(cwd or core.ROOT)
    problems = []
    for sha, base in ranges:
        if not core.run(["git", "-C", root, "cat-file", "-e", base + "^{commit}"], timeout=10).ok:
            base = "origin/" + evolve.main_branch(root)
        listed = core.run(["git", "-C", root, "log", "--format=%h%x1f%ae%x1f%ce", "%s..%s" % (base, sha)], timeout=30)
        if not listed.ok:
            problems.append((sha[:8], "can't tell what this push publishes (%s)" % (listed.err or "git failed")[:120]))
            continue
        for line in filter(None, listed.out.splitlines()):
            short, author, committer = (line.split("\x1f") + ["", ""])[:3]
            for who, email in (("author", author), ("committer", committer)):
                if "noreply" not in email.lower():
                    problems.append(("%s %s" % (short, who), "a personal email address in the commit itself; "
                                     "use your GitHub noreply address (git config user.email)"))
        problems += evolve.guard_branch(sha, base, cwd=root)
    return problems


def main(args):
    if getattr(args, "push", False):
        import sys
        from . import evolve
        try:
            problems = push_problems(push_ranges(sys.stdin.read(), "origin/" + evolve.main_branch()))
        except Exception as e:  # fail closed: a push the Guardian couldn't read isn't a clean one
            problems = [("push", "the Guardian couldn't check it (%s)" % e)]
        if not problems:
            return 0
        print("guard: blocked — this push would publish:", file=sys.stderr)
        for path, why in problems:
            print("  %s: %s" % (path, why), file=sys.stderr)
        print("Fix the commits (git commit --amend, git rebase -i), or if you're sure, push with --no-verify.",
              file=sys.stderr)
        return 1
    if args.text:
        texts = []
        for name in args.text:
            try:
                with open(name, errors="replace") as f:
                    texts.append((os.path.basename(name), f.read()))
            except OSError as e:
                core.die("can't read %s: %s" % (name, e.strerror))
        problems = text_problems(texts)
        if not problems:
            if not args.quiet:
                print("guard: clean (%d text%s checked)" % (len(texts), "" if len(texts) == 1 else "s"))
            return 0
        print("guard: blocked — this would be published.")
        for path, why in problems:
            print("  %s: %s" % (path, why))
        return 1
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
