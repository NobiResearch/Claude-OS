"""cos hook — Ovenbird's tripwires around Claude's own cos, git and gh calls.

- `cos hook pretool` is a PreToolUse hook (decision 0017). Before every Bash call it asks for a
  cos call that changes something, however it's spelled; it denies a gh command when the
  Guardian finds a problem in the text it would publish; and in a downloaded copy it denies gh
  and git push.
- `cos hook check <branch|PR>` answers without acting. Would this push go out clean: a night/*
  branch of this repository, every commit and message read by the Guardian, nothing in
  `.github/` (CI runs a branch's workflow the moment it's pushed)? Is this pull request ready
  for its guardian review (decision 0020), and what's the exact merge command? With no
  argument it lists the night's pull requests and what each waits for.

Nothing here approves anything. Until decision 0024 a PermissionRequest hook, behind the Night
shift switch, approved pushes and pull request text for Claude. The owner's own settings allow
git and gh (0013), so it never ran for them, and anyone else's clone gets Claude Code's normal
card for both (0017). These are tripwires against drift and mistakes, not a wall: Claude works
with the human's own GitHub login.
"""

import json
import os
import re
import shlex
import sys

from . import core

BRANCH = re.compile(r"night/[A-Za-z0-9._-]+")
SHA = re.compile(r"[0-9a-f]{40}")
# Every pull request gets a guardian agent's review before it merges (decision 0020), so
# `cos hook check` never calls one ready to merge: at best it's ready for that review.
READY = "ready once a guardian agent has reviewed it (0020)"
DOWNLOADED = "a downloaded Ovenbird doesn't push or merge (decision 0015)"
GITHUB = re.compile(r"(?:https://github\.com/|git@github\.com:)([\w.-]+)/([\w.-]+?)(?:\.git)?$")
# The files a guardian's review reads first (every pull request gets one, 0020), and the ones
# the human's update cards, evolve's --reviewed and the boot banner single out. They
# include the code these checks lean on (core, cli, evolve's guard_branch), the server and
# the app's Allow/Deny path, so one night's merge can't loosen the next.
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
    like a new file in docs/. -z: otherwise git quotes a name with a non-ASCII byte, a quote
    or a backslash, and ".github/workflows/ø.yml" in quotes wouldn't look protected."""
    r = git("diff", "--no-renames", "--name-only", "-z", "%s...%s" % (base, branch))
    return [p for p in r.out.split("\0") if p] if r.ok else None


def clean_main(base):
    """`cos hook check` runs from the live checkout, so that checkout must be main with nothing
    of the gate changed locally: no edits, no untracked files, no commits origin hasn't got."""
    from . import evolve
    root = str(core.ROOT)
    def git(*args):
        return core.run(["git", "-C", root] + list(args), timeout=10)
    if git("symbolic-ref", "--short", "HEAD").out != evolve.main_branch():
        return False
    status = git("status", "--porcelain", "--", "lib", "bin", ".claude", "CLAUDE.md", "etc", "githooks")
    local = git("diff", "--no-renames", "--name-only", base, "HEAD")
    return status.ok and not status.out.strip() and local.ok and not any(protected(p) for p in local.out.splitlines())


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
        return "the live checkout isn't a clean main"
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
        return False, "changes CI (%s): a branch's workflow runs once it's pushed, so that push waits for the human's yes" % ", ".join(ci[:3])
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


MENTIONS_COS = re.compile(r"(^|[^\w-])cos\b")
PIECES = r"[\s;&|()`\"'{}<>$]+"
TOO_LONG = 16 * 1024  # longer and the shell regexes get slow (the hook has 10 s); no night's command is
# What the quote reading here can't follow: a heredoc (its lines aren't commands), $'…' (its \'
# doesn't end it), a substitution (it can be the command itself: `$(which sh) -c '…'`, `$(true)cos`)
# and a comment (its `don't` isn't a quote; found outside quotes). A command with one is read
# whole, as this hook read every command before friction #35.
UNFOLLOWED = re.compile(r"<<(?!<)|\$'|`|\$\(|<\(|>\(")
COMMENT = re.compile(r"(?:^|[\s;&|()])#")
CONTINUED = re.compile(r"(?<!\\)((?:\\\\)*)\\\n")  # a backslash-newline whose backslash isn't escaped
ASSIGNS = re.compile(r"\w+\+?=")


def _names_cos(text):
    """Is cos one of the words, wherever it is: in quotes, `$( )` or braces, or given to a name
    (`c=cos`)? Not a path like lib/cos."""
    return any(_is_cos(piece) for piece in re.split(PIECES, text.replace("=", " ")))


def _segments(text):
    """The text cut where the shell starts a new command (; & && | || and newlines), outside
    quotes and escapes; `2>&1` and `&>` are redirections, not cuts. Each cos call is then read
    on its own, so text in another command (a commit message's escaped quotes) can't make it
    unreadable (friction #35)."""
    out, cur, quote, i = [], [], None, 0
    while i < len(text):
        c = text[i]
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 1
            elif c == quote:
                quote = None
        elif c == "\\" and i + 1 < len(text):
            cur += [c, text[i + 1]]
            i += 1
        elif c in "'\"":
            quote = c
            cur.append(c)
        elif c in ";|" or (c == "&" and not (cur and cur[-1] in "<>") and text[i + 1:i + 2] != ">"):
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return [s for s in out if s.strip()]


