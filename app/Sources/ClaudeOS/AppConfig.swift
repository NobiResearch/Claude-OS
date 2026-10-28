import AppKit

/// Where Ovenbird lives and how to start its server.
///
/// A developer's own build (app/build.sh) bakes `ClaudeOSRoot` (the repo root) and
/// `ClaudeOSPath` (the builder's $PATH) into the bundle's Info.plist. Both are
/// machine-specific, so they only ever exist in the built bundle, never in a committed file.
/// Apps launched from Finder get launchd's minimal PATH, which is why the shell PATH is baked
/// in. A release (`app/build.sh --release`, decision 0015) bakes neither: it finds its code
/// at runtime, checks it's Ovenbird from this repository, and uses a fixed PATH.
struct AppConfig {
    let root: URL
    let path: String
    let version: String
    /// A downloaded release: `ClaudeOSCommit` in Info.plist, no `ClaudeOSRoot`.
    let release: Bool
    let commit: String?
    /// Why no usable checkout was found (releases only): shown instead of starting the server.
    let rootProblem: String?

    /// Development override: `CLAUDE_OS_SERVE_CMD` is a full shell command, run via
    /// `/bin/sh -c` (in the repo root, with the baked PATH) instead of `cos serve`.
    /// It must honor the same contract: print `COS_SERVE_READY port=<n> token=<t>` on
    /// stdout, serve `/` and `/api/status` on 127.0.0.1, and exit when stdin closes.
    /// Use `exec` so the app's SIGTERM reaches the server. Example:
    ///   open --env CLAUDE_OS_SERVE_CMD='exec python3 /path/to/stub.py' "build/Ovenbird.app"
    let serveCommandOverride: String?

    var cosScript: URL { root.appendingPathComponent("bin/cos") }

    /// The repository a release runs code from, and nothing else.
    static let repository = "github.com/NobiResearch/Ovenbird"
    /// Its name until decision 0019: GitHub sends it on to `repository`, and a copy cloned from
    /// it is still this repository. Like core.FORMER_REPOSITORIES, it's trusted forever: never
    /// rename or delete the NobiResearch organization, and never create Claude-OS in it again.
    static let formerRepositories = ["github.com/NobiResearch/Claude-OS"]
    /// Where a release's first launch puts Ovenbird when there's no checkout yet.
    static let installFolder = "Library/Application Support/Ovenbird"

    static func load() -> AppConfig {
        let info = Bundle.main.infoDictionary ?? [:]
        let env = ProcessInfo.processInfo.environment
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let commit = nonEmpty(info["ClaudeOSCommit"] as? String)
        let release = nonEmpty(info["ClaudeOSRoot"] as? String) == nil && commit != nil
        let version = nonEmpty(info["CFBundleShortVersionString"] as? String) ?? "dev"
        let override = release ? nil : nonEmpty(env["CLAUDE_OS_SERVE_CMD"])

        if release {
            let link = home + "/.local/bin/cos"
            let linked = FileManager.default.fileExists(atPath: link)
                ? URL(fileURLWithPath: link).resolvingSymlinksInPath().deletingLastPathComponent()
                    .deletingLastPathComponent().path
                : nil
            let found = releaseCandidates(home: home, linkedRoot: linked).first {
                isClaudeOS($0, fileExists: { FileManager.default.fileExists(atPath: $0) },
                           read: { try? String(contentsOfFile: $0, encoding: .utf8) })
            }
            return AppConfig(
                root: URL(fileURLWithPath: found ?? home + "/" + installFolder, isDirectory: true),
                path: releasePath(home: home), version: version, release: true, commit: commit,
                rootProblem: found == nil ? missingCodeMessage : nil, serveCommandOverride: nil)
        }

        let rootPath = nonEmpty(info["ClaudeOSRoot"] as? String)
            ?? nonEmpty(env["CLAUDE_OS_ROOT"])
            ?? findRootFromExecutable()
            ?? FileManager.default.currentDirectoryPath

        var path = nonEmpty(info["ClaudeOSPath"] as? String) ?? nonEmpty(env["PATH"]) ?? ""
        let parts = path.split(separator: ":").map(String.init)
        for dir in ["/usr/bin", "/bin", "/usr/sbin", "/sbin"] where !parts.contains(dir) {
            path += (path.isEmpty ? "" : ":") + dir
        }

        return AppConfig(
            root: URL(fileURLWithPath: rootPath, isDirectory: true),
            path: path, version: version, release: false, commit: commit, rootProblem: nil,
            serveCommandOverride: override
        )
    }

