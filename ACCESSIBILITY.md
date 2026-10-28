# Accessibility

Ovenbird should work for everyone who uses a Mac, whatever they use to read, type or point.
It isn't all the way there yet. This page says where it stands, what's missing, and how to tell
us when something gets in your way.

## What it runs on

Ovenbird.app needs macOS 14 or later. `cos` in the terminal runs on the Python that macOS
ships (3.9 or later).

## What works today

- **Asking instead of finding.** Most of what Ovenbird does can be asked for in your own
  words, in the app's chat or in the terminal. `cos ask "…"` answers once in plain text, and
  `cos say "…"` reads text aloud.
- **The terminal** prints plain text, and every command also prints JSON with `--json`, for
  your own tools.
- **Shortcuts.** ⌃⌥Space brings Ovenbird forward from anywhere, and ⌘K opens the command
  palette, where you can type an app's name or a question.
- **Names for VoiceOver.** The menu bar item and the dock's app buttons have names VoiceOver
  can read, and the desktop's notices are marked for screen readers (`aria-live`).
- **Zoom.** Pinch on a trackpad to zoom the desktop.
- **Contrast.** Body text is about 16:1 against its background, and secondary text about 6:1.

## Known gaps

- **Keyboard and VoiceOver in the desktop.** The dock, window controls and tabs don't all work
  from the keyboard yet, and the desktop hasn't been tested with VoiceOver
  ([#127](https://github.com/NobiResearch/Ovenbird/issues/127)).
- **Motion.** Only some animations follow Reduce Motion
  ([#139](https://github.com/NobiResearch/Ovenbird/issues/139)).
- **Appearance.** The desktop is dark only
  ([#125](https://github.com/NobiResearch/Ovenbird/issues/125) adds a light theme). The
  faintest text (placeholders, hints, empty states) is about 2.7:1, below the 4.5:1 that WCAG
  asks for.
- **Text size.** The desktop's text has fixed sizes, so it doesn't follow macOS's text size
  setting.
- **Color in the terminal.** The boot banner always uses color, even when `NO_COLOR` is set.

## Tell us

If something in Ovenbird gets in your way, open an
[issue](https://github.com/NobiResearch/Ovenbird/issues/new?template=bug_report.md) and say
it's about accessibility: what you were trying to do and what happened. If you're comfortable
saying what you use (VoiceOver, Switch Control, a larger text size, …), that helps us
reproduce it. We treat barriers as bugs. As with any issue, describe what you saw in your own
words rather than pasting output from your Mac.

Fixes are welcome too: [CONTRIBUTING.md](CONTRIBUTING.md) says how.

Last reviewed: October 2026.
