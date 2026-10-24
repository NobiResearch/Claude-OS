import AppKit

/// Where Claude OS lives and how to start its server.
///
/// app/build.sh bakes `ClaudeOSRoot` (the repo root) and `ClaudeOSPath` (the builder's
/// $PATH) into the bundle's Info.plist. Both are machine-specific, so they only ever
/// exist in the built bundle, never in a committed file. Apps launched from Finder get
/// launchd's minimal PATH, which is why the shell PATH is baked in.
struct AppConfig {
    let root: URL
    let path: String
    let version: String

    /// Development override: `CLAUDE_OS_SERVE_CMD` is a full shell command, run via
    /// `/bin/sh -c` (in the repo root, with the baked PATH) instead of `cos serve`.
    /// It must honor the same contract: print `COS_SERVE_READY port=<n> token=<t>` on
    /// stdout, serve `/` and `/api/status` on 127.0.0.1, and exit when stdin closes.
    /// Use `exec` so the app's SIGTERM reaches the server. Example:
    ///   open --env CLAUDE_OS_SERVE_CMD='exec python3 /path/to/stub.py' "build/Claude OS.app"
    let serveCommandOverride: String?

    var cosScript: URL { root.appendingPathComponent("bin/cos") }

    static func load() -> AppConfig {
        let info = Bundle.main.infoDictionary ?? [:]
        let env = ProcessInfo.processInfo.environment

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
            path: path,
            version: nonEmpty(info["CFBundleShortVersionString"] as? String) ?? "dev",
            serveCommandOverride: nonEmpty(env["CLAUDE_OS_SERVE_CMD"])
        )
    }

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
    /// #1a1714, the desktop's dark warm gray.
    static let background = NSColor(srgbRed: 0x1a / 255.0, green: 0x17 / 255.0, blue: 0x14 / 255.0, alpha: 1)
}

/// Diagnostics go to the app's stderr only (never the unified log), and never include the token.
func log(_ message: String) {
    FileHandle.standardError.write(Data("ClaudeOS: \(message)\n".utf8))
}
