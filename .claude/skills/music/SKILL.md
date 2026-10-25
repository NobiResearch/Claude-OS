---
name: music
description: Play, find and control the human's own Apple Music on this Mac. Use for requests to play or find songs, artists, albums, playlists, moods ("find me a chill song", "play something to focus"), what's playing, skipping, volume, or liking a track. Not for choosing, adding or editing music or audio files in a video, app or other project.
argument-hint: "[what you want to hear]"
---

> Works from any folder on this Mac ([0009](../../../docs/decisions/0009-claude-os-everywhere.md)). Run syscalls as `cos …`; in the Claude OS folder, `bin/cos …` is the same. Whatever you `cos remember` or `cos friction add` is about the human or this Mac, never the project or client you're working in. Outside Claude OS there's no boot banner: read `cos memory` before choosing by taste.

# Music

You are the DJ. The syscall does mechanics; you bring taste.

## Steps

1. **Know the listener.** Check the boot banner's memory for music preferences. If you need
   more, `cos music history` shows what they've played lately.
2. **Turn the request into a concrete pick.**
   - A specific song/artist/album: use it as the query.
   - A mood or activity ("chill", "focus", "rainy Sunday"): pick a *specific* song you know
     fits, biased toward their taste, and start a **radio** from it (step 3), so the music
     keeps going. Don't reach for the same few famous picks: check `cos music history`
     and choose something they haven't heard in the last few days.
   - "Something from my library": `cos music find <genre or word>`, or
     `cos music playlists`, then `cos music playlist "<name>" --shuffle`. It plays in
     Claude OS's own player when that's on, so next, shuffle and like work there too.
3. **Play it.**
   - A mood or activity: `cos music radio "<song> <artist>"` plays that song, then
     similar music from its Apple Music station, in Claude OS's own player. With no
     argument it starts from the song playing now. If it says the song plays alone (no
     station), say so; if it needs "Apple Music in Claude OS", use `play` instead.
   - A named song, album or artist: `cos music play "<song> <artist>"`, one song as
     asked. It tries the library first; then, if "Apple Music in Claude OS" is on, it plays
     the catalog song in Claude OS's own player; otherwise it opens the song page in Music
     (`cos music setup` shows the state). `--source catalog` skips the library;
     `--pick N` chooses another result from `cos music catalog "<query>"`.
4. **Report** in one line what's playing and why you picked it ("Paper Lanterns, then
   similar music"). If playback only *opened* the song (catalog playback isn't fully
   scriptable), say it's open in Music and they need to press play. Don't retry in a loop.
5. **Learn.** "I love this" → `cos music like` plus `cos remember "likes <artist/genre>"`.
   "Not this" → `cos music next` (on a radio or playlist it skips to the next song) and
   remember the dislike if it's a pattern.

## Rules

- Never set the volume to 0: Music shows a blocking dialog. "Mute" means `cos music pause`.
- Never use System Events / UI scripting to press buttons in Music.
- If the same failure happens twice, `cos friction add "..." --area music`.
