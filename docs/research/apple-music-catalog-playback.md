# Can Claude OS play any Apple Music song, not just library tracks?

- **Asked:** 2026-10-24, during the founding build
- **Status:** open (tracked as friction; see the roadmap's Research section)

## Answer so far

Not reliably with AppleScript alone. Library tracks play instantly and deterministically.
Catalog songs can be *opened* in Music on the right page, but starting playback from a
script is hit-and-miss.

## Evidence

- AppleScript's Music dictionary addresses library objects only. A community Apple Music
  MCP server documents "No catalog access - only library content" and notes that
  `play track id …` requires the song to be in the library
  ([mcp-applemusic notes](https://skills.cat/skills/epheterson/mcp-applemusic)). (verified by reading)
- Tested on macOS 27.0.1 with this Mac (verified):
  - `open location "music://music.apple.com/<cc>/album/<slug>/<albumId>?i=<trackId>"`
    navigates Music to the album page with the song highlighted. It never auto-plays.
  - `play` right after that has done three different things: started the page's album at
    track 1 (twice, the first runs of the session), done nothing, or resumed the previous
    queue (most runs after library playback).
  - The browser window's `view` isn't scriptable for catalog pages (`-1731`, unknown object
    type), and `selection` is empty.
  - `music://music.apple.com/<cc>/song/<slug>/<trackId>` song-page URLs behaved the same.
- The iTunes Search API (`itunes.apple.com/search`, no key) reliably finds catalog songs and
  their `trackViewUrl` (verified).

## Options

| option | effort | reliability | caveats |
|---|---|---|---|
| Current: open page + play, verify, pause on mismatch | done | partial | the human sometimes has to press ▶ |
| UI scripting (click play on the page) | low | medium | needs Accessibility permission; fragile across UI languages and versions |
| MusicKit helper app (Swift) | high | high | needs an Apple Developer account and signing; adds a binary |
| A Shortcuts action that plays catalog items | low if it exists | unknown | needs research: which actions accept catalog items? |

## Recommendation

Keep library-first. For catalog picks, research the Shortcuts route first: it's free, it
needs no extra permissions, and it would make `cos music play` fully reliable.
