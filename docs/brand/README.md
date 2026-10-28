# Ovenbird & Nobi Research — brand assets (Courses)

Direction F "Courses", with the Crown top course, in the mono system. Everything here is original
vector work: no raster textures, no embedded fonts, no metadata. SVGs are plain `xmlns` documents
with no editor, author or path fields; PNGs carry no text chunks; the PDF has no Info dictionary
or XMP.

## What's in the folder

Ovenbird

| Item | Files |
|---|---|
| Symbol | `ovenbird-mark.svg` (Black bars, Crown top, for light grounds), `ovenbird-mark-dark.svg` (White bars, Crown top), `ovenbird-mark-mono.svg` (one color, `currentColor`) |
| Wordmark | `ovenbird-wordmark-light.svg` (Black), `ovenbird-wordmark-dark.svg` (White) — Outfit 500, outlined, −20/1000 em tracking |
| Lockup | `ovenbird-lockup-light.svg`, `ovenbird-lockup-dark.svg` |
| README header (4:1) | `ovenbird-readme-header-light.svg` (Paper card), `ovenbird-readme-header-dark.svg` (#0F0F0F card) |
| App icon, light | `ovenbird-appicon-1024.svg` (master), `ovenbird-appicon-background.svg`, `ovenbird-appicon-foreground.svg`; PNGs at 1024 (flat, background, foreground), 512, 256, 128; hand-drawn `ovenbird-appicon-32.svg/.png`, `ovenbird-appicon-16.svg/.png` |
| App icon, dark | the same set with `-dark-` in the name (`ovenbird-appicon-dark-1024.svg` …), for the dark appearance |
| Menu bar template | `ovenbird-menubar-template.svg` (18 pt), `ovenbird-menubar-template.pdf` (18 pt, vector); hand-drawn `…-16.svg`, `…-32.svg`, `…-36.svg`; PNGs at 16, 18, 32, 36 px, pure black on transparent |
| Social preview | `ovenbird-social-preview-1280x640.png` and its `.svg` |
| Favicon | `ovenbird-favicon.svg`, hand-drawn `ovenbird-favicon-16.svg/.png`, `ovenbird-favicon-32.svg/.png`, `ovenbird-apple-touch-icon-180.svg/.png` |

Nobi Research

| Item | Files |
|---|---|
| Symbol | `nobi-mark.svg` (Black), `nobi-mark-dark.svg` (White), `nobi-mark-mono.svg` (`currentColor`) |
| GitHub avatar | `nobi-avatar-1024.svg`, `nobi-avatar-1024.png`, `nobi-avatar-256.png` (square; GitHub rounds it) |
| Wordmark | `nobi-wordmark-light.svg`, `nobi-wordmark-dark.svg` — Outfit 500, outlined, −12/1000 em |
| Lockup | `nobi-lockup-light.svg`, `nobi-lockup-dark.svg` |
| Favicon | `nobi-favicon.svg`, hand-drawn `nobi-favicon-16.svg/.png`, `nobi-favicon-32.svg/.png`, `nobi-apple-touch-icon-180.svg/.png` |
| Sharing image | `nobi-social-1200x630.png` and its `.svg` |

## Colors

A neutral system with one accent. The marks are black or white; Crown appears only on the top
course of the Ovenbird mark and as the app's accent.

| Name | Hex | Use |
|---|---|---|
| Black | `#111111` | mark and text on light grounds (17.6:1 on Paper) |
| White | `#FFFFFF` | mark on dark grounds |
| Paper | `#F7F7F5` | light background: README, website |
| Mist | `#ECECEA` | light surface |
| Line (light) | `#E0E0DD` | hairlines on light |
| Muted (light) | `#6B6B6B` | secondary text on light (5.0:1) |
| Crown | `#E0912F` | the top course; the app accent. 7.5:1 on #0F0F0F |
| Ember | `#9A5214` | orange *text and links on light grounds* (5.5:1 on Paper) |
| Icon light body | `#FAFAFA` | the light app icon's body |

Rules: Crown is never text and never the only signal on light grounds; use Ember for orange text,
and Black on Crown fills (7.4:1). The mark works all-black and all-white; the Crown course is the
preferred version wherever color is available.

### App tokens (dark only)

| Token | Hex | Notes |
|---|---|---|
| background | `#0F0F0F` | |
| surface | `#171717` | |
| surface-2 | `#1F1F1F` | nested panels, table stripes |
| raise | `#262626` | hover, raised rows, popovers |
| line | `#2E2E2E` | hairlines and borders |
| text | `#F5F5F5` | 17.6:1 |
| muted | `#9A9A9A` | secondary text, 6.8:1 |
| faint | `#5C5C5C` | placeholders and disabled, 2.9:1 (never for essential text) |
| accent | `#E0912F` | Crown |
| accent-2 | `#B86A1E` | deep Crown: pressed states, gradient end (4.7:1). For a lighter hover tone use `#F0AE5A` |
| accent-soft | `#302414` | Crown at 16 % over background: tinted chips and selected rows |

### Status colors (clear of Crown)

| Token | Hex | On #0F0F0F | Black on fill | Soft tint |
|---|---|---|---|---|
| ok | `#72B46E` Leaf | 7.5:1 | 7.1:1 | `#1F291E` |
| warn | `#F4DA6E` Straw | 13.4:1 | 12.7:1 | `#342F1E` |
| bad | `#E5737A` Rose | 6.3:1 | 5.9:1 | `#311F20` |
| info | `#6FA8DC` Sky | 7.4:1 | 7.0:1 | `#1E2730` |

## Geometry

Everything is one primitive: a bar with fully rounded ends (a line with round caps, or a rect
with `rx` = half its height). There are no curves other than those caps and the two corners of
the Nobi gate.

### Ovenbird mark, 64-unit box

Four courses, stroke 8, round caps, 4 between courses (pitch 12). Centre lines, top to bottom;
each path is a stroked line, so the visible bar extends 4 units beyond each end:

| Course | Centre line | Visible extent | Color |
|---|---|---|---|
| 1 (top) | `M24 14 H40` | x 20–44, y 10–18 | Crown |
| 2 | `M15 26 H49` | x 11–53, y 22–30 | bars |
| 3 | `M10 38 H37` and `M53 38 H54` | x 6–41 and 49–58, y 34–42 | bars |
| 4 (bottom) | `M8 50 H37` and `M53 50 H56` | x 4–41 and 49–60, y 46–54 | bars |

The doorway is the 8-unit gap (x 41–49) in courses 3 and 4; the short right-hand pieces are the
door post. The mark's box is x 4–60, y 10–54, so it centres on (32, 32).

### App icon, 1024 grid

Body: rounded square x 100, y 100, w 824, h 824; the SVG uses a corner radius of 185 as a stand-in
for Apple's continuous curve. In Icon Composer, let the system supply the body and import only the
layers: `…-background.svg` (a flat fill, `#FAFAFA` light / `#0F0F0F` dark) and `…-foreground.svg`
(the four courses). Stroke 88, gap 44 (pitch 132), round caps:

| Course | Centre line | Color |
|---|---|---|
| 1 | `M424 314 H600` | Crown |
| 2 | `M325 446 H699` | Black (light) / White (dark) |
| 3 | `M270 578 H567` and `M743 578 H754` | " |
| 4 | `M248 710 H567` and `M743 710 H776` | " |

Visible extent x 204–820, y 270–754. The doorway gap is x 611–699. No gradient, no glow.

SwiftUI, 1024 grid:

```swift
func course(_ x1: CGFloat, _ x2: CGFloat, _ y: CGFloat) -> Path {
    var p = Path()
    p.move(to: CGPoint(x: x1, y: y))
    p.addLine(to: CGPoint(x: x2, y: y))
    return p
}
let style = StrokeStyle(lineWidth: 88, lineCap: .round)
// course(424, 600, 314)  → Crown
// course(325, 699, 446), course(270, 567, 578), course(743, 754, 578),
// course(248, 567, 710), course(743, 776, 710)  → bars color
```

Hand-drawn 32 and 16 px icons (rects, `rx` = half height; body x 3 y 3 w 26 h 26 r 6 at 32, x 1 y 1
w 14 h 14 r 3 at 16):

| Size | Courses (x, y, w, h) top to bottom |
|---|---|
| 32 | (13,8,6,3) Crown · (10,13,12,3) · (8,18,10,3) + (22,18,3,3) · (7,23,11,3) + (22,23,4,3) |
| 16 | (6,3,4,2) Crown · (4,6,8,2) · (3,9,6,2) + (11,9,2,2) · (3,12,6,2) + (11,12,2,2) |

### Menu bar template

Black only (macOS tints a template, so the Crown course cannot carry over). Whole-pixel rects,
`rx` = half height:

| Size | Courses (x, y, w, h) top to bottom |
|---|---|
| 18 pt | (6,2,6,2) · (3,6,12,2) · (2,10,8,2) + (13,10,3,2) · (1,14,9,2) + (13,14,4,2) |
| 16 px | (5,2,6,2) · (3,5,10,2) · (2,8,7,2) + (12,8,2,2) · (1,11,8,2) + (12,11,3,2) |
| 32 / 36 | exactly 2× the 16 / 18 numbers |

Set the asset to *Render As: Template Image* (`isTemplate = true`). The favicons use the 16 px
grid shifted down 1 px with the Crown top course on a `#0F0F0F` square.

### Nobi Research gate, 64-unit box

One stroked path, stroke 8, round caps, corner radius 10 on the centre line:
`M12 52 V22 Q12 12 22 12 H42 Q52 12 52 22 V52`. Visible extent x 8–56, y 8–56. On the avatar it is
placed at `translate(192 192) scale(10)` on a `#111111` 1024 square, white. The 16 px favicon uses
`M4 13 V6 Q4 4 6 4 H10 Q12 4 12 6 V13` at stroke 2; 32 is exactly 2×.

### Lockups

The mark stands 80 units tall beside 100-unit type (Outfit cap height 67.6) with its bottom edge on
the baseline and a 24-unit gap; the README headers are the lockup at 1.6× centred on a 1200 × 300
card; the social images are the dark lockup with the tagline in Outfit 400 at 34 px.

## Type

Wordmarks are **Outfit** at weight 500 (taglines at 400), converted to outlines. No font files are
shipped and nothing is loaded remotely.

Outfit — Copyright 2021 The Outfit Project Authors (https://github.com/Outfitio/Outfit-Fonts),
designed by Rodrigo Fuenzalida. Licensed under the SIL Open Font License, Version 1.1
(https://openfontlicense.org); a copy is in `OUTFIT-LICENSE-OFL.txt`. The app interface keeps Apple's
system font; SF Pro is not used in any logo file.

## Using the files

- **App icon (macOS 26 Icon Composer):** background and foreground layers for light; the `-dark-` pair for the dark appearance. The flat PNGs are the fallback for older systems and marketing. The 16 and 32 px PNGs are for places where the system does not downscale the master.
- **Menu bar:** `ovenbird-menubar-template.pdf` (or the 18/36 PNGs as 1x/2x) with *Render As: Template Image*.
- **README:** `<picture>` with `ovenbird-readme-header-dark.svg` for `prefers-color-scheme: dark` and the light one as the fallback `<img>`; both are 1200 × 300.
- **GitHub social preview:** `ovenbird-social-preview-1280x640.png`; the lockup and tagline sit inside the central 1000 × 300 safe area.
- **Favicons:** `<link rel="icon" href="ovenbird-favicon.svg" type="image/svg+xml">`, the 32 and 16 PNGs as fallbacks, `<link rel="apple-touch-icon" href="ovenbird-apple-touch-icon-180.png">`. Same with the `nobi-` files on nobiresearch.com.
- **Org avatar:** `nobi-avatar-1024.png`.

## Using the names and marks

The files are MIT, like the rest of the repository. The names Ovenbird and Nobi Research and
these marks aren't: they tell people where a copy came from. Use them to talk about Ovenbird (an
article, a talk, a "works with Ovenbird" note), but a fork or another product needs a name and
mark of its own (decisions 0021 and 0022).
