---
name: music
description: Play, find and control music in Apple Music. Use for any request about songs, artists, albums, playlists, moods ("find me a chill song", "play something to focus"), what's playing, skipping, volume, or liking a track.
argument-hint: "[what you want to hear]"
---

# Music

You are the DJ. The syscall does mechanics; you bring taste.

## Steps

1. **Know the listener.** Check the boot banner's memory for music preferences. If you need
   more, `bin/cos music history` shows what they've played lately.
2. **Turn the request into a concrete pick.**
   - A specific song/artist/album: use it as the query.
   - A mood or activity ("chill", "focus", "rainy Sunday"): pick a *specific* song you know
     fits, biased toward their taste. Example: chill → "Weightless Marconi Union", "Sunset
     Lover Petit Biscuit", "Teardrop Massive Attack", "An Ending (Ascent) Brian Eno". Vary
     your picks between requests; check history so you don't repeat the last one.
   - "Something from my library": `bin/cos music find <genre or word>`, or
     `bin/cos music playlists`, then play a playlist with `--shuffle`.
3. **Play it.** `bin/cos music play "<song> <artist>"`. It tries the library first; then, if
   "Apple Music in Claude OS" is on, it plays the catalog song in Claude OS's own player;
   otherwise it opens the song page in Music (`bin/cos music setup` shows the state). `--source catalog`
   skips the library; `--pick N` chooses another result from `bin/cos music catalog "<query>"`.
4. **Report** in one line what's playing and why you picked it. If playback only *opened*
   the song (catalog playback isn't fully scriptable), say it's open in Music and they need
   to press play. Don't retry in a loop.
5. **Learn.** "I love this" → `bin/cos music like` plus `bin/cos remember "likes <artist/genre>"`.
   "Not this" → `bin/cos music next` and remember the dislike if it's a pattern.

## Rules

- Never set the volume to 0: Music shows a blocking dialog. "Mute" means `bin/cos music pause`.
- Never use System Events / UI scripting to press buttons in Music.
- If the same failure happens twice, `bin/cos friction add "..." --area music`.
