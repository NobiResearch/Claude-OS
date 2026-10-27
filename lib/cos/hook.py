"""cos hook permission — answer Claude Code's push prompts for the night shift (0006).

Claude Code runs this as a PermissionRequest hook, just before it would ask the human. While
the human has "Night shift" on in Settings, it approves pushes and nothing that merges:

- **Pushing** `git push [-q] -u origin night/<name>` from a checkout of this repository, to
  the remote it was cloned from, after the Guardian has checked every commit and message it
  would publish. A pushed branch runs nothing that matters, so it may change anything except
  `.github/` (CI runs a branch's workflow the moment it's pushed).
- **Never merging.** A merge is where code starts to run, and every pull request gets a
  guardian agent's review first (decision 0020). For `gh pr merge <N> --squash
  --delete-branch --match-head-commit <sha>` it says at best that the pull request is ready
  for that review, and the human's prompt appears.

While the switch is on, it also lets read-only `gh api <path>` calls through, and pull request
text (`gh pr create|edit|comment` with a title and a body) once the Guardian has read it. With the switch off, or in a downloaded copy, it
approves nothing (decision 0017: a stranger's clone sees a card for `gh`). Anything else, any
doubt, any error: it prints nothing and the human's normal prompt appears. This is a tripwire against drift and mistakes, not a wall: Claude works with the
human's own GitHub login, and decision 0006 lists the spellings these rules don't catch.

`cos hook check <branch|PR>` answers without acting: would this push go through, and is this
pull request ready for its review (with the exact merge command)? With no argument it lists
the night's pull requests and what each waits for.
"""

import json
import os
import re
import shlex
import sys

from . import core

ALLOW = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
COMMAND = re.compile(r"[A-Za-z0-9._/ -]+")  # no quotes, $, ;, &, |, <, >, globs, :, +, @, ~ or newlines
BRANCH = re.compile(r"night/[A-Za-z0-9._-]+")
SHA = re.compile(r"[0-9a-f]{40}")
# Every pull request gets a guardian agent's review before it merges (decision 0020), so the
# hook never merges one on its own: at best it's ready for that review.
READY = "ready once a guardian agent has reviewed it (0020)"
GITHUB = re.compile(r"(?:https://github\.com/|git@github\.com:)([\w.-]+)/([\w.-]+?)(?:\.git)?$")
# The files a guardian's review reads first (every pull request gets one, 0020), and the ones
# the human's update cards, evolve's --reviewed and the boot banner single out. They
# include the code this hook leans on (core, cli, evolve's guard_branch), the server that
# flips the switch and the app's Allow/Deny path, so one night's merge can't loosen the next.
PROTECTED = (".claude/", ".github/", "githooks/", "bin/", "CLAUDE.md", "etc/daemons.json",
             "lib/cos/guard.py", "lib/cos/hook.py", "lib/cos/daemon.py",
             "lib/cos/core.py", "lib/cos/cli.py", "lib/cos/evolve.py", "lib/cos/server.py",
             "lib/cos/__init__.py", "lib/cos/chat.py", "lib/cos/security.py",
             "lib/cos/system.py",  # system.py decides which skills load in every session
             # The app's build, signing and first-launch setup: once strangers run a binary
             # signed in the human's name, its code gets a review before it merges (0015).
             "app/")
NEVER_PUSHED = (".github/",)  # CI runs it on push: a workflow could merge pull requests itself
GREEN = ("SUCCESS", "SKIPPED", "NEUTRAL")


def protected(path):
    """Is this path part of the gate? Also anything Python loads before Ovenbird's own code:
    bin/cos puts lib/ first on sys.path, so a lib/json.py would stand in for the standard
    library's inside this very hook, and compiled .pyc files can skip their source."""
    if path in PROTECTED or path.startswith(PROTECTED):
        return True
    if path.startswith("lib/") and not path.startswith("lib/cos/"):
        return True
    return "__pycache__/" in path or path.endswith((".pyc", ".pth"))


def changed(git, base, branch):
    """Every path the branch touches, or None if git can't say. --no-renames: git lists a
    moved file under its new name only, so moving .claude/settings.json away would look
    like a new file in docs/."""
    r = git("diff", "--no-renames", "--name-only", "%s...%s" % (base, branch))
    return r.out.splitlines() if r.ok else None