def cos_calls(command):
    """Every cos call in a shell command -> [(canonical, words)]: "cos clean apply x --yes", and
    the leading subcommand words as written, up to the first that isn't a plain word (a quote,
    a redirection, `$…`, braces). None when the command runs cos and can't be read for sure.

    A plain command is read one simple command at a time (_segments), so text in another one
    (a commit message's escaped quotes) can't make a cos call unreadable (friction #35). Each
    with a cos word gets _whole_cos_calls alone, and one that has what the quote reading can't
    follow gets it whole. One that names cos and starts a shell, or runs a variable, asks."""
    text = str(command or "")
    if not MENTIONS_COS.search(text):
        return []
    if len(text) > TOO_LONG:
        return None
    text = CONTINUED.sub(r"\1", text).replace("\n", " ; ")  # line continuations, then one command a line
    if _names_cos(text) and STARTS_SHELL.search(_bare(text)):
        return None  # eval, sh -c, `| sh`, `zsh <<<`: a shell runs text it read as data, maybe cos
    if UNFOLLOWED.search(text) or COMMENT.search(_bare(text)):
        return _whole_cos_calls(text)
    try:
        _tokens(text, True)
    except ValueError:
        return _whole_cos_calls(text)  # no real command ends inside a quote: the reading drifted
    if _names_cos(text) and RUNS_VARIABLE.search(_bare(text)):
        return None  # `x='cos …'; $x` runs what the variable holds
    calls = []
    for segment in _segments(text):
        found = _whole_cos_calls(segment) if _has_cos_word(segment) else []
        if found is None:
            return None
        calls += found
    return calls


def _has_cos_word(segment):
    """Is cos a word in this simple command: glued to quotes (`"$x"cos`), or a value that can run
    later (`x='cos …'; env $x`)? A cos inside a commit message's quotes isn't: it runs nothing,
    so its escapes can't make anything ask."""
    try:
        return _names_cos(_bare(segment)) or any(_is_cos(word) or (ASSIGNS.match(word) and _names_cos(word))
                                                 for word in _tokens(segment, True))
    except ValueError:
        return True


def _whole_cos_calls(text):
    """The text at once, with a cos word anywhere counting, in quotes too: it asks unless the
    shell's reading and the raw one agree, and whenever a substitution could run cos."""
    runs_cos = _names_cos(text)
    try:
        cooked, raw = _tokens(text, True), _tokens(text, False)
    except ValueError:
        return None if runs_cos else []
    if len(cooked) != len(raw):
        return None
    if runs_cos and (SUBSTITUTES.search(text) or "$'" in text):
        return None  # what a substitution or $'…' (whose \' doesn't end it) turns into isn't known
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
# With `gh *` allowed (0013), no prompt is ever about to show for the owner, so a check that
# waited for one never ran (Fable's review, F5/F8). This one runs before every Bash call: it reads what a gh command would publish and denies it when
# the Guardian finds a problem. A deny goes back to Claude, never to a card.

PUBLISHES = {(s, v) for s in ("pr", "issue") for v in ("create", "edit", "comment", "close", "reopen")} | {
    ("pr", "review"), ("pr", "merge"), ("release", "create"), ("release", "edit"),
    ("discussion", "create"), ("discussion", "edit"), ("discussion", "comment")}
REFUSED = {("gist", "create"): "gh gist uploads files: those are for the human to publish",
           ("gist", "edit"): "gh gist uploads files: those are for the human to publish",
           ("alias", "set"): "a gh alias can hide what a later command publishes",
           ("alias", "import"): "a gh alias can hide what a later command publishes"}
PUBLISHES |= {("label", "create"), ("label", "edit"), ("repo", "create"), ("repo", "edit"), ("workflow", "run"),
              ("project", "create"), ("project", "edit"), ("project", "item-create"), ("project", "item-edit")}
# gh's own alias: `gh pr new` is `gh pr create` (and so for issue, repo, release and gist).
PUBLISHES |= {(s, "new") for s in ("pr", "issue", "repo", "release")}
REFUSED[("gist", "new")] = REFUSED[("gist", "create")]
SUBCOMMANDS = {"pr", "issue", "release", "discussion", "gist", "alias", "api", "label", "repo", "workflow", "project"}
# Text flags that only one subcommand has (elsewhere the same letter means something else).
OWN_TEXT = {"label": {"--description", "-d"}, "repo": {"--description", "-d", "--homepage", "-h"}}
FIELDS = {"api", "workflow"}  # -f/-F key=value: a workflow's inputs show on its public run page
# Flags that are on/off switches for one command, though they take text for another.
SWITCHES = {("pr", "review"): {"--comment", "-c", "--approve", "-a", "--request-changes", "-r"}}
LONG_TEXT = {"--title", "--body", "--notes", "--subject", "--comment", "--author-email"}
LONG_FILE = {"--body-file", "--notes-file", "--recover"}
SHORT_TEXT = {"-t", "-b", "-n", "-c", "-A"}
SHORT_FILE = {"-F"}
API_FIELD = {"-f", "-F", "--field", "--raw-field"}
API_WRITES = API_FIELD | {"--input", "-X", "--method"}
GLOBAL_VALUE = {"-R", "--repo", "--hostname"}  # before the subcommand; their values aren't text
# Short flags whose value isn't text: skipped with it, unless the next word is itself a flag.
SHORT_VALUE = {"-R", "-B", "-H", "-a", "-l", "-m", "-p", "-r", "-T", "-X", "-q", "-j"}
SESSION_TEMP = "/private/tmp/claude-%d" % os.getuid()  # Claude Code's own temp: the session scratchpad
EXTRA_BODY_PLACES = []  # tests add their temp folder
READABLE = ("run gh on its own and write the text plainly: --title \"…\" --body-file <file> (for gh api, "
            "-F key=@<file>, --input <file>, or quote the whole key=value), so Ovenbird can read what it publishes")
