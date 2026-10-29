"""The docs list every command: CLAUDE.md's syscall table and README's syscall block must
name every user-facing `cos` command (issue #140).

`cli.COMMANDS` is the source of truth. Every command there is either a syscall (it belongs in
both docs) or, if it is a way in or plumbing, it is named in INTERNAL below — on purpose. So
adding a command makes you choose: document it, or say here why it is not a syscall. Delete a
command's doc line and the test fails; add one and forget the docs and it fails. Pure file
reads, standard library, no network.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))

from cos import cli

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# Not syscalls, so not in the syscall table or block. Each is a way in or a piece of plumbing,
# documented where it belongs instead: `cos` itself boots (boot), `ask` is a one-shot answer
# with no session, `app`/`serve` are the desktop, `statusline` is Claude Code's status line,
# and `install`/`uninstall`/`version` are lifecycle and plumbing (see CLAUDE.md's
# "Apps (skills)" section).
INTERNAL = {"ask", "boot", "statusline", "serve", "app", "install", "uninstall", "version"}


def _claude_syscalls(text):
    """First-column commands of CLAUDE.md's `## Syscalls` table, backticks stripped. Only the
    command column counts: the "what it does" column also has backticked examples."""
    found = set()
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Syscalls"
            continue
        if not in_section or not line.startswith("|"):
            continue
        first_col = line.split(" | ")[0]  # the rest of the row is the description
        for span in re.findall(r"`([^`]+)`", first_col):
            word = span.split()[0] if span.split() else ""
            if word:
                found.add(word)
    return found


def _readme_syscalls(text):
    """Commands of README's first code block under `### Syscalls`. Lines read `cos power`;
    several commands can share a line separated by `·`, the rest of the line is a description."""
    found = set()
    in_section = False
    in_code = False
    for line in text.splitlines():
        if line.startswith("### "):
            in_section = line.strip() == "### Syscalls"
            continue
        if not in_section:
            continue
        if line.strip().startswith("```"):
            if in_code:
                break
            in_code = True
            continue
        if not in_code:
            continue
        if not line.strip().startswith("cos "):  # a wrapped description is not a command line
            continue
        command_part = re.split(r"\s{2,}", line.strip())[0]  # stop at the description gap
        for segment in command_part.split("·"):
            segment = segment.strip()
            if segment.startswith("cos "):
                segment = segment[len("cos "):].strip()
            word = segment.split()[0] if segment.split() else ""
            if word:
                found.add(word)
    return found


class TestDocsListEveryCommand(unittest.TestCase):
    def _read(self, name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
            return handle.read()

    def test_internal_commands_are_real(self):
        # A typo in INTERNAL would quietly excuse a real command from the docs.
        self.assertEqual(set(), INTERNAL - cli.COMMANDS)

    def test_every_user_command_is_in_claude_md(self):
        documented = _claude_syscalls(self._read("CLAUDE.md"))
        missing = sorted((cli.COMMANDS - INTERNAL) - documented)
        self.assertEqual([], missing, "CLAUDE.md's syscall table is missing: %s" % missing)

    def test_a_wrapped_description_is_not_a_command(self):
        # A description that wraps onto its own line must not count as documenting a command.
        text = "### Syscalls\n\n```\ncos power   what keeps the Mac awake\npower users see more\n```\n"
        self.assertEqual({"power"}, _readme_syscalls(text))

    def test_every_user_command_is_in_readme(self):
        documented = _readme_syscalls(self._read("README.md"))
        missing = sorted((cli.COMMANDS - INTERNAL) - documented)
        self.assertEqual([], missing, "README's syscall block is missing: %s" % missing)
