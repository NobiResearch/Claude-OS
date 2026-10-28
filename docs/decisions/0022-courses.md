# 0022 — Courses: the mark, again

- **Status:** accepted
- **Date:** 2026-10-28
- **Decided by:** the owner, who chose it; the board adopted it unanimously, with conditions
- **Supersedes:** 0021's mark (its licensing of the names and marks stands)

## Context

The Nest (0021) went live in the morning. In the owner's own Dock, next to other brands, it
looked unfinished: a cream dome on dark olive, all mid-tones, with no single crisp shape. The
board had judged it at real size, but on mock-ups, not on a real build beside real icons, and
it merged before the owner had seen it in place.

The owner went back to Claude Design with a minimalist direction and chose **Courses**: the
oven-nest's dome built from four stacked, round-ended bars, like courses of bricks, the top one
in Crown, the doorway a gap in the lower two. Ovenbird builds its own home one course at a time,
every night.

## Decision

- **Ovenbird's mark is Courses**, black or white with the Crown top course wherever color is
  possible. Nobi Research's mark is the **gate**, one round-ended arch. Wordmarks stay Outfit 500,
  outlined. The files, rules and every coordinate are in
  [docs/brand/README.md](../brand/README.md); the files are MIT and the names and marks are
  reserved, as in 0021.
- **The app icon is the dark variant** (a `#0F0F0F` body), drawn by `app/icon.swift` from the
  note's numbers with the designer's hand-drawn 16 and 32 px. Following macOS's light and dark
  icon appearance needs an Icon Composer icon compiled by Xcode's `actool`, a new build
  dependency, so it's on the roadmap instead.
- **The menu bar shows the mark as a template image** from the 18 pt bars. Without Crown it can
  read as a list; the owner checks it in their own menu bar, and if it does, the menu bar gets its
  own variant.
- **"◆" stays as a text glyph** in the terminal, `cos status` and the desktop's chips and bullets.
  It marks Claude in text, where a mark can't be drawn; it isn't the logo. "≡" would read as a
  menu.
- **Names don't follow the design:** the desktop's files are `ui/mark.svg` and
  `ui/mark-mono.svg`, the class `.brand-mark`, the image `StatusItemController.mark`, the struct
  `Mark`. A future redesign changes files, not names.
- **A mark merges only after the owner has seen a real build** in their own Dock and menu bar. This
  one did.

## Consequences

- The desktop's colors move to the note's neutral tokens in their own pull request, after the
  owner has lived with the new icon. That change also moves the last hard-coded warm colors into
  tokens, so a palette is one block of CSS.
- The README header, favicons and the social preview change with the files. The owner uploads
  the new social preview and the Nobi Research avatar.
- 0021 stays as the record of the Nest and of why the names and marks are reserved.