def clean_main(base):
    """The hook runs from the live checkout, so that checkout must be main with nothing of
    the gate changed locally: no edits, no untracked files, no commits origin hasn't got."""
    from . import evolve
    root = str(core.ROOT)
    def git(*args):
        return core.run(["git", "-C", root] + list(args), timeout=10)
    if git("symbolic-ref", "--short", "HEAD").out != evolve.main_branch():
        return False
    status = git("status", "--porcelain", "--", "lib", "bin", ".claude", "CLAUDE.md", "etc", "githooks")
    local = git("diff", "--no-renames", "--name-only", base, "HEAD")
    return status.ok and not status.out.strip() and local.ok and not any(protected(p) for p in local.out.splitlines())


# ---------------------------------------------------------------- the commands

def _words(command):
    if not isinstance(command, str) or not COMMAND.fullmatch(command):
        return None
    return command.split()


def parse_push(command):
    """The one command the night shift may push with -> its branch, or None."""
    words = _words(command)
    if not words or words[:2] != ["git", "push"]:
        return None
    rest = words[2:]
    if rest[:1] in (["-q"], ["--quiet"]):
        rest = rest[1:]
    if len(rest) != 3 or rest[:2] != ["-u", "origin"]:
        return None
    branch = rest[2]
    if not BRANCH.fullmatch(branch) or ".." in branch or branch.endswith((".", ".lock", "main", "master")):
        return None
    return branch


def parse_merge(command):
    """The one command the night shift may merge with -> (PR number, the commit it checked),
    or None. Pinning the commit means GitHub merges exactly what was checked here."""
    words = _words(command)
    if not words or len(words) != 8 or words[:3] != ["gh", "pr", "merge"]:
        return None
    if words[4:7] != ["--squash", "--delete-branch", "--match-head-commit"]:
        return None
    if not words[3].isdigit() or not SHA.fullmatch(words[7]):
        return None
    return int(words[3]), words[7]


PR_TEXT = {("gh", "pr", "create"), ("gh", "pr", "edit"), ("gh", "pr", "comment")}
EXPANDS = re.compile(r"[$`\n\r]")  # nothing the shell would expand, and one line


def parse_pr_text(command):
    """`gh pr create|edit|comment` publishing only a title and a body -> {"texts", "body_file"},
    or None. Titles have spaces, so this parses quotes, but anything a shell would expand or
    chain makes it None."""
    if not isinstance(command, str) or EXPANDS.search(command):
        return None
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        words = list(lex)
    except ValueError:
        return None
    if any(w and set(w) <= set("();<>|&") for w in words) or tuple(words[:3]) not in PR_TEXT:
        return None
    texts, body_file, number, rest, i = [], None, False, words[3:], 0
    while i < len(rest):
        w, value = rest[i], rest[i + 1] if i + 1 < len(rest) else None
        if w in ("--title", "-t", "--body", "-b") and value is not None:
            texts.append(value)
            i += 2
        elif w in ("--body-file", "-F") and value not in (None, "-") and body_file is None:
            body_file = value
            i += 2
        elif w in ("--base", "-B", "--head", "-H") and value and re.fullmatch(r"[\w./-]+", value):
            i += 2
        elif w == "--draft":
            i += 1
        elif w.isdigit() and not number and words[2] in ("edit", "comment"):
            number = True
            i += 1
        else:
            return None
    if not texts and body_file is None:
        return None
    return {"texts": texts, "body_file": body_file}


def decide_pr_text(parsed, cwd):
    """The Guardian over what a pull request's title and body would publish."""
    from . import guard
    texts = [("title", t) for t in parsed["texts"]]
    if parsed["body_file"]:
        path = os.path.join(cwd, os.path.expanduser(parsed["body_file"]))
        try:
            if os.path.getsize(path) > 256 * 1024:
                return False, "the body file is too big to check"
            with open(path, errors="replace") as f:
                texts.append(("body", f.read()))
        except OSError:
            return False, "couldn't read the body file"
    problems = guard.text_problems(texts)
    if problems:
        return False, "the Guardian found %d problem(s) in what this would publish" % len(problems)
    return True, "the Guardian checked what this publishes"


def parse_api_read(command):
    """A read-only `gh api [--paginate] <path>`: no method, no fields, no input, no GraphQL."""
    words = _words(command)
    if not words or words[:2] != ["gh", "api"]:
        return False
    rest = [w for w in words[2:] if w != "--paginate"]
    return len(rest) == 1 and not rest[0].startswith("-") and "graphql" not in rest[0] and ".." not in rest[0]