MENTIONS_GH = re.compile(r"(?<![\w-])gh(?:-axi)?(?![\w-])")
NAMES_PUBLISHING = re.compile(r"\b(?:pr|issue|discussion)\s+(?:create|new|edit|comment|review|close|reopen|merge)\b"
                              r"|\b(?:release|gist|label|repo)\s+(?:create|new|edit)\b|\balias\s+(?:set|import)\b"
                              r"|\bworkflow\s+run\b|\bproject\s+(?:create|edit|item-create|item-edit)\b"
                              r"|\bapi\b[^\n;&|]*\s(?:-f|-F|--field|--raw-field|--input|-X|--method)")  # -XPOST too
# Ways a command can run text as a command. Substitutions work inside double quotes, so they're
# searched in _active text; a shell given a string or stdin, eval, source and `.` only run
# outside all quotes, so they're searched in _bare text ("Open source the brief" is a title).
SUBSTITUTES = re.compile(r"`|\$\(|<\(|>\(")
_SHELL = r"(?:[^\s;&|()]*/)?(?:ba|z|da|k)?sh"  # bounded at ( and ;, or a run of `(bin/sh` takes minutes
SHELLS = re.compile(r"\beval\b|\bsource\b|(?:^|[;&|(]\s*)\.\s+\S"
                    r"|(?:^|[\s;&|(])" + _SHELL + r"\b[^;&|]*\s-[A-Za-z]*[cs]"  # sh -c, bash -lc, -o x -c
                    r"|\|\s*" + _SHELL + r"\b")
# For cos_calls: a shell started anywhere in a command. eval and source only count as commands,
# so `grep eval` and `git log --source` start nothing.
_COMMAND = r"(?:^\s*|[;&|({!]\s*|\b(?:then|do|else|elif|if|while|until|command|builtin|exec|time)\s+)"
STARTS_SHELL = re.compile(_COMMAND + r"(?:eval|source)\b|(?:^|[;&|(]\s*)\.\s+\S"
                          r"|(?:^|[\s;&|(])" + _SHELL + r"\b[^;&|]*\s-[A-Za-z]*[cs]"
                          r"|\|&?\s*" + _SHELL + r"\b"
                          r"|(?:^|[\s;&|(])" + _SHELL + r"\b[^;&|]*<")  # zsh <<<'…', bash < file
RUNS_VARIABLE = re.compile(_COMMAND + r"\$")
FLAG_LIKE = re.compile(r"--?[A-Za-z][\w-]*(?:=.*)?")
REDIRECT = re.compile(r"\d*[<>]&(?:\d+|-)|&>>?")  # 2>&1, >&2, &>: one word, not a cut at `&`


def _is_gh(word):
    return word in ("gh", "gh-axi") or word.endswith(("/gh", "/gh-axi"))


def _global_only(words):
    """Are these words (gh's, before the verb) only -R/--repo/--hostname with their values?"""
    k = 0
    while k < len(words):
        w = words[k]
        if w in GLOBAL_VALUE:
            k += 2
        elif w.startswith(("--repo=", "--hostname=")) or (w.startswith("-R") and len(w) > 2):
            k += 1
        else:
            return False
    return True


def gh_calls(command):
    """Every gh or gh-axi word followed by something that publishes -> [(subcommand, verb, raw
    args, cooked args, cooked words before it, why it's refused or None, gh's own words before
    the verb)]. Found wherever it
    sits, so `env gh`, `command gh` and `{ gh …; }` count too. The subcommand and verb are
    found the way gh finds them, past flags, and any flag before the verb other than
    -R/--repo/--hostname is refused: it might be text this doesn't read. None when the command
    can't be read."""
    text = str(command or "").replace("\\\n", "").replace("\n", " ; ")
    text = REDIRECT.sub(lambda m: m.group(0).replace("&", "@"), text)
    try:
        cooked, raw = _tokens(text, True), _tokens(text, False)
    except ValueError:
        return None
    if len(cooked) != len(raw):
        return None
    calls = []
    for i, word in enumerate(cooked):
        if not _is_gh(word):
            continue
        end = i + 1
        while end < len(cooked) and cooked[end] not in OPERATORS:
            end += 1
        args, rargs = cooked[i + 1:end], raw[i + 1:end]
        k = next((n for n, w in enumerate(args) if w in SUBCOMMANDS), None)
        if k is None:
            continue
        sub = args[k]
        if sub == "api":
            if not any(w.split("=", 1)[0] in API_WRITES or w[:2] in ("-f", "-F", "-X") for w in args):
                continue  # a read publishes nothing
            v, verb = k, ""
        else:
            # The verb the way gh finds it: past -R/--repo/--hostname, the next plain word.
            n = k + 1
            while n < len(args) and (args[n] in GLOBAL_VALUE or args[n].startswith(("--repo=", "--hostname="))
                                     or (args[n].startswith("-R") and len(args[n]) > 2)):
                n += 2 if args[n] in GLOBAL_VALUE else 1
            if n < len(args) and not args[n].startswith("-"):
                v = n
                if (sub, args[v]) not in PUBLISHES and (sub, args[v]) not in REFUSED:
                    continue  # gh pr list --search review: not a verb that publishes
            else:
                # Another flag comes first: whatever it carries isn't read here, so a later
                # publishing verb is refused rather than guessed at.
                v = next((m for m in range(n, len(args)) if not args[m].startswith("-")
                          and ((sub, args[m]) in PUBLISHES or (sub, args[m]) in REFUSED)), None)
                if v is None:
                    continue
            verb = args[v]
        why = None
        if not _global_only(args[:k] + args[k + 1:v]):
            why = "write gh's flags after the verb (gh pr comment 1 --body-file …): " + READABLE
        first = i  # where gh's own command starts
        while first > 0 and cooked[first - 1] not in OPERATORS:
            first -= 1
        if "xargs" in cooked[first:i]:
            why = why or "xargs adds words to this gh command that Ovenbird can't see: " + READABLE
        calls.append((sub, verb, rargs[v + 1:], args[v + 1:], cooked[:i], why, args[:v]))
    return calls


