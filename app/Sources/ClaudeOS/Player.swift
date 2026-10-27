import AppKit
import MusicKit

/// Ovenbird's own Apple Music player (decision 0003, amended): MusicKit's
/// ApplicationMusicPlayer plays any catalog song with the human's subscription, under the
/// narrow "Media & Apple Music" permission. No UI scripting, no Accessibility.
///
/// Commands arrive as URLs from `cos` (and Claude sessions, through `cos`), carrying this
/// launch's nonce (AppURL), so a link from anywhere else is refused:
///   claude-os://music/authorize          ask macOS for Media & Apple Music access
///   claude-os://music/play?id=<digits>   play a catalog song by its Apple Music id
///   claude-os://music/play-library?title=…&artist=…   play a song from the human's library
///   claude-os://music/play-playlist?name=…&shuffle=1|0  play one of the human's playlists
///   claude-os://music/radio?id=<digits>  a catalog song, then similar music (its station)
///   claude-os://music/pause | resume | stop | next | previous
///   claude-os://music/shuffle?on=1|0
///   claude-os://music/love               love the current song in the human's Apple Music
///   claude-os://music/unlove             remove that rating again
/// Every command rewrites ~/.claude-os/state/player.json, which `cos music now` reads.
/// The music commands a claude-os:// link can carry. Anything else is refused, and ids must
/// be all digits, so even a trusted link can at most play, pause or rate a song.
enum MusicCommand: Equatable {
    case authorize, pause, resume, stop, next, previous, love, unlove
    case play(id: String)
    case playLibrary(title: String, artist: String)
    case playPlaylist(name: String, shuffle: Bool?)
    case radio(id: String)
    case shuffle(on: Bool)

    init?(url: URL) {
        guard url.scheme == "claude-os", url.host == "music" else { return nil }
        let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        func value(_ name: String) -> String { query.first(where: { $0.name == name })?.value ?? "" }
        switch url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/")) {
        case "authorize": self = .authorize
        case "pause": self = .pause
        case "resume": self = .resume
        case "stop": self = .stop
        case "next": self = .next
        case "previous": self = .previous
        case "love": self = .love
        case "unlove": self = .unlove
        case "play", "radio":
            let id = value("id")
            guard !id.isEmpty, id.allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
            self = url.path.hasSuffix("radio") ? .radio(id: id) : .play(id: id)
        case "play-library":
            let title = value("title")
            guard !title.isEmpty, title.count <= 200 else { return nil }
            self = .playLibrary(title: title, artist: String(value("artist").prefix(200)))
        case "play-playlist":
            let name = value("name")
            guard !name.isEmpty, name.count <= 200 else { return nil }
            let shuffle = value("shuffle")
            self = .playPlaylist(name: name, shuffle: shuffle.isEmpty ? nil : shuffle == "1")
        case "shuffle":
            guard ["0", "1"].contains(value("on")) else { return nil }
            self = .shuffle(on: value("on") == "1")
        default: return nil
        }
    }
}

@MainActor
final class Player {
    static let shared = Player()

    private let player = ApplicationMusicPlayer.shared
    private var current: Song?
    private var playlist: String?  // the playlist playing, if any; then the queue says which song
    private var radioSeed: Song?   // radio: the song it started from (decision 0005)
    private var station: String?   // radio: the station playing after it, if Apple Music had one
    private var note: String?      // something worth saying that isn't an error
    private var lovedID: String?
    private var requestID: String?
    private var lastError: String?
    private var ticker: Timer?

    private lazy var stateURL: URL = {
        let env = ProcessInfo.processInfo.environment["CLAUDE_OS_HOME"]
        let base = env.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude-os")
        return base.appendingPathComponent("state/player.json")
    }()

    func handle(_ url: URL, trusted: Bool) {
        requestID = AppURL.requestID(url)
        guard trusted else {
            log("refused a music link without this launch's nonce")
            return
        }
        guard let command = MusicCommand(url: url) else {
            lastError = "unknown music command"
            write()
            return
        }
        switch command {
        case .authorize, .play, .playLibrary, .playPlaylist, .radio:
            guard Self.appleMusicEnabled else {
                lastError = "Apple Music in Ovenbird is off (Settings › Permissions)"
                write()
                return
            }
        default:
            break
        }
        Task { @MainActor in
            switch command {
            case .authorize: await authorize()
            case .play(let id): await play(id: id)
            case .playLibrary(let title, let artist): await playLibrary(title: title, artist: artist)
            case .playPlaylist(let name, let shuffle): await playPlaylist(name: name, shuffle: shuffle)
            case .radio(let id): await startRadio(id: id)
            case .pause: player.pause(); ticker?.invalidate(); lastError = nil; await settledWrite()
            case .resume: try? await player.play(); startTicking(); lastError = nil; await settledWrite()
            case .stop:
                player.stop(); ticker?.invalidate(); forget(); lastError = nil
                await settledWrite()
            case .next: await skip { try await $0.skipToNextEntry() }
            case .previous: await skip { try await $0.skipToPreviousEntry() }
            case .shuffle(let on): player.state.shuffleMode = on ? .songs : .off; lastError = nil; write()
            case .love: await rate(love: true)
            case .unlove: await rate(love: false)
            }
        }
    }

