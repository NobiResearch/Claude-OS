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

## Each release

From a clean checkout of `main`, at `origin/main`:

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

Only on the owner's yes, each time: `gh release create`, which asks before it runs. The notes say
what you need (macOS 14+, Claude Code and a Claude plan, Apple Music for music), what first launch
adds and how to remove it, that Claude OS is under the PolyForm Noncommercial License 1.0.0
(binaries too), and that it isn't made or endorsed by Anthropic. They pass `bin/cos guard --text`.