# ---------------------------------------------------------------- what's true

def _repo(git):
    from . import evolve
    top = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    ours = core.run(["git", "-C", str(core.ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"], timeout=30)
    base = "origin/" + evolve.main_branch()
    return base, {
        "same_repo": top.ok and ours.ok and top.out == ours.out,
        "clean_main": clean_main(base),
        "main": evolve.main_branch(),
        "url": git("remote", "get-url", "origin").out,
        "push_url": git("remote", "get-url", "--push", "origin").out,
    }


def inspect(branch, cwd):
    """What a push decision needs to know, read with main's own code."""
    from . import evolve
    def git(*args):
        return core.run(["git", "-C", cwd] + list(args), timeout=30)
    base, facts = _repo(git)
    head = git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch).out
    facts.update(head=head, paths=changed(git, base, branch) if head else [],
                 problems=evolve.guard_branch(branch, base=base) if head else [])
    return facts


def inspect_pr(number, sha, cwd):
    """What a merge decision needs to know: one `gh pr view` for the pull request's state and
    checks, and everything about its code from local git (GitHub's file list stops at 100)."""
    from . import evolve, guard
    def git(*args):
        return core.run(["git", "-C", cwd] + list(args), timeout=20)
    base, facts = _repo(git)
    view = core.run(["gh", "pr", "view", str(number), "--json",
                     "number,state,isDraft,isCrossRepository,headRefName,headRefOid,baseRefName,url,title,statusCheckRollup"],
                    cwd=cwd, timeout=15)
    try:
        pr = json.loads(view.out) if view.ok else None
    except ValueError:
        pr = None
    facts["pr"] = pr if isinstance(pr, dict) else None
    if facts["pr"] and BRANCH.fullmatch(str(pr.get("headRefName"))) and git("cat-file", "-e", sha + "^{commit}").ok:
        facts["local"] = git("rev-parse", "--verify", "--quiet", "refs/heads/" + pr["headRefName"]).out
        facts["paths"] = changed(git, base, sha)
        facts["problems"] = evolve.guard_branch(sha, base=base)
        patterns = guard.SECRET_PATTERNS + guard.personal_patterns()
        facts["problems"] += [("title", why) for _, why in guard.check_text("title", str(pr.get("title") or ""), patterns)]
    return facts


# ---------------------------------------------------------------- deciding

def _common(facts):
    if not facts.get("same_repo"):
        return "not a checkout of Ovenbird"
    if not facts.get("clean_main"):
        return "the hook isn't running from a clean main"
    url = facts.get("url") or ""
    if not url or facts.get("push_url") != url or not GITHUB.match(url):
        return "origin isn't a plain GitHub remote"
    return None


def checks_green(rollup):
    """Every check finished and passed, and `test` (what the ruleset requires) is among them."""
    runs = rollup if isinstance(rollup, list) else []
    def outcome(c):
        return c.get("conclusion") if c.get("__typename", "CheckRun") == "CheckRun" else c.get("state")
    def name(c):
        return c.get("name") or c.get("context")
    if not runs or any(outcome(c) not in GREEN for c in runs):
        return False
    return any(name(c) == "test" and outcome(c) == "SUCCESS" for c in runs)


def decide_push(branch, facts):
    why = _common(facts)
    if why:
        return False, why
    if not facts.get("head"):
        return False, "no local branch %s" % branch
    if facts.get("paths") is None:
        return False, "couldn't list what the branch changes"
    ci = [p for p in facts["paths"] if p.startswith(NEVER_PUSHED)]
    if ci:
        return False, "changes CI (%s): the hook never pushes that, since a branch's workflow runs once it's pushed" % ", ".join(ci[:3])
    if facts.get("problems"):
        return False, "the Guardian found %d problem(s)" % len(facts["problems"])
    return True, "%s at %s" % (branch, facts["head"][:8])


def decide_merge(number, sha, facts):
    why = _common(facts)
    if why:
        return False, why
    pr = facts.get("pr")
    if not pr:
        return False, "couldn't read pull request #%d" % number
    owner_repo = GITHUB.match(facts["url"]).groups()
    if str(pr.get("url", "")).lower() != ("https://github.com/%s/%s/pull/%d" % (owner_repo + (number,))).lower():
        return False, "#%d isn't a pull request of this repository" % number
    if pr.get("state") != "OPEN" or pr.get("isDraft") or pr.get("isCrossRepository"):
        return False, "#%d isn't an open, ready pull request from this repository" % number
    head = str(pr.get("headRefName"))
    if not BRANCH.fullmatch(head) or pr.get("baseRefName") != facts.get("main"):
        return False, "#%d isn't a night/* branch into %s" % (number, facts.get("main"))
    if not (pr.get("headRefOid") == sha == facts.get("local")):
        return False, "#%d's head isn't the commit that was checked" % number
    if not checks_green(pr.get("statusCheckRollup")):
        return False, "#%d's checks aren't all green yet" % number
    if facts.get("paths") is None:
        return False, "couldn't list what #%d changes" % number
    if facts.get("problems"):
        return False, "the Guardian found %d problem(s)" % len(facts["problems"])
    touched = [p for p in facts["paths"] if protected(p)]
    where = ("; it changes Ovenbird's safety files (%s), so the review looks there first" % ", ".join(touched[:3])
             if touched else "")
    return False, READY + where


def decide(request, cfg, look=inspect, look_pr=inspect_pr):
    """-> (approve, why). Pure apart from `look` and `look_pr`, which read the repository."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return False, "inside a background job"
    if request.get("tool_name") != "Bash":
        return False, "not a shell command"
    command = (request.get("tool_input") or {}).get("command")
    if not (cfg.get("autonomy") or {}).get("night_shift"):
        return False, "night shift is off"
    if core.downloaded():
        return False, "a downloaded Ovenbird doesn't push or merge (decision 0015)"
    if parse_api_read(command):
        return True, "a read-only gh api call"
    pr_text = parse_pr_text(command)
    if pr_text:
        return decide_pr_text(pr_text, request.get("cwd") or str(core.ROOT))
    cwd = request.get("cwd") or str(core.ROOT)
    branch = parse_push(command)
    if branch:
        return decide_push(branch, look(branch, cwd))
    merge = parse_merge(command)
    if merge:
        return decide_merge(merge[0], merge[1], look_pr(merge[0], merge[1], cwd))
    return False, "not the exact push or merge the night shift may use"


def permission():
    """The hook itself: read the request on stdin, print an approval or nothing. Never fails
    loudly: for a PermissionRequest hook, exit code 2 means deny."""
    try:
        request = json.loads(sys.stdin.read() or "{}")
        approve, why = decide(request, core.config())
        command = str((request.get("tool_input") or {}).get("command", ""))[:200]
        if approve and not why.startswith(("a read-only", "the Guardian checked")):
            core.journal("action", "night shift: pushed " + why, via="hook")  # it never merges (0020)
        elif not approve and command.startswith(("git push", "gh pr merge", "gh-axi pr merge", "gh pr create",
                                                 "gh pr edit", "gh pr comment")):
            core.journal("permission", "night shift: asked the human (%s): %s" % (why, command), via="hook")
        if approve:
            print(json.dumps(ALLOW))
    except BaseException:  # noqa: B036 — any doubt falls through to the human's prompt
        pass
    return 0


# ---------------------------------------------------------------- cos hook pretool (0017)
#
# Claude Code matches permission rules against a command as it's written, so `cos  clean apply`
# (two spaces) or `cos 'clean' apply` slips past the ask for `cos clean apply*`, while cos
# itself reads the same argv. Before every Bash call, this reads the command the way a shell
# would, writes each cos call the canonical way, and asks the human when that matches one of
# the checked-in ask rules. It only ever adds a card.

OPERATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
ASK = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}


def _is_cos(token):
    return token in ("cos", "bin/cos", "./bin/cos") or token.endswith("/bin/cos")


PLAIN = re.compile(r"[A-Za-z0-9._-]+")


def _tokens(text, posix):
    lex = shlex.shlex(text, posix=posix, punctuation_chars=";&|()")
    lex.whitespace_split = True
    lex.commenters = ""  # `#` in a word isn't a comment to a shell, and mustn't hide what follows
    return list(lex)


def cos_calls(command):
    """Every cos call in a shell command -> [(canonical, words)]: "cos clean apply x --yes", and
    the leading subcommand words as written, up to the first that isn't a plain word (a quote,
    a redirection, `$…`, braces). None when the command runs cos and can't be read for sure."""
    text = str(command or "")
    if not re.search(r"(^|[^\w-])cos\b", text):
        return []
    text = text.replace("\\\n", "").replace("\n", " ; ")  # line continuations, then one command a line
    # A cos call anywhere in the text, inside `$( )`, backticks or quotes too.
    runs_cos = any(_is_cos(piece) for piece in re.split(r"[\s;&|()`\"'{}<>$]+", text))
    try:
        cooked, raw = _tokens(text, True), _tokens(text, False)
    except ValueError:
        return None if runs_cos else []
    if len(cooked) != len(raw):
        return None
    calls = []
    for i, token in enumerate(cooked):
        if not _is_cos(token):
            continue
        argv, plain = [], []
        for c, r in zip(cooked[i + 1:], raw[i + 1:]):
            if c in OPERATORS:
                break
            argv.append(c)
            if len(plain) == len(argv) - 1 and PLAIN.fullmatch(r):
                plain.append(r)
        calls.append((" ".join(["cos"] + argv), plain, len(plain) < len(argv)))
    if runs_cos and ("`" in text or "$(" in text or "<(" in text):
        return None
    return calls


def ask_patterns(root=None):
    """The checked-in ask rules for cos, as glob patterns over "cos …"."""
    try:
        with open(os.path.join(str(root or core.ROOT), ".claude", "settings.json")) as f:
            asks = json.load(f)["permissions"]["ask"]
    except Exception:
        return None
    return [a[len("Bash("):-1] for a in asks if a.startswith("Bash(cos ") and a.endswith(")")]


def pretool_decision(command, patterns):
    """-> why to ask, or None for no opinion."""
    import fnmatch
    calls = cos_calls(command)
    if calls is None:
        return "Ovenbird can't read this command for sure, and it runs cos"
    if calls and patterns is None:
        return "Ovenbird couldn't read its own ask rules"
    for call, plain, odd in calls:
        if any(fnmatch.fnmatchcase(call, p) for p in patterns):
            return "`%s` changes something" % call[:120]
        if odd:
            # A word that isn't plain where a subcommand could still be chosen: it might become one.
            prefix = " ".join(["cos"] + plain)
            literal = [p.split("*", 1)[0].rstrip() for p in patterns]
            if any(l == prefix or l.startswith(prefix + " ") for l in literal):
                return "`%s …` is written in a way Ovenbird can't read for sure" % prefix[:120]
    return None


# ---------------------------------------------------------------- the Guardian over gh text
#
# With `gh *` allowed (0013), no prompt is ever about to show for the owner, so the
# PermissionRequest hook's check of pull request text never ran (Fable's review, F5/F8). This
# one runs before every Bash call: it reads what a gh command would publish and denies it when
# the Guardian finds a problem. A deny goes back to Claude, never to a card.

GH_TEXT = {("pr", "create"), ("pr", "edit"), ("pr", "comment"), ("pr", "review"), ("issue", "create"),
           ("issue", "edit"), ("issue", "comment"), ("release", "create"), ("release", "edit")}
TEXT_FLAGS = {"--title", "-t", "--body", "-b", "--notes", "-n"}
FILE_FLAGS = {"--body-file", "-F", "--notes-file"}
API_FIELDS = {"-f", "--raw-field", "-F", "--field"}
# Where a body file may come from: the repository (or a worktree) and the temp folder.
TEMP_DIRS = ("/private/tmp", "/private/var/folders", "/tmp", "/var/folders")
READABLE = "write it as gh … --title \"…\" --body-file <file>, so Ovenbird can read what it publishes"
_START = r"(?:^|[;&|(]\s*|\n\s*)(?:\w+=\S*\s+)*gh(?:-axi)?\s+"
GH_AT_START = re.compile(_START + r"(?:pr|issue|release|api)\b")
# A gh command that publishes text, at a command's start: these can be denied as unreadable.
GH_TEXT_AT_START = re.compile(_START + r"(?:pr\s+(?:create|edit|comment|review)|issue\s+(?:create|edit|comment)"
                              r"|release\s+(?:create|edit)|api\b[^\n;&|]*\s(?:-f|-F|--field|--raw-field|--input|-X)\b)")


def gh_calls(command):
    """Every gh or gh-axi call at a command's start -> [(raw words, cooked words)], or None
    when the command can't be read."""
    text = str(command or "").replace("\\\n", "").replace("\n", " ; ")
    try:
        cooked, raw = _tokens(text, True), _tokens(text, False)
    except ValueError:
        return None
    if len(cooked) != len(raw):
        return None
    calls, start = [], True
    for i, c in enumerate(cooked):
        if c in OPERATORS:
            start = True
            continue
        if start and re.fullmatch(r"\w+=.*", c):  # FOO=1 gh …
            continue
        if start and c in ("gh", "gh-axi"):
            j = i + 1
            while j < len(cooked) and cooked[j] not in OPERATORS:
                j += 1
            calls.append((raw[i + 1:j], cooked[i + 1:j]))
        start = False
    return calls


def _body_file_ok(path, cwd):
    real = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    top = core.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], timeout=5).out.strip()
    places = [os.path.realpath(top)] if top else []
    places += [os.path.realpath(p) for p in TEMP_DIRS] + [os.path.realpath(os.path.expanduser("~/.claude-os/dev"))]
    return real if any(real == p or real.startswith(p.rstrip("/") + "/") for p in places) else None


