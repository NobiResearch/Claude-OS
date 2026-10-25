# Can Claude OS work from any directory, as a Claude Code plugin?

- **Asked:** 2026-10-25, overnight lab (three scouts: plugin format, marketplaces, Claude OS itself)
- **Checked against:** Claude Code 2.1.310, the official plugin docs, and `claude plugin validate`
- **Status:** decided ([0009](../decisions/0009-claude-os-everywhere.md)): links in `~/.claude/skills`, no plugin

## Answer

Yes. Make the **repo root the plugin root**, and add the checkout as a **local-directory
marketplace**. A relative-path plugin in a local marketplace loads *in place*: no cached
copy, no version bumps, and each night's merge is live at the next session (or
`/reload-plugins`). The plugin's `bin/` goes on the Bash tool's PATH, so `cos` works
everywhere. Ship only the skills that are about the Mac; keep the self-building parts
(board, evolve, lab, agents) in the repo. Two things don't come along and need a design:
permission rules and the boot context.

## Evidence

**What a plugin can ship** (docs: [plugins reference](https://code.claude.com/docs/en/plugins-reference),
[components](https://code.claude.com/docs/en/plugins/components.md))
- `skills/`, `commands/`, `agents/`, `hooks/hooks.json` (every event, SessionStart included),
  `.mcp.json`, `output-styles/`, and `bin/`, which is added to the Bash tool's PATH. (verified in docs)
- **Not** permission rules, a main `statusLine`, or a CLAUDE.md. `claude plugin validate` on a mock
  plugin: "Unknown field 'permissions'… ignores it", "Unknown field 'statusLine'", "CLAUDE.md at
  the plugin root is not loaded as project context". A plugin's `settings.json` only honours
  `agent` and `subagentStatusLine`. (verified with the validator)
- Skills are namespaced `/<plugin>:<skill>`; a bare `/<skill>` works when nothing else claims
  the name. Descriptions trigger automatically like project skills. (docs; not tested live)
- Hooks can run scripts in the plugin via `"${CLAUDE_PLUGIN_ROOT}/…"` (quote it: paths can
  contain spaces). SessionStart can inject context (stdout or `additionalContext`), capped at
  10,000 characters. (docs; the cap matters: CLAUDE.md alone is ~6,000)
- `claude-os` is a **reserved plugin name** (the validator rejects it); use another, e.g. `cos`.
  (verified)

**How it gets installed and updated** (docs: [marketplaces](https://code.claude.com/docs/en/plugin-marketplaces),
[discover plugins](https://code.claude.com/docs/en/discover-plugins), plugins/loading.md)
- `.claude-plugin/marketplace.json` (`name`, `owner`, `plugins[]`); a plugin entry may use
  `"source": "./"`, making the repo itself the plugin. (verified in docs and installed examples)
- A marketplace added from **GitHub** installs a **copy** under `~/.claude/plugins/cache/…`
  without `.git`, keyed by version or commit, updated only on a version change, and
  third-party auto-update is off by default. A bad fit for a repo that changes nightly and
  whose daemons and app point at the checkout. (verified on this Mac's cache)
- A marketplace added from a **local directory** loads relative-path plugins in place, version
  ignored. (docs only; not yet tried on this Mac)
- Non-interactive: `claude plugin marketplace add "<checkout>" --scope user`, then
  `claude plugin install <name>@<marketplace> -s user`. (verified from `--help`)
- A repo's own `.claude/settings.json` can suggest a marketplace and plugin, but only inside
  that repo after the trust dialog, so it doesn't give "any directory". (docs)
- Inside the repo, project skills and plugin skills both load (namespaced), and a hook defined
  in both runs twice. (docs; not tested)

**What Claude OS would ship** (read from this repo)
- `music`, `tidy`, `update`, `startup`, `brief` only call syscalls and work anywhere once they
  call `cos` instead of `bin/cos` (`cos` resolves its repo from its own path, `core.ROOT`).
- `board`, `evolve`, `lab` and the agents read and write repo files (`docs/`, `tests/`, the
  roadmap) by relative path: repo-only.
- `music` and `brief` lean on the boot banner's memory; without the hook they need a
  `cos memory` step.
- `update` ("outdated packages, dependencies") and `tidy` ("cleaning up") would misfire in code
  projects: narrow them to the Mac, Homebrew and global tools.
- The full boot banner and status line show memory about the human and what's playing: not
  welcome in every session, client work included.
- The guard checks paths and secrets, not free text: a client detail saved with `cos remember`
  or `cos friction add` from another project could travel into evolve's commits. Skills
  shipped in a plugin need a rule: memory and friction text is about the human or the Mac,
  never the project at hand.
- Side finding, fixed in #13: daemons could run `cos ask` (another Claude without the
  daemon's budget or deny-list), `cos remember` (a feed item planting "facts" in every boot
  banner), `cos serve` and `cos app build`.

## Options

| Option | Effort | Fits a nightly-changing checkout? |
|---|---|---|
| A. Repo root as plugin, local-directory marketplace (user scope) | low | yes: loads in place |
| B. GitHub marketplace | medium | no: cached copies, version-gated updates |
| C. A folder under `~/.claude/skills/` pointing at the repo | low | unverified (symlinks) |

## Recommendation

Option A, named `cos`, in two steps:

1. **Skills everywhere.** Move `music`, `tidy`, `update`, `startup`, `brief` to a top-level
   `skills/` (so the repo doesn't list them twice), call `cos`, add a `cos memory` step,
   narrow the `update`/`tidy` descriptions, add the "memory and friction stay generic" rule.
   No hooks. `cos install` (which already asks) adds the marketplace and plugin at user scope.
2. **Permissions** (board): a PreToolUse hook in the plugin that allows read-only `cos`
   commands and returns `ask` for mutations, or user-level rules `cos install` writes with
   the human's yes. Not a blanket `Bash(cos *)` allow: several mutations rely on `ask` rules
   rather than `--yes`.

Later, opt-in: a lite SessionStart line outside the repo (warn-level signals only, never
memory or music), skipped when `CLAUDE_PROJECT_DIR` is the checkout so it doesn't run twice.

## Open questions

- In-place loading from a local-directory marketplace: try it on this Mac before building on it.
- Does bare `/music` resolve to the plugin skill when no project skill claims it?
- Does a `~/.claude/skills/<name>` symlink to the checkout load?

## Verified on this Mac (2026-10-25, Claude Code 2.1.310)

Option C works and is what Claude OS uses:
- A symlink `~/.claude/skills/<name>` to a skill folder loads in a session outside the repo
  (it appears in the session's skills and slash commands, and it's used).
- Edits to the linked folder show in the next session, with no reinstall: nothing is cached.
- A link to one of the repo's own skills appears once, not twice, in a session inside the repo.