    /// Where a release looks for its code, in order: the checkout `cos install` linked into
    /// ~/.local/bin (a developer's own), then the folder a release's first launch uses. Never
    /// CLAUDE_OS_ROOT or the current folder: those are for developers' own builds.
    static func releaseCandidates(home: String, linkedRoot: String?) -> [String] {
        [linkedRoot, home + "/" + installFolder].compactMap { $0 }
    }

    /// A fixed PATH: a release never bakes in anyone's shell PATH.
    static func releasePath(home: String) -> String {
        [home + "/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
            .joined(separator: ":")
    }

    /// Is this folder Ovenbird, cloned from `repository`? Read from the files themselves: a
    /// release never runs `git` to find out (on a Mac without the command line tools, that
    /// would summon Apple's install dialog).
    static func isClaudeOS(_ root: String, fileExists: (String) -> Bool, read: (String) -> String?) -> Bool {
        guard fileExists(root + "/bin/cos"), fileExists(root + "/lib/cos/__init__.py"),
              let config = read(root + "/.git/config") else { return false }
        return originURL(gitConfig: config).map(isRepository) ?? false
    }

    /// `[remote "origin"] url = …` from a .git/config, or nil.
    static func originURL(gitConfig: String) -> String? {
        var inOrigin = false
        for raw in gitConfig.split(separator: "\n") {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.hasPrefix("[") {
                inOrigin = line == "[remote \"origin\"]"
            } else if inOrigin, line.hasPrefix("url") {
                let parts = line.split(separator: "=", maxSplits: 1)
                if parts.count == 2, parts[0].trimmingCharacters(in: .whitespaces) == "url" {
                    return parts[1].trimmingCharacters(in: .whitespaces)
                }
            }
        }
        return nil
    }

    static func isRepository(_ url: String) -> Bool {
        var u = url.lowercased()
        for prefix in ["https://", "ssh://git@", "git@"] where u.hasPrefix(prefix) { u.removeFirst(prefix.count) }
        u = u.replacingOccurrences(of: "github.com:", with: "github.com/")
        if u.hasSuffix(".git") { u.removeLast(4) }
        if u.hasSuffix("/") { u.removeLast() }
        return ([repository] + formerRepositories).contains { u == $0.lowercased() }
    }

    /// What `cos` reads to find this app (decision 0015): which bundle and which build, so its
    /// claude-os:// links reach this copy and not another one macOS prefers. Written at launch
    /// to ~/.claude-os/state/app.json (mode 0600), next to the link nonce.
    func record(base: URL = AppURL.base) {
        let state: [String: Any] = [
            "bundle": Bundle.main.bundlePath, "bundle_id": Bundle.main.bundleIdentifier ?? "",
            "version": version, "commit": commit ?? NSNull(), "release": release, "root": root.path,
            "pid": Int(getpid()), "ts": Date().timeIntervalSince1970,
        ]
        let file = base.appendingPathComponent("state/app.json")
        guard let data = try? JSONSerialization.data(withJSONObject: state, options: [.sortedKeys]) else { return }
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.createFile(atPath: file.path, contents: data, attributes: [.posixPermissions: 0o600]) {
            log("couldn't write state/app.json")
        }
    }

    /// Until the first-launch checklist (0015, step 5): what to do when a release finds no code.
    static let missingCodeMessage = """
        Ovenbird needs its code on this Mac. In Terminal, run:

          git clone https://\(repository).git "$HOME/\(installFolder)"

        then open Ovenbird again. If macOS offers to install the command line developer tools, \
        say yes: Ovenbird runs on them.
        """

    /// For `swift run` during development: walk up from the executable to the repo root.
    private static func findRootFromExecutable() -> String? {
        var dir = Bundle.main.executableURL?.resolvingSymlinksInPath().deletingLastPathComponent()
        while let d = dir, d.path != "/" {
            if FileManager.default.fileExists(atPath: d.appendingPathComponent("bin/cos").path) {
                return d.path
            }
            dir = d.deletingLastPathComponent()
        }
        return nil
    }

    private static func nonEmpty(_ s: String?) -> String? {
        guard let s = s?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty else { return nil }
        return s
    }
}

enum Theme {
    /// #0f0f0f: the desktop's background (ui/style.css --bg), so loading shows no seam.
    static let background = NSColor(srgbRed: 0x0f / 255.0, green: 0x0f / 255.0, blue: 0x0f / 255.0, alpha: 1)
}

/// Diagnostics go to the app's stderr only (never the unified log), and never include the token.
func log(_ message: String) {
    FileHandle.standardError.write(Data("ClaudeOS: \(message)\n".utf8))
}