def _under(path, places):
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in places)


def _body_file_ok(path, cwd):
    """The body file's real path when it may be published, or None: only from the repository,
    one of its worktrees or the session's temp folder, and never a private folder outside them
    (wherever the home folder is: a sandbox puts it under /private/tmp)."""
    real = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    top = core.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], timeout=5).out.strip()
    trees = [l.split(" ", 1)[1] for l in core.run(["git", "-C", cwd, "worktree", "list", "--porcelain"],
                                                     timeout=5).out.splitlines() if l.startswith("worktree ")]
    ours = [os.path.realpath(p) for p in ([top] if top else []) + trees]
    if not _under(real, ours + [os.path.realpath(p) for p in [SESSION_TEMP] + EXTRA_BODY_PLACES]):
        return None
    home = os.path.realpath(os.path.expanduser("~"))
    if _under(real, [os.path.join(home, p) for p in core.PRIVATE_DIRS]) and not _under(real, ours):
        return None
    return real


def _active(text):
    """The text without what the shell won't expand: single-quoted spans (only outside double
    quotes: in "it's" the ' is a letter) and backslash-escaped characters. `$` and backticks
    left in it are live."""
    out, quote, i = [], None, 0
    while i < len(text):
        c = text[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            out.append("_")
            i += 1
        elif c == "'" and quote is None:
            quote = "'"
        else:
            if c == '"':
                quote = None if quote == '"' else '"'
            out.append(c)
        i += 1
    return "".join(out)


def _bare(text):
    """The text outside all quotes, the only place a shell word like eval or `sh -c` runs."""
    out, quote, i = [], None, 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"':
                i += 1
            out.append(" ")
        elif c == "\\":
            out.append("_")
            i += 1
        elif c in "'\"":
            quote = c
            out.append(" ")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _tilde(raw):
    """Would the shell turn a ~ in this word into the home folder? At its start, or after = or
    :, outside quotes."""
    return bool(re.search(r"(?:^|[=:])~", re.sub(r"'[^']*'|\"[^\"]*\"", "''", raw)))


# What may use the body file earlier in the same command: commands that only read it.
READERS = {"cat", "head", "tail", "wc", "grep", "less", "more", "file", "ls", "stat", "test", "[", "diff", "shasum"}
MOVES = {"cd", "pushd", "popd"}


def _used_before(path, before, cwd):
    """-> why the body file can't be trusted, or None. Earlier in the command it may only be
    read (`cos guard --text f`, `cat f`): a write, or a command that might write it, means what
    gets checked isn't what gets sent."""
    real = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    moved = any(w in MOVES for w in before)
    segment = []
    for k, w in enumerate(before):
        if w in OPERATORS:
            segment = []
            continue
        segment.append(w)
        # Redirections, with &> and &>> as REDIRECT left them (@>, @>>).
        redirect = re.match(r"(?:\d*|@)>>?\|?", w)
        target = before[k + 1] if w in (">", ">>", ">|", "@>", "@>>") and k + 1 < len(before) else (
            re.sub(r"^(?:\d*|@)>>?\|?", "", w) if redirect and len(w) > len(redirect.group(0)) else None)
        if target is not None and re.fullmatch(r"@(?:\d+|-)", target):
            target = None  # 2>&1 copies a file descriptor: no file is written
        if target is not None and moved:
            return "after a cd, nothing may be written before gh in the same command: what's checked must be what's sent"
        # dd of=f, --output=f: the path can sit after an =.
        names = {w} | ({target} if target else set()) | ({w.split("=", 1)[1]} if "=" in w else set())
        if not any(n == path or os.path.realpath(os.path.join(cwd, os.path.expanduser(n))) == real for n in names):
            continue
        command = next((s for s in segment if not re.fullmatch(r"\w+=.*", s)), "")
        reads = command in READERS or (_is_cos(command) and "guard" in segment)
        if target is not None or not reads:
            return "the body file is written or used in the same command, so what's checked isn't what's sent: write it first"
    return None


def _gh_text(sub, verb, raw, cooked, before, cwd):
    """One publishing gh call -> (texts, None) or (None, why it's denied)."""
    if (sub, verb) in REFUSED:
        return None, REFUSED[(sub, verb)]
    if any(w.startswith("--attach") for w in cooked):
        return None, "attachments (pictures, files) are for the human to publish, not Claude"
    if any(re.search(r"[$`]|<\(|>\(", _active(r)) for r in raw):
        return None, "this gh command's text has a `$`, backticks or a substitution: " + READABLE
    switches = SWITCHES.get((sub, verb), set())
    fields = API_FIELD if sub in FIELDS else set()
    own = OWN_TEXT.get(sub, set())
    texts, files, i = [], [], 0
    while i < len(cooked):
        w = cooked[i]
        i += 1
        if w in switches:
            continue
        written = raw[i - 1]  # the value as typed, for the ~ check: the flag word itself when attached
        if w.startswith("--"):
            flag, eq, value = w.partition("=")
            kinds = LONG_TEXT | LONG_FILE | own | fields | ({"--input"} if sub == "api" else set())
            if flag not in kinds:
                continue
            if not eq:
                written = raw[i] if i < len(raw) else ""
                value, i = (cooked[i] if i < len(cooked) else None), i + 1
        elif w.startswith("-") and len(w) > 1:
            if len(w) > 2:  # -bX, -b=X, -F/path, -cb: gh's flag parser reads these more ways than one
                return None, "write each short flag on its own, with its value after a space: " + READABLE
            if w in SHORT_VALUE and w not in fields | own:
                if i < len(cooked) and not cooked[i].startswith("-"):
                    i += 1
                continue
            if w not in SHORT_TEXT | SHORT_FILE | fields | own:
                continue
            written = raw[i] if i < len(raw) else ""
            flag, value, i = w, (cooked[i] if i < len(cooked) else None), i + 1
        else:
            continue
        if value is None or FLAG_LIKE.fullmatch(value):
            # Its value is missing or is another flag: gh would read the words some other way.
            return None, "%s needs its value right after it: %s" % (flag, READABLE)
        if flag not in LONG_FILE | SHORT_FILE | {"--input"} and _tilde(written):
            return None, "an unquoted ~ in %s becomes your home folder: quote it, or %s" % (flag, READABLE)
        if flag in fields or flag == "--input":
            if flag in ("-F", "--field") and value.partition("=")[2].startswith("@"):
                files.append(value.partition("=")[2][1:])
            elif flag == "--input":
                files.append(value)
            texts.append(("field", value))  # its key as well as its value
        elif flag in LONG_FILE | SHORT_FILE:
            files.append(value)
        else:
            texts.append(("title" if flag in ("--title", "-t", "--subject") else "body", value))
    for path in files:
        if path == "-":
            return None, "a body from stdin can't be checked: " + READABLE
        if not path.startswith(("/", "~")) and any(w in MOVES for w in before):
            return None, "after a cd, give the body file's full path: what's checked must be what's sent"
        used = _used_before(path, before, cwd)
        if used:
            return None, used
        real = _body_file_ok(path, cwd)
        if not real:
            return None, "the body file isn't in this repository, a worktree of it or the session's temp folder"
        if not os.path.isfile(real):
            return None, "couldn't read the body file"
        if os.path.getsize(real) > 256 * 1024:
            return None, "the body file is too big to check"
        with open(real, errors="replace") as f:
            texts.append(("body file", f.read()))
    return texts, None


def gh_text_decision(command, cwd):
    """-> why to deny, or None. Only commands that publish through gh are judged; an error
    while judging one denies, and any other command gets no opinion."""
    text = str(command or "")
    if not MENTIONS_GH.search(text):
        return None
    publishes = bool(NAMES_PUBLISHING.search(text))
    try:
        from . import guard
        if publishes and (SUBSTITUTES.search(_active(text)) or SHELLS.search(_bare(text))):
            return ("this command publishes through gh and also runs text as a command (a substitution, backticks, "
                    "sh -c, | sh, eval or source): " + READABLE)
        calls = gh_calls(text)
        if calls is None:
            return ("Ovenbird can't read this command, and it publishes text through gh: " + READABLE) if publishes else None
        for sub, verb, raw, cooked, before, refused, _ in calls:
            if refused:
                return refused
            texts, why = _gh_text(sub, verb, raw, cooked, before, cwd)
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


# ---------------------------------------------------------------- someone else's pull request
#
# A pull request from anyone else merges, closes or gets a comment only after the human's yes
# (0014, 0018), and its text is read in the one session that can do all of that. So that yes is
# a card (0025). Claude's own pull requests never show one (0013). A lookup that fails is a deny,
# not a card: Claude reads why and tries again, so it can't hold a night, and nothing goes out.

ON_A_PR = {"merge", "close", "comment", "review", "edit", "reopen"}
NAMES_A_PR_VERB = re.compile(r"\bpr\b.*\b(?:%s)\b" % "|".join(sorted(ON_A_PR)), re.S)
PR_LINK = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+/?")
HEREDOC = re.compile(r"(?<!<)<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|\\?([\w.-]+))")
MOVES = {"cd", "pushd", "popd"}
NAME_ONE_PR = ("name one pull request a command, by its number or link, and write any other number as --flag=value, "
               "so Ovenbird can check whose it is: one from anyone else takes the human's yes (0014)")
NAME_THE_REPO = ("this command moves before gh runs, so name the repository with -R owner/name or a link, so "
                 "Ovenbird checks the right pull request: one from anyone else takes the human's yes (0014)")
COULDNT_READ = "a shell reads this command's text, so run gh on its own, so Ovenbird can check whose pull request it is"
COULDNT_LOOK = "Ovenbird couldn't check whose pull request this is, so nothing was sent. Try again"


def _without_heredocs(text):
    """The text without each heredoc's lines: they're data for a command, not commands. Only one
    that closes: a `1 << 3` or a comment that looks like one must not hide what follows it."""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        found = HEREDOC.search(lines[i]) if "<<" in _bare(lines[i]) else None
        tag = next(g for g in found.groups() if g) if found else None
        close = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == tag), None) if tag else None
        out.append(lines[i])
        i = i + 1 if close is None else close + 1
    return "\n".join(out)


