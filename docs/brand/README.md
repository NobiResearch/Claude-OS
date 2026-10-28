# Ovenbird & Nobi Research — brand assets

Everything here is original vector work. There are no raster textures, no embedded fonts and no
metadata in any file. All SVGs are plain `xmlns` documents with no editor, author or path fields;
PNGs carry no text chunks; the PDF has no Info dictionary or XMP.

## What's in the folder

Ovenbird

| Item | Files |
|---|---|
| Symbol | `ovenbird-mark.svg` (Olive + Crown, for light grounds), `ovenbird-mark-dark.svg` (Moss + Crown, for dark grounds), `ovenbird-mark-mono.svg` (one color, `currentColor`, doorway knocked out) |
| Wordmark | `ovenbird-wordmark-light.svg` (Ink), `ovenbird-wordmark-dark.svg` (Bone) — Outfit 500, outlined |
| Lockup | `ovenbird-lockup-light.svg`, `ovenbird-lockup-dark.svg` |
| README header (4:1) | `ovenbird-readme-header-light.svg` (Cream card), `ovenbird-readme-header-dark.svg` (Night card) |
| App icon | `ovenbird-appicon-1024.svg` (master, both layers), `ovenbird-appicon-background.svg`, `ovenbird-appicon-foreground.svg`, PNGs at 1024 (flat, background, foreground), 512, 256, 128; hand-drawn `ovenbird-appicon-32.svg/.png` and `ovenbird-appicon-16.svg/.png` |
| Menu bar template | `ovenbird-menubar-template.svg` (18 pt), `ovenbird-menubar-template.pdf` (18 pt, vector), hand-drawn `…-16.svg`, `…-32.svg`, `…-36.svg`; PNGs at 16, 18, 32 and 36 px, pure black on transparent |
| Social preview | `ovenbird-social-preview-1280x640.png` (36 KB) and its `.svg` |
| Favicon | `ovenbird-favicon.svg`, hand-drawn `ovenbird-favicon-16.svg/.png`, `ovenbird-favicon-32.svg/.png`, `ovenbird-apple-touch-icon-180.svg/.png` |

Nobi Research

| Item | Files |
|---|---|
| Symbol | `nobi-mark.svg` (Olive), `nobi-mark-dark.svg` (Moss), `nobi-mark-mono.svg` (`currentColor`) |
| GitHub avatar | `nobi-avatar-1024.svg`, `nobi-avatar-1024.png`, `nobi-avatar-256.png` (square; GitHub rounds it) |
| Wordmark | `nobi-wordmark-light.svg`, `nobi-wordmark-dark.svg` — Outfit 500, outlined |
| Lockup | `nobi-lockup-light.svg`, `nobi-lockup-dark.svg` |
| Favicon | `nobi-favicon.svg`, hand-drawn `nobi-favicon-16.svg/.png`, `nobi-favicon-32.svg/.png`, `nobi-apple-touch-icon-180.svg/.png` |
| Sharing image | `nobi-social-1200x630.png` (40 KB) and its `.svg` |

## Colors

Core palette, taken from the bird: olive-brown back, cream breast, orange crown.