    @discardableResult
    private func authorize() async -> Bool {
        let status = await MusicAuthorization.request()
        lastError = status == .authorized ? nil : "Apple Music access is \(Self.describe(status))"
        write()
        return status == .authorized
    }

    private func play(id: String) async {
        if MusicAuthorization.currentStatus != .authorized {
            guard await authorize() else { return }
        }
        do {
            let request = MusicCatalogResourceRequest<Song>(matching: \.id, equalTo: MusicItemID(id))
            guard let song = try await request.response().items.first else {
                lastError = "Apple Music doesn't have song \(id) in this storefront"
                write()
                return
            }
            player.queue = [song]
            try await player.play()
            forget()
            current = song
            lastError = nil
            startTicking()
        } catch {
            // Most often: MusicKit isn't enabled for this app's bundle id in the developer account.
            lastError = "MusicKit couldn't play it: \(error.localizedDescription)"
        }
        write()
    }

    /// One player (decision 0004): library songs play here too, so now-playing, pause and
    /// love work the same for everything. Matching is by title, then artist if given.
    private func playLibrary(title: String, artist: String) async {
        if MusicAuthorization.currentStatus != .authorized {
            guard await authorize() else { return }
        }
        do {
            var request = MusicLibraryRequest<Song>()
            request.filter(matching: \.title, contains: title)
            request.limit = 25
            let songs = try await request.response().items
            let wanted = artist.lowercased()
            guard let song = songs.first(where: { wanted.isEmpty || $0.artistName.lowercased().contains(wanted) })
                    ?? songs.first else {
                lastError = "no song called \(title) in the library"
                write()
                return
            }
            player.queue = [song]
            try await player.play()
            forget()
            current = song
            lastError = nil
            startTicking()
        } catch {
            lastError = "MusicKit couldn't play it from the library: \(error.localizedDescription)"
        }
        write()
    }

    /// A playlist from the human's library, so "play my Deep Work playlist" plays here too
    /// and pause, next and love keep working. `cos` matches the name against Music's list
    /// first; here an exact (case-insensitive) match wins over a partial one.
    private func playPlaylist(name: String, shuffle: Bool?) async {
        if MusicAuthorization.currentStatus != .authorized {
            guard await authorize() else { return }
        }
        do {
            var request = MusicLibraryRequest<Playlist>()
            request.filter(matching: \.name, contains: name)
            request.limit = 25
            let lists = try await request.response().items
            guard let list = lists.first(where: { $0.name.lowercased() == name.lowercased() }) ?? lists.first else {
                lastError = "no playlist called \(name) in the library"
                write()
                return
            }
            if let shuffle = shuffle { player.state.shuffleMode = shuffle ? .songs : .off }
            player.queue = [list]
            try await player.play()
            forget()
            playlist = list.name
            lastError = nil
            startTicking()
        } catch {
            lastError = "MusicKit couldn't play the playlist: \(error.localizedDescription)"
        }
        write()
    }

    /// Radio (0005): the song first, then similar music. Apple Music's station for the song
    /// if it has one, else the artist's; if neither, the song alone, and player.json says so
    /// (`station` missing), so the worst case is today's single song.
    private func startRadio(id: String) async {
        if MusicAuthorization.currentStatus != .authorized {
            guard await authorize() else { return }
        }
        do {
            let request = MusicCatalogResourceRequest<Song>(matching: \.id, equalTo: MusicItemID(id))
            guard let song = try await request.response().items.first else {
                lastError = "Apple Music doesn't have song \(id) in this storefront"
                write()
                return
            }
            let detailed = (try? await song.with([.station, .artists])) ?? song
            var found = detailed.station
            if found == nil, let artist = detailed.artists?.first {
                found = try? await artist.with([.station]).station
            }
            forget()
            player.queue = [song]
            try await player.play()
            radioSeed = song
            current = song
            if let found = found {
                do {
                    try await player.queue.insert(found, position: .tail)
                    station = found.name
                    current = nil
                } catch {
                    note = "Apple Music wouldn't queue its station, so the song plays alone"
                }
            } else {
                note = "Apple Music has no station for it, so the song plays alone"
            }
            lastError = nil
            startTicking()
        } catch {
            lastError = "MusicKit couldn't start the radio: \(error.localizedDescription)"
        }
        write()
    }

    /// Whatever played before: a new command starts from a clean slate.
    private func forget() {
        current = nil
        playlist = nil
        radioSeed = nil
        station = nil
        note = nil
    }

    /// A playlist or a station moves along by itself: then the queue says what's playing.
    private var queueMoves: Bool { playlist != nil || station != nil }

    private func skip(_ move: (ApplicationMusicPlayer) async throws -> Void) async {
        do {
            try await move(player)
            lastError = nil
            startTicking()
        } catch {
            lastError = "couldn't skip: \(error.localizedDescription)"
        }
        await settledWrite()
    }