def _gh_commands(text):
    """Each simple command in this text that runs gh or gh-axi -> [(its text, did a command up to
    it move, so gh may act on another repository?)]. A mention isn't one: an `echo`'s words, a
    commit message, a heredoc or a comment can name a pull request without acting on it."""
    found, moved = [], False
    for segment in _segments(CONTINUED.sub(r"\1", _without_heredocs(text)).replace("\n", " ; ")):
        try:
            words = [w for w in _tokens(segment, True) if w not in ("(", ")")]
        except ValueError:
            continue  # gh_text_decision denies a publishing command it can't read
        k = _command_word(words)
        # After a wrapper, a flag's value can read as the command: sudo -u x gh, env -C x gh.
        wrapped = k is not None and any(w.rsplit("/", 1)[-1] in WRAPPERS for w in words[:k])
        moved = moved or (k is not None and words[k] in MOVES) or any(w.startswith("GH_REPO=") for w in words) \
            or (words[:1] == ["env"] and "-C" in words)
        if k is not None and (_is_gh(words[k]) or (wrapped and any(_is_gh(w) for w in words[k:]))):
            found.append((segment, moved))
    return found


def _named_repo(words):
    """The value of gh's -R/--repo among these words, or None. gh takes the last."""
    repo = None
    for i, w in enumerate(words):
        if w in ("-R", "--repo"):
            repo = words[i + 1] if i + 1 < len(words) else None
        elif w.startswith("--repo="):
            repo = w.split("=", 1)[1]
        elif w.startswith("-R") and len(w) > 2:
            repo = w[2:].lstrip("=")
    return repo


