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
    # A pasted prompt (`name@host %`) or log line carries these without the home path
    # (Fable's review, F10). The login only where it names someone (`login@`, `~login`, a
    # `/login` folder), never in a GitHub noreply address, and never a word everyone uses.
    login = login_name()
    if login:
        w = re.escape(login)
        pats.append(("your login name", re.compile(
            r"(?<![\w.+-])%s@(?!users\.noreply\.github\.com)|~%s(?![\w-])|/%s(?![\w.-])" % (w, w, w), re.I)))
    # The Mac's names only when they're the "Ada's MacBook Pro" kind macOS makes from a person's
    # name; "Home" or "Studio" would block half the repository.
    computer = core.run(["scutil", "--get", "ComputerName"], timeout=5).out.strip()
    if re.search(r"\w['’]s\s", computer) and not generic_mac_name(computer):
        local = core.run(["scutil", "--get", "LocalHostName"], timeout=5).out.strip()
        for what, name in (("your Mac's name", computer), ("your Mac's network name", local)):
            if name and not generic_mac_name(name):
                pats.append((what, re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(name), re.I)))
    return pats


# Logins that are also everyday words or folder names: as a pattern they'd block half the tree.
COMMON_LOGINS = {"root", "admin", "administrator", "user", "users", "guest", "test", "runner", "dev", "mac",
                 "staff", "home", "code", "data", "music", "work", "claude", "apps", "docs", "share", "local",
                 "private", "shared", "build", "tools", "projects"}


def login_name():
    import pwd
    try:
        name = pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, OSError):
        name = os.environ.get("USER", "")
    return name if len(name) >= 4 and name.lower() not in COMMON_LOGINS else ""


def generic_mac_name(name):
    """"MacBook Pro", "Mac-mini-2": a model, not a person, so not worth blocking."""
    rest = re.sub(r"(?i)\b(macbook|imac|mac|mini|studio|pro|air|max|ultra|local)\b|[\s\-_'’().0-9]", "", name)
    return not rest


def check_paths(paths):
    return [(p, "private or credential file") for p in paths if any(rx.search(p) for rx in BLOCKED_PATHS)]


def check_text(path, text, patterns):
    from urllib.parse import unquote
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        # A URL hides a path as %2FUsers%2F…: look at the decoded line too.
        decoded = unquote(line) if "%" in line else line
        for what, rx in patterns:
            if rx.search(line) or (decoded is not line and rx.search(decoded)):
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
        text = read(p)
        if p.lower().endswith(BINARY):
            # Pictures carry text too (EXIF, PNG tEXt chunks, a PDF's /Author): check the
            # readable runs in them rather than skipping the file.
            text = "\n".join(re.findall(r"[ -~]{6,}", text))
        problems += check_text(p, text, patterns)
    return problems


BINARY = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".heic", ".webp")


def text_problems(texts):
    """[(label, text)] -> problems: the Guardian over words about to be published outside the
    repository's files (a pull request's title and body)."""
    patterns = SECRET_PATTERNS + personal_patterns()
    return [p for label, text in texts for p in check_text(label, text, patterns)]


def push_ranges(lines):
    """git's pre-push input ("<local ref> <local sha> <remote ref> <remote sha>" per line) ->
    [(ref, sha, remote sha or None)]. Deletions publish nothing."""
    out = []
    for line in lines.splitlines():
        parts = line.split()
        if len(parts) != 4 or set(parts[1]) == {"0"}:
            continue
        out.append((parts[0], parts[1], None if set(parts[3]) == {"0"} else parts[3]))
    return out


def noreply(email):
    """Only GitHub's own noreply addresses: "noreply" anywhere else (someone+noreply@…) is
    still a personal address."""
    e = (email or "").strip().lower()
    return e.endswith("@users.noreply.github.com") or e == "noreply@github.com"


def _personal(where):
    return (where, "a personal email address in the commit itself; use your GitHub noreply address "
                   "(git config user.email)")


def push_problems(ranges, remote="origin", cwd=None):
    """Everything the push would publish: each commit not already on the remote (files and
    messages, like the night shift's own pushes), each commit's author and committer address,
    and an annotated tag's tagger and message. Anything git can't answer blocks the push."""
    from . import evolve
    root = str(cwd or core.ROOT)

    def git(*args, timeout=30):
        return core.run(["git", "-C", root] + list(args), timeout=timeout)
    problems = []
    for ref, sha, remote_sha in ranges:
        kind = git("cat-file", "-t", sha).out
        if kind == "tag":
            tag = git("cat-file", "tag", sha)
            if not tag.ok:
                problems.append((ref, "git couldn't read the tag"))
                continue
            head, _, message = tag.out.partition("\n\n")
            tagger = next((l for l in head.splitlines() if l.startswith("tagger ")), "")
            email = tagger[tagger.find("<") + 1:tagger.find(">")] if "<" in tagger else ""
            if tagger and not noreply(email):
                problems.append(_personal("%s tagger" % ref))
            problems += [("%s message" % ref, why) for _, why in
                         check_text("tag", message, SECRET_PATTERNS + personal_patterns())]
            target = git("rev-parse", "--verify", "--quiet", sha + "^{commit}")
            if not target.ok:
                problems.append((ref, "a tag of something other than a commit; the Guardian can't check it"))
                continue
            sha = target.out
        elif kind != "commit":
            problems.append((ref, "pushes a %s, not a commit; the Guardian can't check it" % (kind or "thing git can't name")))
            continue
        # New to the remote: not on any of its branches here, and not in what it had at this ref.
        since = ["^" + remote_sha] if remote_sha and git("cat-file", "-e", remote_sha + "^{commit}").ok else []
        listed = git("log", "--format=%H%x1f%ae%x1f%ce", sha, "--not", "--remotes=" + remote, *since)
        if not listed.ok:
            problems.append((ref, "can't tell what this push publishes (%s)" % (listed.err or "git failed")[:120]))
            continue
        commits = []
        for line in filter(None, listed.out.splitlines()):
            full, author, committer = (line.split("\x1f") + ["", ""])[:3]
            commits.append(full)
            problems += [_personal("%s %s" % (full[:8], who)) for who, email in
                         (("author", author), ("committer", committer)) if not noreply(email)]
        problems += evolve.guard_commits(list(reversed(commits)), cwd=root)
    return problems


def main(args):
    if getattr(args, "push", False):
        import sys
        try:
            problems = push_problems(push_ranges(sys.stdin.read()), remote=args.remote or "origin")
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