    /// The song playing. While the queue moves by itself, only its current entry counts:
    /// never an earlier song, so `love` can't rate the wrong one.
    private var nowPlaying: Song? {
        guard queueMoves else { return current }
        if let entry = player.queue.currentEntry, case .song(let song)? = entry.item { return song }
        return nil
    }

    /// "Love" the current song in the human's Apple Music (the same as ♥ in Music), via the
    /// Apple Music API's ratings endpoint. MusicDataRequest adds both tokens itself.
    private func rate(love: Bool) async {
        guard let song = nowPlaying else {
            lastError = queueMoves ? "can't tell which song is playing, so nothing was rated" : "nothing is playing in Ovenbird"
            write()
            return
        }
        do {
            let id = song.id.rawValue
            // Library songs have library ids ("i.…") and their own ratings endpoint.
            let kind = id.hasPrefix("i.") ? "library-songs" : "songs"
            var request = URLRequest(url: URL(string: "https://api.music.apple.com/v1/me/ratings/\(kind)/\(id)")!)
            if love {
                request.httpMethod = "PUT"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.httpBody = try JSONSerialization.data(withJSONObject: ["type": "rating", "attributes": ["value": 1]])
            } else {
                request.httpMethod = "DELETE"
            }
            _ = try await MusicDataRequest(urlRequest: request).response()
            lovedID = love ? id : nil
            lastError = nil
        } catch {
            lastError = "couldn't \(love ? "love" : "unlove") it: \(error.localizedDescription)"
        }
        write()
    }

    /// Keep player.json fresh while something plays (position, end of song). A few quiet
    /// ticks in a row end it, so the moment between two songs of a queue doesn't.
    private func startTicking() {
        ticker?.invalidate()
        var quiet = 0
        ticker = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self else { return }
                self.write()
                quiet = self.player.state.playbackStatus == .playing ? 0 : quiet + 1
                if quiet >= 3 { self.ticker?.invalidate() }
            }
        }
    }

    /// playbackStatus lags a command by a moment; report what actually happened.
    private func settledWrite() async {
        try? await Task.sleep(nanoseconds: 400_000_000)
        write()
    }

    private func write() {
        var state: [String: Any] = [
            "ts": Date().timeIntervalSince1970,
            "authorization": Self.describe(MusicAuthorization.currentStatus),
            "status": Self.describe(player.state.playbackStatus),
        ]
        state["shuffle"] = player.state.shuffleMode == .songs
        if let name = playlist { state["playlist"] = name }
        if let seed = radioSeed { state["radio"] = "\(seed.title) — \(seed.artistName)" }
        if let name = station { state["station"] = name }
        if let note = note { state["note"] = note }
        if let song = nowPlaying {
            state["id"] = song.id.rawValue
            state["track"] = song.title
            state["artist"] = song.artistName
            state["album"] = song.albumTitle ?? ""
            state["duration"] = Self.seconds(song.duration)
            state["position"] = player.playbackTime
            state["artwork"] = song.artwork?.url(width: 600, height: 600)?.absoluteString ?? ""
            state["loved"] = lovedID == song.id.rawValue
        } else if queueMoves, let entry = player.queue.currentEntry {
            state["track"] = entry.title  // a station's entry may not be a Song; still say what's on
            state["artist"] = entry.subtitle ?? ""
        }
        if let error = lastError { state["error"] = error }
        if let rid = requestID { state["rid"] = rid }
        do {
            try FileManager.default.createDirectory(at: stateURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: state, options: [.sortedKeys])
            try data.write(to: stateURL, options: .atomic)
        } catch {
            log("couldn't write player state: \(error.localizedDescription)")
        }
    }

    /// The human's switch in Settings (config.json › music.apple_music), read fresh each time.
    static var appleMusicEnabled: Bool {
        let url = AppURL.base.appendingPathComponent("config.json")
        guard let data = try? Data(contentsOf: url),
              let config = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let music = config["music"] as? [String: Any] else { return false }
        return music["apple_music"] as? Bool ?? false
    }

    /// Library songs report their duration in milliseconds (catalog songs in seconds);
    /// nothing real is longer than ten hours, so treat anything above that as ms.
    nonisolated static func seconds(_ duration: TimeInterval?) -> TimeInterval {
        guard let d = duration else { return 0 }
        return d > 36_000 ? d / 1000 : d
    }

    private static func describe(_ status: MusicAuthorization.Status) -> String {
        switch status {
        case .authorized: return "authorized"
        case .denied: return "denied"
        case .restricted: return "restricted"
        case .notDetermined: return "not determined"
        @unknown default: return "unknown"
        }
    }

    private static func describe(_ status: MusicPlayer.PlaybackStatus) -> String {
        switch status {
        case .playing: return "playing"
        case .paused: return "paused"
        case .stopped: return "stopped"
        case .interrupted: return "interrupted"
        case .seekingForward, .seekingBackward: return "seeking"
        @unknown default: return "unknown"
        }
    }
}
