# Changelog

User-visible changes to Claude OS. Evolve runs add entries under **Unreleased**.

## Unreleased

## 0.1.0 — 2026-10-24

The founding release.

- **Kernel:** `CLAUDE.md` laws and syscall table; SessionStart boot banner; status line.
- **Syscalls:** `status`, `clean` (24 targets with safety levels), `update` (macOS,
  Homebrew, npm, mas, rustup), `music` (library + catalog), `feeds` (RSS/Atom/RDF with
  read tracking), `log`, `friction`, `remember`/`memory`, `notify`, `say`, `brief`,
  `daemon`, `evolve`, `guard`, `doctor`, `install`/`uninstall`, `config`.
- **Apps:** `/music`, `/tidy`, `/update`, `/brief`, `/board`, `/lab`, `/evolve`.
- **Colleagues:** board seats `architect`, `guardian`, `steward`, `skeptic`; lab `scout`.
- **Daemons:** `pulse` (free), `morning`, `evolve`, `board` (opt-in, budget-capped).
- **Privacy:** Guardian pre-commit hook and whole-tree test.
