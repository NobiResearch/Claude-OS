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
///   claude-os://music/pause | resume | stop
///   claude-os://music/love               love the current song in the human's Apple Music
/// Every command rewrites ~/.claude-os/state/player.json, which `cos music now` reads.
/// The worst a stray link can do is play or pause a song, or favorite the one playing.
@MainActor
final class Player {
    static let shared = Player()

    private let player = ApplicationMusicPlayer.shared
    private var current: Song?
    private var lovedID: String?
    private var lastError: String?
    private var ticker: Timer?

    private lazy var stateURL: URL = {
        let env = ProcessInfo.processInfo.environment["CLAUDE_OS_HOME"]
        let base = env.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude-os")
        return base.appendingPathComponent("state/player.json")
    }()

    func handle(_ url: URL) {
        guard url.scheme == "claude-os", url.host == "music" else { return }
        let command = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let id = query.first(where: { $0.name == "id" })?.value ?? ""
        Task { @MainActor in
            switch command {
            case "authorize": await authorize()
            case "play" where !id.isEmpty && id.allSatisfy(\.isNumber): await play(id: id)
            case "pause": player.pause(); ticker?.invalidate(); lastError = nil; await settledWrite()
            case "resume": try? await player.play(); startTicking(); lastError = nil; await settledWrite()
            case "stop": player.stop(); ticker?.invalidate(); current = nil; lastError = nil; await settledWrite()
            case "love": await love()
            default: lastError = "unknown music command"; write()
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

    /// "Love" the current song in the human's Apple Music (the same as ♥ in Music), via the
    /// Apple Music API's ratings endpoint. MusicDataRequest adds both tokens itself.
    private func love() async {
        guard let song = current else {
            lastError = "nothing is playing in Claude OS"
            write()
            return
        }
        do {
            let id = song.id.rawValue
            var request = URLRequest(url: URL(string: "https://api.music.apple.com/v1/me/ratings/songs/\(id)")!)
            request.httpMethod = "PUT"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["type": "rating", "attributes": ["value": 1]])
            _ = try await MusicDataRequest(urlRequest: request).response()
            lovedID = id
            lastError = nil
        } catch {
            lastError = "couldn't love it: \(error.localizedDescription)"
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
            state["duration"] = song.duration ?? 0
            state["position"] = player.playbackTime
            state["artwork"] = song.artwork?.url(width: 600, height: 600)?.absoluteString ?? ""
            state["loved"] = lovedID == song.id.rawValue
        }
        if let error = lastError { state["error"] = error }
        do {
            try FileManager.default.createDirectory(at: stateURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: state, options: [.sortedKeys])
            try data.write(to: stateURL, options: .atomic)
        } catch {
            log("couldn't write player state: \(error.localizedDescription)")
        }
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