def _someone_elses(pr, repo, cwd):
    """Is this pull request from a fork, or by anyone but the signed-in account? None when GitHub
    didn't say. At most 7 s for the hook's 10: a hook that's killed shows no card, so a command
    gets one lookup. A pull request that doesn't say where it's from counts as someone else's."""
    view = core.run(["gh", "pr", "view", pr] + (["-R", repo] if repo else []) + ["--json", "isCrossRepository,author"],
                    timeout=4, cwd=cwd)
    if not view.ok:
        return None
    me = core.run(["gh", "api", "user", "--jq", ".login"], timeout=3, cwd=cwd).out.strip()
    try:
        facts = json.loads(view.out)
        author = str((facts.get("author") or {}).get("login") or "")
    except (ValueError, AttributeError):
        return None
    return None if not me else facts.get("isCrossRepository") is not False or author.lower() != me.lower()


def pr_decision(command, cwd):
    """-> ("ask", why) for acting on someone else's pull request, ("deny", why) when whose it is
    can't be told, or None: for anything else, and for what gh_text_decision already denied."""
    text = str(command or "")
    if not (MENTIONS_GH.search(text) and NAMES_A_PR_VERB.search(text)):
        return None
    if STARTS_SHELL.search(_bare(text)):
        return "deny", COULDNT_READ
    commands = _gh_commands(text)
    acts = [call for segment, _ in commands for call in gh_calls(segment) or []
            if call[0] == "pr" and call[1] in ON_A_PR]
    if not acts:
        return None
    named = [{w for w in cooked if w.isdigit() or PR_LINK.fullmatch(w)} for _, _, _, cooked, _, _, _ in acts]
    repos = {_named_repo(ahead + cooked) for _, _, _, cooked, _, _, ahead in acts}
    if any(len(n) != 1 for n in named) or len(set.union(*named)) != 1 or len(repos) != 1:
        return "deny", NAME_ONE_PR
    pr, repo = named[0].pop(), repos.pop()
    if not repo and not PR_LINK.fullmatch(pr) and any(moved for _, moved in commands):
        return "deny", NAME_THE_REPO
    anothers = _someone_elses(pr, repo, cwd)
    if anothers is None:
        return "deny", COULDNT_LOOK
    if anothers:
        return "ask", "gh pr %s on %s: it's someone else's pull request, which takes your yes (0014, 0018)" % (acts[0][1], pr)
    return None


# ---------------------------------------------------------------- a downloaded copy and GitHub
#
# A copy the app downloaded (0015) doesn't use GitHub or push: core.DOWNLOAD_DENY says so in its
# settings, but those rules match a command's first words, so `env gh …`, a full path or
# `sh -c 'gh …'` get past them. This is the same policy, read the way a shell reads a command.
# A tripwire, not the wall: a download's origin has a push address that goes nowhere.

WRAPPERS = {"env", "command", "exec", "nice", "nohup", "time", "timeout", "gtimeout", "stdbuf", "arch", "xargs", "sudo",
            "caffeinate"}
KEYWORDS = {"if", "then", "elif", "else", "fi", "do", "done", "while", "until", "!", "{", "}"}
SHELL_WORD = re.compile(r"(?:\S*/)?(?:ba|z|da|k)?sh")
GIT_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
INNER = re.compile(r"\$\(([^()`]*)\)|`([^`]*)`|[<>]\(([^()`]*)\)")
MENTIONS_PUSH = re.compile(r"(?<![\w-])push(?![\w-])")


def _command_word(words):
    """Where the command in one simple command starts: past VAR=value, shell keywords (if, do,
    {, !), wrappers like env or nice, and their flags and numbers. -> index, or None (none, or
    `command -v`, which only looks a name up)."""
    k = 0
    while k < len(words):
        w = words[k]
        if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", w) or w.startswith("-") or w.isdigit() or w in KEYWORDS:
            k += 1
        elif w in WRAPPERS or w.endswith(tuple("/" + x for x in WRAPPERS)):
            if w.rsplit("/", 1)[-1] == "command" and k + 1 < len(words) and words[k + 1] in ("-v", "-V"):
                return None
            k += 1
        else:
            return k
    return None


def _git_pushes(args):
    """Is git's subcommand, past its global options, push?"""
    k = 0
    while k < len(args):
        a = args[k]
        if a in GIT_VALUE:
            k += 2
        elif a.startswith("-"):
            k += 1
        else:
            return a == "push"
    return False


def _mask(text):
    """The text, the same length, with what the shell won't expand turned into "_":
    single-quoted spans (outside double quotes) and backslash-escaped characters. A `…` or
    $( ) found in it is live; its position is the same in the text."""
    out, quote, i = list(text), None, 0
    while i < len(text):
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = None
            else:
                out[i] = "_"
        elif c == "\\":
            out[i] = "_"
            if i + 1 < len(text):
                out[i + 1] = "_"
            i += 1
        elif c == "'" and quote is None:
            quote = "'"
        elif c == '"':
            quote = None if quote == '"' else '"'
        i += 1
    return "".join(out)