| Name | Hex | Use |
|---|---|---|
| Night | `#15120E` | dark background; the social preview and the dark README header |
| Loam | `#221E18` | dark surface |
| Cream | `#F6EFE2` | light background (README, website) |
| Linen | `#ECE3D2` | light surface |
| Olive | `#5E5A3A` | main color on light grounds (6.1:1 on Cream) |
| Moss | `#8F8A5A` | main color on dark grounds (5.3:1 on Night, 5.4:1 on GitHub's `#0D1117`; Olive is only 2.7:1 there) |
| Crown | `#E0912F` | accent: the doorway, fills, focus. 7.3:1 on Night |
| Ember | `#9A5214` | orange *text and links on light grounds* (5.1:1 on Cream) |
| Ink | `#1C1813` | text on light grounds and on Crown fills (6.9:1 on Crown) |
| Bone | `#F3ECE0` | text on dark grounds |
| Icon cream | `#F3EADA` | the dome on the app icon, the avatar and the favicons |

Rules: Crown is never text and never the only signal on light grounds (it is 2.2:1 on Cream);
use Ember for orange text there and Ink on Crown fills. The doorway diamond carries its meaning
by shape, so the one-color mark and the template image stay readable without the orange.

### Status colors (clear of Crown)

| Token | Hex | On Night | Ink on fill | Soft tint (16 % over Night) |
|---|---|---|---|---|
| ok | `#72B46E` Leaf | 7.5:1 | 7.1:1 | `#242C1D` |
| warn | `#F4DA6E` Straw | 13.4:1 | 12.7:1 | `#39321D` |
| bad | `#E5737A` Rose | 6.3:1 | 5.9:1 | `#36221F` |
| info | `#6FA8DC` Sky | 7.4:1 | 7.0:1 | `#232A2F` |

Warn is a lighter, cooler yellow than the old `#E7B765`, so it sits well apart from Crown's
amber (hue 48° vs 33°, and much lighter). Bad is a rose rather than a red-orange for the same
reason. Text on any of these fills is Ink.

### App tokens (dark only)

| Token | Hex | Notes |
|---|---|---|
| background | `#15120E` | Night |
| surface | `#221E18` | Loam |
| surface-2 | `#2B2620` | nested panels, table stripes |
| raise | `#352F27` | hover, raised rows, popovers |
| line | `#3B342C` | hairlines and borders on surface |
| text | `#F3ECE0` | Bone, 15.9:1 |
| muted | `#A89E8E` | secondary text, 7.1:1 |
| faint | `#6F665A` | placeholders and disabled, 3.3:1 (never for essential text) |
| accent | `#E0912F` | Crown |
| accent-2 | `#B86A1E` | deep Crown: pressed states, gradient end (4.6:1 on Night). If accent-2 is a lighter hover tone in your code, use `#F0AE5A` instead |
| accent-soft | `#352613` | Crown at 16 % over Night: tinted chips and selected rows |

Light tokens for the README and the website: background Cream `#F6EFE2`, surface Linen `#ECE3D2`,
line `#DED6C7`, text Ink `#1C1813`, muted `#6B6355` (5.2:1), accent for fills Crown with Ink on it,
accent for text Ember `#9A5214`.

## Geometry

All marks share one curve. The dome is a closed cubic path whose sides start vertical at the
base and whose top is a broad, rounded crown; it is taller than a half circle. For a dome of
width W and height H whose base-left corner is at (x0, y0):

```
M x0, y0
C x0, y0 - 0.62·H   x0 + 0.15·W, y0 - H   x0 + 0.5·W, y0 - H
C x0 + 0.85·W, y0 - H   x0 + W, y0 - 0.62·H   x0 + W, y0
Z
```

The doorway is a diamond, 2 wide : 3 tall, whose bottom vertex sits on the base line so the cut
opens to the ground. It sits to the right of center.

### App icon, 1024 grid

| Element | Numbers |
|---|---|
| Body | rounded square x 100, y 100, w 824, h 824; the SVG uses a corner radius of 185 as a stand-in for Apple's continuous curve — in the app, let Icon Composer / the system supply the real shape and only draw the layers below |
| Background layer | vertical linear gradient `#4F4B34` (y 100) → `#27241A` (y 924), clipped to the body |
| Glow (background layer, optional) | radial, center (620, 700), radius 260, Crown at 22 % → 0 %. The only glow in the icon, and it comes from the doorway |
| Ground line (foreground) | from (196, 760) to (828, 760), stroke 24, round caps, Moss `#8F8A5A` |
| Dome (foreground) | `M232 760 C232 462 316 280 512 280 C708 280 792 462 792 760 Z`, fill `#F3EADA` (width 560, height 480, base at y 760) |
| Doorway (foreground) | diamond top (620, 460), right (720, 610), bottom (620, 760), left (520, 610), fill Crown. 200 wide, 300 tall |

The doorway is drawn on top of the solid dome (same result as a cut-out, one path fewer).
The 32 px and 16 px icons are drawn by hand on whole pixels, not scaled down:

| Size | Body | Ground | Dome | Doorway |
|---|---|---|---|---|
| 32 | x 3 y 3 w 26 h 26 r 6 | rect x 6 y 23 w 20 h 1 | `M7 24 C7 14.7 9.7 9 16 9 C22.3 9 25 14.7 25 24 Z` | (19,16) (22,20) (19,24) (16,20) |
| 16 | x 1 y 1 w 14 h 14 r 3 | rect x 2 y 12 w 12 h 1 | `M3 13 C3 8 4.5 5 8 5 C11.5 5 13 8 13 13 Z` | (9,7) (11,10) (9,13) (7,10) |

SwiftUI, 1024 grid (scale the rect to the view):

```swift
var dome = Path()
dome.move(to: CGPoint(x: 232, y: 760))
dome.addCurve(to: CGPoint(x: 512, y: 280), control1: CGPoint(x: 232, y: 462), control2: CGPoint(x: 316, y: 280))
dome.addCurve(to: CGPoint(x: 792, y: 760), control1: CGPoint(x: 708, y: 280), control2: CGPoint(x: 792, y: 462))
dome.closeSubpath()

var door = Path()
door.move(to: CGPoint(x: 620, y: 460))
door.addLine(to: CGPoint(x: 720, y: 610))
door.addLine(to: CGPoint(x: 620, y: 760))
door.addLine(to: CGPoint(x: 520, y: 610))
door.closeSubpath()

var ground = Path()
ground.move(to: CGPoint(x: 196, y: 760))
ground.addLine(to: CGPoint(x: 828, y: 760))
// stroke ground with lineWidth 24, round caps, Moss; fill dome #F3EADA; fill door Crown
```

### Menu bar template, 18 pt grid

Filled dome with the doorway cut out (`fill-rule: evenodd`), pure black. The 18 pt master is what
the PDF holds; 16, 32 and 36 are drawn by hand on whole pixels. Set the image as a template
(`isTemplate = true`) so macOS tints it.

| Size | Dome | Doorway (top, right, bottom, left) |
|---|---|---|
| 18 pt | `M1 16 C1 7.3 3.4 2 9 2 C14.6 2 17 7.3 17 16 Z` | (12,8) (15,12) (12,16) (9,12) |
| 16 px | `M1 14 C1 6.6 3.1 2 8 2 C12.9 2 15 6.6 15 14 Z` | (10,6) (13,9) (10,14) (7,9) — 6 px wide |
| 32 px (16 @2x) | `M2 28 C2 13.2 6.2 4 16 4 C25.8 4 30 13.2 30 28 Z` | (20,12) (26,18) (20,28) (14,18) |
| 36 px (18 @2x) | `M2 32 C2 14.6 6.8 4 18 4 C29.2 4 34 14.6 34 32 Z` | (24,16) (30,24) (24,32) (18,24) |

### Symbol, 64-unit box (the general-purpose mark)

Dome `M4 56 C4 26 12 8 32 8 C52 8 60 26 60 56 Z`; doorway (44,26) (54,41) (44,56) (34,41).
In the lockups the dome stands 80 units tall on the wordmark's baseline next to 100-unit type
(cap height 67.6), with a 28-unit gap.

### Nobi Research arch, 64-unit box

Same dome path as the symbol. The opening is the Nest's doorway shape with legs: a pentagon
`M19 56 V41 L32 22 L45 41 V56 Z`, open at the base (`fill-rule: evenodd`). The point of the arch
has the same 2:3 slope as the diamond, so the n reads as the sibling of the Nest rather than a
magnet. On the avatar the mark is placed at `translate(176 176) scale(10.5)` on an Olive
1024 square, Icon cream fill; GitHub rounds the corners itself.

Hand-drawn favicons: 16 px uses dome `M3 13 C3 7.4 4.5 4 8 4 C11.5 4 13 7.4 13 13 Z` with the
opening `M6 13 V10 L8 7 L10 10 V13 Z` (Nobi) or the diamond (9,7) (11,10) (9,13) (7,10)
(Ovenbird); 32 px is exactly twice that.

## Type

Wordmarks are set in **Outfit** at weight 500 (the taglines at 400), then converted to outlines.
No font files are shipped and nothing is loaded remotely. "Ovenbird" has −8/1000 em tracking,
"Nobi Research" −6/1000 em.

Outfit — Copyright 2021 The Outfit Project Authors (https://github.com/Outfitio/Outfit-Fonts),
designed by Rodrigo Fuenzalida. Licensed under the SIL Open Font License, Version 1.1
(https://openfontlicense.org). The OFL allows the outlines to be used and redistributed in this
MIT-licensed repository; please keep this credit in the repo's notes.

The app interface keeps Apple's system font; SF Pro is not used in any logo file.

## Using the files

- **App icon (macOS 26 Icon Composer):** import `ovenbird-appicon-background.svg` as the back layer and `ovenbird-appicon-foreground.svg` as the front layer; the flat PNG is the fallback for older systems and for marketing. The 16 and 32 px PNGs are for places where the system does not downscale the master for you.
- **Menu bar:** add `ovenbird-menubar-template.pdf` (or the 18/36 PNGs as 1x/2x) to the asset catalog with *Render As: Template Image*.
- **README:** `<picture>` with `ovenbird-readme-header-dark.svg` for `prefers-color-scheme: dark` and the light one as the fallback `<img>`; both are 1200 × 300.
- **GitHub social preview:** upload `ovenbird-social-preview-1280x640.png`. The lockup and tagline sit inside the central 1000 × 300 safe area.
- **Favicons:** `<link rel="icon" href="ovenbird-favicon.svg" type="image/svg+xml">`, with the 32 and 16 PNGs as fallbacks and `<link rel="apple-touch-icon" href="ovenbird-apple-touch-icon-180.png">`. Same pattern with the `nobi-` files on nobiresearch.com.
- **Org avatar:** upload `nobi-avatar-1024.png`.

## Using the names and marks

The files are MIT, like the rest of the repository. The names Ovenbird and Nobi Research and
these marks aren't: they tell people where a copy came from. Use them to talk about Ovenbird (an
article, a talk, a "works with Ovenbird" note), but a fork or another product needs a name and
mark of its own (decision 0021).
