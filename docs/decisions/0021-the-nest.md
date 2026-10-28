# 0021 — The Nest: Ovenbird's mark, and Nobi Research's

- **Status:** accepted
- **Date:** 2026-10-28
- **Decided by:** the board (all four seats), confirmed by the owner
- **Follows:** 0019 ("a mark of its own is a separate decision")

## Context

After the rename (0019), Ovenbird still wore the Claude OS mark: an off-white diamond on a
coral gradient, and "◆" as text in the menu bar. The coral sat right next to Claude's own color,
and a diamond says nothing about a bird or a home. The owner briefed Claude Design, which came
back with three directions for Ovenbird (Nest, Bird, Ring), three for Nobi Research, the GitHub
organization that makes it (Canopy, Arch, Clutch), a palette taken from the bird and three open
typefaces.

The board judged them at real size, in a Dock and a menu bar, not as large lockups. At 1x the
Ring's menu bar icon reads as macOS's reload arrow (the Guardian vetoed it), the Bird's
streaked breast reads as a toothy grin, Clutch reads as a smiley and Canopy blurs into the
Nest's own dome.

## Decision

- **Ovenbird's mark is the Nest:** the ovenbird's domed nest, taller than a half circle, on a
  ground line, with the diamond as its doorway, lit in Crown. It tells the story at a glance
  (a home Claude builds for itself and keeps working on), and the diamond lives on: "◆" stays
  the text glyph in the terminal, in `cos status` and in the desktop.
- **Nobi Research's mark is the Arch:** a lowercase n drawn from the Nest's dome, its opening the
  doorway's shape, so the two read as siblings.
- **Outfit** (SIL OFL 1.1), weight 500, for both wordmarks, outlined; no font files in the
  repository, nothing loaded remotely. A soft serif on cream with an orange accent came too
  close to claude.ai's own look.
- **The palette comes from the bird:** Olive, Moss, Cream, Night and Crown (`#E0912F`), with
  Ember for orange text on light grounds and new status colors that read clearly apart from
  Crown. The full set, the rules and every shape's numbers are in
  [docs/brand/README.md](../brand/README.md).
- **Where it shows now:** the app icon (`app/icon.swift` draws it from those numbers, with the
  designer's hand-drawn 16 and 32 px), the menu bar (a template image, so macOS tints it, with
  "Ovenbird" for VoiceOver instead of "black diamond"), the README header and the desktop's
  favicon.

## Consequences

- The desktop's own accent stays coral until a separate change moves it to Crown and the new
  status colors, after the owner has seen the icon in their Dock and menu bar. That change also
  replaces the hard-coded coral in `ui/style.css` with tokens and the terminal's coral (ANSI 173).
- The GitHub social preview and the organization's avatar are repository settings: the owner
  uploads them from `docs/brand/`.
- The mark is the designer's original work, under the repository's MIT license; Outfit's credit
  and license are in `docs/brand/`.