def runs_github(text, depth=0):
    """Does this shell text run gh or gh-axi, or git … push, as a command? True, False, or None
    when it can't be read for sure."""
    if depth > 3:
        return None
    text = str(text or "").replace("\\\n", "").replace("\n", " ; ")
    # Live substitutions only: in single quotes, `…` and $( ) are text, unless sh -c or eval
    # runs that text, which the branches below read whole.
    masked = _mask(text)
    live = list(INNER.finditer(masked))
    for m in live:
        g = next(n for n in (1, 2, 3) if m.group(n) is not None)
        inner = text[m.start(g):m.end(g)]
        if inner.strip() and runs_github(inner, depth + 1) is not False:
            return True
    if SUBSTITUTES.search(INNER.sub(lambda m: " " * len(m.group(0)), masked)):
        return None  # a substitution this doesn't take apart (nested)
    chars = list(text)
    for m in live:
        chars[m.start():m.end()] = " " * (m.end() - m.start())
    text = REDIRECT.sub(lambda m: m.group(0).replace("&", "@"), "".join(chars))
    try:
        words = _tokens(text, True)
    except ValueError:
        return None
    segment = []
    for w in words + [";"]:
        if w not in OPERATORS:
            segment.append(w)
            continue
        k = _command_word(segment)
        if k is not None:
            cmd, args = segment[k], segment[k + 1:]
            if _is_gh(cmd):
                return True
            if (cmd == "git" or cmd.endswith("/git")) and _git_pushes(args):
                return True
            if cmd in ("eval", "source", "."):
                if runs_github(" ".join(args), depth + 1) is not False:
                    return True
            if SHELL_WORD.fullmatch(cmd):
                c = next((n for n, a in enumerate(args) if a.startswith("-") and not a.startswith("--")
                          and "c" in a[1:]), None)
                if c is not None and c + 1 < len(args) and runs_github(args[c + 1], depth + 1) is not False:
                    return True
        segment = []
    return False


def download_decision(command):
    """-> why to deny, or None. A tripwire for the usual spellings, not the wall (that's the
    push address that goes nowhere). Only ever in a downloaded copy, and only for a command
    that runs gh or pushes; a mere mention (`brew upgrade gh`, a friction note) is fine. The
    text is checked before core.downloaded(), so a command that names neither costs nothing;
    without its quotes and backslashes, so g''h still reaches the real check."""
    text = str(command or "")
    flat = re.sub(r"[\"'\\]", "", text)
    if not (MENTIONS_GH.search(flat) or MENTIONS_PUSH.search(flat)):
        return None
    if not core.downloaded():
        return None
    try:
        runs = runs_github(text)
    except Exception:
        runs = None
    if runs is False:
        return None
    if runs is None:
        return ("Ovenbird can't read this command for sure, and in a downloaded copy it doesn't run gh or "
                "git push (0015): write it plainly, one command")
    return ("a downloaded Ovenbird doesn't use GitHub or push (decision 0015): its code comes with the app. "
            "To work on Ovenbird itself, clone your own fork")


def pretool():
    """The PreToolUse hook: print a deny, an ask, or nothing. A deny is the Guardian over what a
    gh command would publish. An ask is a cos call that changes something, or a gh pr verb on
    someone else's pull request. Any other error is no opinion: the normal rules still apply,
    and they ask for the canonical spellings."""
    try:
        request = json.loads(sys.stdin.read() or "{}")
        if request.get("tool_name") != "Bash":
            return 0
        command = (request.get("tool_input") or {}).get("command")
        try:
            in_download = download_decision(command)  # a downloaded copy only; denies on its own errors
        except Exception:
            in_download = None
        try:
            denied = gh_text_decision(command, request.get("cwd") or os.getcwd())
        except Exception:
            denied = None  # only a gh text command is ever denied; gh_text_decision says so itself
        denied = in_download or denied
        on_a_pr = None
        if not denied:
            try:
                on_a_pr = pr_decision(command, request.get("cwd") or os.getcwd())
            except Exception:
                on_a_pr = ("deny", COULDNT_LOOK)  # only a gh pr verb gets this far
            if on_a_pr and on_a_pr[0] == "deny":
                denied = on_a_pr[1]
        if denied:
            out = json.loads(json.dumps(DENY))
            out["hookSpecificOutput"]["permissionDecisionReason"] = denied
            print(json.dumps(out))
            return 0
        why = on_a_pr[1] if on_a_pr else pretool_decision(command, ask_patterns())
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


def _safety_label(path):
    """Which of the gate's entries a path falls under, never the path itself: a fork names its
    own files, and a file name is text someone else wrote."""
    for entry in PROTECTED:
        if path.startswith(entry):  # the same test protected() makes
            return entry
    if path.startswith("lib/") and not path.startswith("lib/cos/"):
        return "lib/ (a module Python finds before the standard library's)"
    return "compiled Python (__pycache__, .pyc or .pth)"


SAFE_GIT = "git -c core.hooksPath=/dev/null -c core.fsmonitor=false"  # a fork's githooks/ never run


def _fork_paths(sha, cwd):
    """Every path a fork's head commit changes, from local git with --no-renames (GitHub names
    a moved file only by its new path), or why there's no list. Nothing is fetched."""
    def git(*args):
        return core.run(["git", "-C", cwd, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]
                        + list(args), timeout=20)
    if not SHA.fullmatch(sha) or not git("cat-file", "-e", sha + "^{commit}").ok:
        return "its head commit isn't here, and nothing was fetched"
    from . import evolve
    paths = changed(git, "origin/" + evolve.main_branch(cwd), sha)
    return paths if paths is not None else "its head commit is here, but git couldn't list what it changes"


