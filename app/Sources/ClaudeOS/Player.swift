import AppKit
import MusicKit

/// Claude OS's own Apple Music player (decision 0003, amended): MusicKit's
/// ApplicationMusicPlayer plays any catalog song with the human's subscription, under the
/// narrow "Media & Apple Music" permission. No UI scripting, no Accessibility.
///
/// Commands arrive as URLs, so `cos` (and Claude sessions, through `cos`) can drive it
/// without any token or private channel:
///   claude-os://music/authorize          ask macOS for Media & Apple Music access
///   claude-os://music/play?id=<digits>   play a catalog song by its Apple Music id
///   claude-os://music/play-library?title=…&artist=…   play a song from the human's library
///   claude-os://music/pause | resume | stop
///   claude-os://music/love               love the current song in the human's Apple Music
///   claude-os://music/unlove             remove that rating again
/// Every command rewrites ~/.claude-os/state/player.json, which `cos music now` reads.
/// The worst a stray link can do is play or pause a song, or favorite the one playing.
/// The music commands a claude-os:// link can carry. Anything else is refused, and ids must
/// be all digits, so a stray link can at most play, pause or rate a song.
enum MusicCommand: Equatable {
    case authorize, pause, resume, stop, love, unlove
    case play(id: String)
    case playLibrary(title: String, artist: String)

    init?(url: URL) {
        guard url.scheme == "claude-os", url.host == "music" else { return nil }
        let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        func value(_ name: String) -> String { query.first(where: { $0.name == name })?.value ?? "" }
        switch url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/")) {
        case "authorize": self = .authorize
        case "pause": self = .pause
        case "resume": self = .resume
        case "stop": self = .stop
        case "love": self = .love
        case "unlove": self = .unlove
        case "play":
            let id = value("id")
            guard !id.isEmpty, id.allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
            self = .play(id: id)
        case "play-library":
            let title = value("title")
            guard !title.isEmpty, title.count <= 200 else { return nil }
            self = .playLibrary(title: title, artist: String(value("artist").prefix(200)))
        default: return nil
        }
    }
}

@MainActor
final class Player {
    static let shared = Player()

    private let player = ApplicationMusicPlayer.shared
    private var current: Song?
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
        case .authorize, .play, .playLibrary:
            guard Self.appleMusicEnabled else {
                lastError = "Apple Music in Claude OS is off (Settings › Permissions)"
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
            case .pause: player.pause(); ticker?.invalidate(); lastError = nil; await settledWrite()
            case .resume: try? await player.play(); startTicking(); lastError = nil; await settledWrite()
            case .stop: player.stop(); ticker?.invalidate(); current = nil; lastError = nil; await settledWrite()
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
            current = song
            lastError = nil
            startTicking()
        } catch {
            lastError = "MusicKit couldn't play it from the library: \(error.localizedDescription)"
        }
        write()
    }

    /// "Love" the current song in the human's Apple Music (the same as ♥ in Music), via the
    /// Apple Music API's ratings endpoint. MusicDataRequest adds both tokens itself.
    private func rate(love: Bool) async {
        guard let song = current else {
            lastError = "nothing is playing in Claude OS"
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

    /// Keep player.json fresh while something plays (position, end of song).
    private func startTicking() {
        ticker?.invalidate()
        ticker = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self else { return }
                self.write()
                if self.player.state.playbackStatus != .playing { self.ticker?.invalidate() }
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
        if let song = current {
            state["id"] = song.id.rawValue
            state["track"] = song.title
            state["artist"] = song.artistName
            state["album"] = song.albumTitle ?? ""
            state["duration"] = Self.seconds(song.duration)
            state["position"] = player.playbackTime
            state["artwork"] = song.artwork?.url(width: 600, height: 600)?.absoluteString ?? ""
            state["loved"] = lovedID == song.id.rawValue
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