def _gh_text(raw, cooked, cwd):
    """One gh call -> (texts, None) or (None, why it's denied); ([], None) when it publishes no text."""
    if len(cooked) >= 2 and (cooked[0], cooked[1]) in GH_TEXT:
        sub = cooked[1]
    elif cooked[:1] == ["api"] and any(w.split("=", 1)[0] in API_FIELDS | {"--input", "-X", "--method"}
                                       for w in cooked[1:]):
        sub = "api"  # an api call that writes; a read (`gh api … --jq '…'`) publishes nothing
    else:
        return [], None
    if any(re.search(r"[$`]|<\(|>\(", r) for r in raw):
        return None, "this gh command's text has a `$`, backticks or a substitution: " + READABLE
    texts, files, i = [], [], 0
    while i < len(cooked):
        w = cooked[i]
        flag, value = (w.split("=", 1) + [None])[:2] if w.startswith("--") and "=" in w else (w, None)
        takes = flag in TEXT_FLAGS | FILE_FLAGS | (API_FIELDS if sub == "api" else set()) | {"--input"}
        if takes and value is None:
            value = cooked[i + 1] if i + 1 < len(cooked) else None
            i += 1
        i += 1
        if not takes or value is None:
            continue
        if sub == "api" and flag in API_FIELDS:
            key, _, val = value.partition("=")
            if flag in ("-F", "--field") and val.startswith("@"):
                files.append(val[1:])
            else:
                texts.append(("field", val))
        elif flag in FILE_FLAGS or flag == "--input":
            files.append(value)
        else:
            texts.append(("title" if flag in ("--title", "-t") else "body", value))
    for path in files:
        if path == "-":
            return None, "a body from stdin can't be checked: " + READABLE
        real = _body_file_ok(path, cwd)
        if not real:
            return None, "the body file isn't in this repository or the temp folder (never a private folder)"
        if not os.path.isfile(real):
            return None, "couldn't read the body file"
        if os.path.getsize(real) > 256 * 1024:
            return None, "the body file is too big to check"
        with open(real, errors="replace") as f:
            texts.append(("body file", f.read()))
    return texts, None