def fork_pr(number, pr, paths=None):
    """A pull request from someone else's fork (0014): never ready from here, it waits for the
    human's yes. Its checks ran the fork's own copy of the workflow, so a green check proves
    nothing. Which safety files it touches comes from `paths` (local git's list, _fork_paths), or
    else, when that's a reason there's none, from GitHub's file list, trusted only when it's
    complete and renames nothing. Nothing of its title, body, comments or file names is
    printed, and no merge command stands on its own: it's in the text, after "only after the
    human's yes". decide_merge still refuses it. -> why it waits."""
    sha = str(pr.get("headRefOid") or "")
    open_ = pr.get("state") == "OPEN"
    lines = ["the human's yes (0014): #%d is from a fork, so its checks ran the fork's own workflow and a "
             "green check proves nothing" % number if open_ else "#%d is from a fork and isn't open" % number]
    if not isinstance(paths, list):
        lines.append(paths if isinstance(paths, str) else "its head commit isn't here, and nothing was fetched")
        files = pr.get("files") if isinstance(pr.get("files"), list) else []
        listed = [f for f in files if isinstance(f, dict) and f.get("path")]
        total = pr.get("changedFiles")
        if not isinstance(total, int) or len(listed) < total:
            lines.append("GitHub listed %d of %s changed files, so which safety files it touches isn't known"
                         % (len(listed), total if isinstance(total, int) else "?"))
            listed = None
        elif any(f.get("changeType") not in ("ADDED", "MODIFIED", "DELETED") for f in listed):
            lines.append("it moves files, and GitHub names a moved file only by its new path, so which safety "
                         "files it touches isn't known until it's fetched")
            listed = None
        paths = [str(f["path"]) for f in listed] if listed is not None else None
    if paths is not None:
        touched = sorted({_safety_label(p) for p in paths if protected(p)})
        lines.append("it changes Ovenbird's safety files: %s" % ", ".join(touched) if touched
                     else "it changes none of Ovenbird's safety files")
    lines.append("test it here before anyone says yes, from the live checkout and never with gh pr checkout: "
                 "%s fetch origin +pull/%d/head:fork-%d; check that git rev-parse fork-%d is %s (a fork can be "
                 "force-pushed); %s diff --no-renames --stat origin/main...fork-%d; its tests in a fresh temp "
                 "clone, sandboxed, with main's code: /usr/bin/python3 -c \"import sys; sys.path.insert(0, 'lib'); "
                 "from cos import evolve; t = evolve.test_commit('fork-%d'); print('tests pass' if t and t.ok "
                 "else 'tests fail or could not run')\"; then git branch -D fork-%d; no swift test or build of it "
                 "without the human" % (SAFE_GIT, number, number, number, sha or "the pinned commit",
                                        SAFE_GIT, number, number, number))
    if open_ and SHA.fullmatch(sha):
        lines.append("only after the human's yes (0014): gh pr merge %d --squash --match-head-commit %s"
                     % (number, sha))
    return "\n    ".join(lines)


def check_push(branch, cwd=None, look=inspect):
    """Would `git push -u origin <branch>` go out clean? -> (ok, why). Only a night/* branch,
    and never from a background job or a downloaded copy (0015)."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return False, "inside a background job"
    if core.downloaded():
        return False, DOWNLOADED
    if not BRANCH.fullmatch(str(branch)) or ".." in branch or branch.endswith((".", ".lock", "main", "master")):
        return False, "only a night/* branch, named plainly"
    return decide_push(branch, look(branch, cwd or os.getcwd()))


def check_pr(number, cwd=None, look_pr=inspect_pr):
    """Is #number ready for its guardian review and merge? -> (ready, why, the exact command).
    One from a fork is never ready (fork_pr), and a downloaded copy merges nothing (0015)."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return False, "inside a background job", None  # it would be GitHub with the human's login
    if core.downloaded():
        return False, DOWNLOADED, None
    view = core.run(["gh", "pr", "view", str(number), "--json", "headRefOid,isCrossRepository,state,changedFiles,files"],
                    cwd=cwd or os.getcwd(), timeout=15)
    try:
        pr = json.loads(view.out) if view.ok else None
    except ValueError:
        pr = None
    sha = pr.get("headRefOid") if isinstance(pr, dict) else None
    if not sha or not SHA.fullmatch(str(sha)):
        return False, "couldn't read pull request #%d" % number, None
    if pr.get("isCrossRepository"):
        return False, fork_pr(number, pr, _fork_paths(str(sha), cwd or os.getcwd())), None
    _, why = decide_merge(number, sha, look_pr(number, sha, cwd or os.getcwd()))
    return why.startswith(READY), why, merge_command(number, sha)


def waiting(cwd=None):
    """The night shift's open pull requests and what each waits for, or None if GitHub
    couldn't be asked. Ones that touch the gate list exactly which safety files. A background
    run never asks: it would be GitHub with the human's login (Fable's review, F12)."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return None
    r = core.run(["gh", "pr", "list", "--state", "open", "--limit", "50", "--json",
                  "number,title,headRefName,url,isCrossRepository"], cwd=cwd or str(core.ROOT), timeout=20)
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
        if pr.get("isCrossRepository") is not False:
            # A fork can name its branch night/* too: its number only, never its title or branch.
            rows.append({"number": pr["number"], "fork": True, "ready": False,
                         "why": "#%d is from a fork: cos hook check %d" % (pr["number"], pr["number"])})
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
        if r.get("fork"):
            print("#%d\n    waits: %s" % (r["number"], r["why"]))
            continue
        print("#%d %s (%s)\n    %s\n    %s" % (r["number"], r["title"], r["branch"],
                                          r["why"] if r["ready"] else "waits: " + r["why"], r["url"]))


def main(args):
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
    approve, why = check_push(target)
    core.emit({"branch": target, "approve": approve, "why": why}, args.json,
              lambda d: print(("✓ clean to push: " if d["approve"] else "✗ don't push: ") + d["why"]))
    return 0 if approve else 1
