import Foundation

/// claude-os:// links that change something (play, rate, ask macOS for a permission) must
/// carry this launch's nonce. It lives in ~/.claude-os/state/app.nonce (mode 0600), which
/// `cos` can read and a web page or another user can't, so a stray link can't make Claude
/// OS act or summon a permission prompt. Harmless links (refresh, flush) need no nonce.
enum AppURL {
    static var base: URL {
        let env = ProcessInfo.processInfo.environment["CLAUDE_OS_HOME"]
        return env.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude-os")
    }

    /// ~/.claude-os holds the journal and memory, so only its owner may look inside. On a new
    /// Mac the app can be the first to create it.
    static func makeBase() {
        guard !FileManager.default.fileExists(atPath: base.path) else { return }
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true,
                                                 attributes: [.posixPermissions: 0o700])
    }

    /// Created on first use (at launch, from the app delegate) and written for `cos`.
    static let nonce: String = {
        var bytes = [UInt8](repeating: 0, count: 16)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        let value = bytes.map { String(format: "%02x", $0) }.joined()
        let file = base.appendingPathComponent("state/app.nonce")
        do {
            makeBase()
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            FileManager.default.createFile(atPath: file.path, contents: Data(value.utf8), attributes: [.posixPermissions: 0o600])
        } catch {
            log("couldn't write the link nonce: \(error.localizedDescription)")
        }
        return value
    }()

    static func query(_ url: URL, _ name: String) -> String? {
        URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == name })?.value
    }

    static func authorized(_ url: URL, nonce: String = AppURL.nonce) -> Bool {
        guard !nonce.isEmpty, let given = query(url, "nonce") else { return false }
        return given == nonce
    }

    /// The caller's request id, echoed back in state files so `cos` knows which answer is its own.
    static func requestID(_ url: URL) -> String? {
        guard let rid = query(url, "rid"), !rid.isEmpty, rid.count <= 32,
              rid.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber) }) else { return nil }
        return rid
    }
}