def gh_text_decision(command, cwd):
    """-> why to deny, or None. Only commands that publish text through gh are judged; an error
    while judging one denies, and any other command gets no opinion."""
    from . import guard
    if not GH_AT_START.search(str(command or "")):
        return None
    publishes = bool(GH_TEXT_AT_START.search(str(command or "")))
    try:
        calls = gh_calls(command)
        if calls is None:
            return ("Ovenbird can't read this command, and it publishes text through gh: " + READABLE) if publishes else None
        for raw, cooked in calls:
            texts, why = _gh_text(raw, cooked, cwd)
            if why:
                return why
            problems = guard.text_problems(texts) if texts else []
            if problems:
                kinds = sorted({p.split(": ", 1)[-1] for _, p in problems})
                return "the Guardian found %s in what this would publish; nothing was sent" % ", ".join(kinds)
    except Exception:
        return "Ovenbird couldn't check what this gh command would publish" if publishes else None
    return None


DENY = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}}


def pretool():
    """The PreToolUse hook: print a deny, an ask, or nothing. A deny is the Guardian over what a
    gh command would publish. An ask is a cos call that changes something. Any other error is
    no opinion: the normal rules still apply, and they ask for the canonical spellings."""
    try:
        request = json.loads(sys.stdin.read() or "{}")
        if request.get("tool_name") != "Bash":
            return 0
        command = (request.get("tool_input") or {}).get("command")
        try:
            denied = gh_text_decision(command, request.get("cwd") or os.getcwd())
        except Exception:
            denied = None  # only a gh text command is ever denied; gh_text_decision says so itself
        if denied:
            out = json.loads(json.dumps(DENY))
            out["hookSpecificOutput"]["permissionDecisionReason"] = denied
            print(json.dumps(out))
            return 0
        why = pretool_decision(command, ask_patterns())
        if why:
            out = json.loads(json.dumps(ASK))
            out["hookSpecificOutput"]["permissionDecisionReason"] = why
            print(json.dumps(out))
    except BaseException:  # noqa: B036
        pass
    return 0


