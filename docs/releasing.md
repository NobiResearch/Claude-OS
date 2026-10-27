# Releasing Claude OS.app

How the downloadable app is built (decision 0015). Only the repository's owner cuts a release,
on their own Mac; nothing here runs in CI, and publishing is a separate step on their yes.

## Once

1. **A Developer ID certificate** ("Developer ID Application") in your login Keychain.
2. **The release App ID** (`app.claude-os.desktop`, MusicKit ticked under App Services) and a
   **Developer ID provisioning profile** for it, named neutrally. Keep the profile outside the
   repository, for example in `~/.claude-os/`. A brand-new App ID can take a few minutes before
   MusicKit accepts it (see `docs/lessons.md`).
3. **Notarization credentials in the Keychain**: create an app-specific password for your Apple
   Account (account.apple.com → Sign-In and Security → App-Specific Passwords), then run, in your
   own Terminal:

   ```sh
   xcrun notarytool store-credentials claude-os --apple-id <your Apple Account> --team-id <your team id>
   ```

   It asks for the password and keeps it in the Keychain under the name `claude-os`. The password
   is never written to a file, an environment variable or the repository.

## Before the first public release

The full check from decision 0015, step 1, on the notarized zip: download it in a **second
macOS user account** (so it's quarantined and nothing of yours is there), and go through the
first launch from nothing. The command line tools, Claude Code and the download, then Calendar,
Location, notifications, Music automation and the Apple Music player all prompt and work, and
Remove Claude OS… leaves nothing behind but the app.

Check one thing no one has tested yet: whether the code the downloaded app clones comes out
quarantined (`xattr -l` on `bin/cos`), and whether `cos` still runs from Terminal and from
Claude Code there ([research](research/growing-the-project.md)).

## Each release

1. **The version.** Raise `__version__` in `lib/cos/__init__.py` in a pull request of its own,
   and fold `changes/` into `CHANGELOG.md` under that version. The app's version comes from
   there, and downloaded apps compare it with the newest release's tag, so tag it `v<version>`
   (`v0.8.0`).
2. **The oldest app the code works with.** If the server now needs something only this app
   does, raise `APP_NEEDED` in `lib/cos/core.py` to this version: older downloaded apps then say
   "download Claude OS.app" instead of breaking.
3. **Build** from a clean checkout of `main`, at `origin/main`:

```sh
COS_RELEASE_PROFILE=~/.claude-os/ClaudeOS-Release.provisionprofile \
COS_NOTARY_PROFILE=claude-os \
app/build.sh --release
```

It refuses to run with uncommitted changes, off `origin/main`, or in a background job, CI or
the evolve sandbox. It then:

- builds the app with nothing machine-specific inside (no paths, a stripped binary), and scans
  the whole bundle for anything private before signing;
- checks the profile: Developer ID (any Mac), the release App ID, neutral names;
- signs with Developer ID, the hardened runtime, a secure timestamp and the allowlisted
  entitlements, with no fallback;
- notarizes, staples and zips it to `build/Claude-OS-<version>.zip`.

`--no-notarize` stops before notarizing, for a local check. That zip isn't for publishing.

## Publishing

Only on the owner's yes, each time: `gh release create v<version> build/Claude-OS-<version>.zip
--title "Claude OS <version>" --notes-file <notes>`, which asks before it runs. The notes pass
`bin/cos guard --text` first.

### The notes

Plain words, for someone who isn't a developer. Start from this and add what's new:

```markdown
**Claude OS <version>**: an operating layer for your Mac that Claude lives in.

**What you need:** macOS 14 or later, [Claude Code](https://claude.com/claude-code) with a Claude
plan, and Apple Music for the music player.

**Install:** unzip, move Claude OS.app to your Applications folder, and open it. The first launch
shows a checklist: Apple's command line tools (Apple installs them), Claude Code (a link to
Anthropic's page), and Claude OS itself, downloaded from this repository into
~/Library/Application Support/Claude OS. Nothing is installed until you click. Two extras, the
skills in Claude Code and a vitals check every 2 hours, start off. Claude OS never asks for Full
Disk Access, Accessibility or Screen Recording.

**Updates:** when a newer Claude OS.app is out, Updates says so. Download it, replace the old one
and open it: Claude OS comes along.

**Remove:** Claude OS menu › Remove Claude OS… turns off its background jobs, removes its links
and moves its code to the Trash; your journal and memory go only if you say so. Then drag the app
to the Trash.

**What's new:** <from CHANGELOG.md>

Claude OS is open source under the MIT License, the app included. It isn't made or endorsed by
Anthropic; Claude is Anthropic's trademark.
```