# ---------------------------------------------------------------- cos hook check

def merge_command(number, sha):
    return "gh pr merge %d --squash --delete-branch --match-head-commit %s" % (number, sha)


def check_pr(number, cwd=None):
    """Is #number ready for its guardian review and merge? -> (ready, why, the exact command).
    The pull request is judged whatever the Night shift switch says (0020): the switch only
    decides whether the hook may run git and gh for a clone's Claude."""
    view = core.run(["gh", "pr", "view", str(number), "--json", "headRefOid"], cwd=cwd or os.getcwd(), timeout=15)
    try:
        sha = json.loads(view.out).get("headRefOid") if view.ok else None
    except (ValueError, AttributeError):
        sha = None
    if not sha or not SHA.fullmatch(sha):
        return False, "couldn't read pull request #%d" % number, None
    command = merge_command(number, sha)
    cfg = core.config()
    cfg["autonomy"] = dict(cfg.get("autonomy") or {}, night_shift=True)
    _, why = decide({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or os.getcwd()}, cfg)
    return why.startswith(READY), why, command


def waiting(cwd=None):
    """The night shift's open pull requests and what each waits for, or None if GitHub
    couldn't be asked. Ones that touch the gate list exactly which safety files. A background
    run never asks: it would be GitHub with the human's login (Fable's review, F12)."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return None
    r = core.run(["gh", "pr", "list", "--state", "open", "--limit", "50", "--json", "number,title,headRefName,url"],
                 cwd=cwd or str(core.ROOT), timeout=20)
    try:
        prs = json.loads(r.out) if r.ok else None
    except ValueError:
        prs = None
    if not isinstance(prs, list):
        return None
    rows = []
    for pr in prs:
        if not BRANCH.fullmatch(str(pr.get("headRefName"))):
            continue
        approve, why, command = check_pr(pr["number"], cwd)
        rows.append({"number": pr["number"], "title": pr.get("title"), "branch": pr["headRefName"], "url": pr.get("url"),
                     "ready": approve, "why": why, "command": command})
    return rows


def render_waiting(rows):
    if rows is None:
        print("Couldn't ask GitHub about the night shift's pull requests.")
    elif not rows:
        print("No night shift pull requests are open.")
    for r in rows or []:
        print("#%d %s (%s)\n    %s\n    %s" % (r["number"], r["title"], r["branch"],
                                          r["why"] if r["ready"] else "waits: " + r["why"], r["url"]))


def main(args):
    if args.hook_cmd == "permission":
        return permission()
    if args.hook_cmd == "pretool":
        return pretool()
    target = args.target
    if os.environ.get("CLAUDE_OS_DAEMON") and (target is None or target.isdigit()):
        core.die("a background run doesn't ask GitHub: it would be the human's login", 3)
    if target is None:
        rows = waiting(os.getcwd())
        core.emit(rows, args.json, render_waiting)
        return 0 if rows is not None else 1
    if target.isdigit():
        approve, why, command = check_pr(int(target))
        core.emit({"pr": int(target), "ready": approve, "why": why, "command": command}, args.json,
                  lambda d: print(("✓ %s: %s" % (d["why"], d["command"])) if d["ready"] else "✗ waits: " + d["why"]))
        return 0 if approve else 1
    approve, why = decide({"tool_name": "Bash", "tool_input": {"command": "git push -u origin %s" % target},
                           "cwd": os.getcwd()}, core.config())
    core.emit({"branch": target, "approve": approve, "why": why}, args.json,
              lambda d: print(("✓ would push on its own: " if d["approve"] else "✗ would ask the human: ") + d["why"]))
    return 0 if approve else 1
