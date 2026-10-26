import Foundation

/// A downloaded Claude OS.app's first launch (decision 0015, step 5): what this Mac still needs
/// before the desktop can start, found without prompting for anything, and the one download it
/// makes after a click. Nothing here runs `git` or `python3` before the command line tools are
/// known to be installed: on a Mac without them, /usr/bin/git and /usr/bin/python3 are shims
/// that summon Apple's install dialog.
enum FirstLaunch {
    /// What the install folder holds.
    enum Folder: Equatable {
        case absent, empty, claudeOS
        /// Something else (another project, a fork, a half-finished copy): left alone.
        case other
    }

    static let claudeCodePage = URL(string: "https://claude.com/claude-code")!

    // MARK: what's there

    /// The developer folder `xcode-select -p` names, if it has git and python3. `xcode-select
    /// -p` only reads a setting; it never offers to install anything.
    static func developerDir() -> String? {
        let r = run("/usr/bin/xcode-select", ["-p"], environment: ["PATH": "/usr/bin:/bin"])
        guard r.status == 0 else { return nil }
        return toolsReady(r.output.trimmingCharacters(in: .whitespacesAndNewlines),
                          isExecutable: FileManager.default.isExecutableFile(atPath:))
    }

    static func toolsReady(_ dir: String, isExecutable: (String) -> Bool) -> String? {
        guard dir.hasPrefix("/"), isExecutable(dir + "/usr/bin/git"), isExecutable(dir + "/usr/bin/python3") else { return nil }
        return dir
    }

    /// Where Claude Code is, from a fixed list (its installer's folder, Homebrew's, npm's).
    static func claudeCode(home: String, isExecutable: (String) -> Bool = FileManager.default.isExecutableFile(atPath:)) -> String? {
        [home + "/.local/bin/claude", home + "/.claude/local/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]
            .first(where: isExecutable)
    }

    static func folder(_ path: String, entries: (String) -> [String]?, isClaudeOS: (String) -> Bool) -> Folder {
        guard let names = entries(path) else { return .absent }
        if names.allSatisfy({ $0 == ".DS_Store" }) { return .empty }
        return isClaudeOS(path) ? .claudeOS : .other
    }

    static func folder(_ path: String) -> Folder {
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: path, isDirectory: &isDir), !isDir.boolValue { return .other }
        return folder(path, entries: { try? FileManager.default.contentsOfDirectory(atPath: $0) },
                      isClaudeOS: { AppConfig.isClaudeOS($0, fileExists: { FileManager.default.fileExists(atPath: $0) },
                                                          read: { try? String(contentsOfFile: $0, encoding: .utf8) }) })
    }

    /// macOS runs a downloaded app from a random read-only copy until it's moved out of the
    /// folder it was downloaded to ("App Translocation"), and `cos` would lose track of it.
    static func translocated(_ bundlePath: String) -> Bool {
        bundlePath.contains("/AppTranslocation/")
    }

    static func inApplications(_ bundlePath: String, home: String) -> Bool {
        bundlePath.hasPrefix("/Applications/") || bundlePath.hasPrefix(home + "/Applications/")
    }

    static func isCommit(_ s: String?) -> Bool {
        guard let s = s, s.count == 40 else { return false }
        return s.allSatisfy { ("0"..."9").contains($0) || ("a"..."f").contains($0) }
    }

    // MARK: the download

    /// Like catch-up's git (evolve.SAFE_GIT): nothing from the repository runs, nothing stops
    /// to ask for a login, and only https is spoken.
    static let safeGit = ["-c", "core.hooksPath=/dev/null", "-c", "credential.helper=", "-c", "submodule.recurse=false",
                          "-c", "core.fsmonitor=false", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always"]

    /// No system or personal git config: a url.insteadOf rule there could send the clone
    /// somewhere else.
    static func gitEnvironment(home: String) -> [String: String] {
        ["HOME": home, "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8",
         "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "",
         "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"]
    }

    /// The git commands that put `commit` of this repository's main into `dir`, on a `main`
    /// that tracks GitHub's, the way catch-up expects to find it.
    static func cloneSteps(commit: String, into dir: String) -> [[String]] {
        [safeGit + ["clone", "--quiet", "--no-checkout", "--no-recurse-submodules", "--single-branch", "--branch", "main",
                    "https://\(AppConfig.repository).git", dir],
         safeGit + ["-C", dir, "merge-base", "--is-ancestor", commit, "origin/main"],
         safeGit + ["-C", dir, "checkout", "--quiet", "-B", "main", commit],
         safeGit + ["-C", dir, "branch", "--quiet", "--set-upstream-to=origin/main", "main"]]
    }

    /// A downloaded copy's Claude Code may not push or use GitHub on its own: the repository
    /// isn't the person's (decision 0013 covers only a repository the human owns).
    static let localSettings: [String: Any] = [
        "permissions": ["deny": ["Bash(gh *)", "Bash(gh-axi *)", "Bash(git push*)"]],
    ]

    /// Downloads Claude OS into `target`: into a folder beside it first, so `target` only ever
    /// holds a complete, checked copy. Runs off the main thread; returns why it failed, or nil.
    static func download(commit: String, git: String, target: URL, home: String) -> String? {
        let fm = FileManager.default
        let parent = target.deletingLastPathComponent()
        let staging = parent.appendingPathComponent(".Claude OS download \(UUID().uuidString)")
        defer { try? fm.removeItem(at: staging) }  // ours, made a moment ago; gone once it's moved
        do {
            try fm.createDirectory(at: parent, withIntermediateDirectories: true)
        } catch {
            return "Couldn't create \(parent.path): \(error.localizedDescription)"
        }
        let env = gitEnvironment(home: home)
        let steps = cloneSteps(commit: commit, into: staging.path)
        for (i, args) in steps.enumerated() {
            let r = run(git, args, environment: env, timeout: i == 0 ? 600 : 60)
            if r.status != 0 {
                if i == 1 { return "This app's version (\(commit.prefix(7))) isn't on GitHub's main. Download the latest Claude OS.app." }
                let said = (r.error.isEmpty ? r.output : r.error).trimmingCharacters(in: .whitespacesAndNewlines)
                return i == 0 ? "Couldn't download Claude OS from GitHub. Are you online?\n\n\(said.suffix(400))"
                              : "git couldn't set up the download: \(said.suffix(400))"
            }
        }
        let head = run(git, safeGit + ["-C", staging.path, "rev-parse", "HEAD"], environment: env)
        guard head.output.trimmingCharacters(in: .whitespacesAndNewlines) == commit, folder(staging.path) == .claudeOS else {
            return "The download isn't the Claude OS this app expects; nothing was installed."
        }
        do {
            let settings = staging.appendingPathComponent(".claude/settings.local.json")
            try fm.createDirectory(at: settings.deletingLastPathComponent(), withIntermediateDirectories: true)
            try JSONSerialization.data(withJSONObject: localSettings, options: [.prettyPrinted, .sortedKeys]).write(to: settings)
            if folder(target.path) == .empty { try fm.removeItem(at: target) }
            try fm.moveItem(at: staging, to: target)
        } catch {
            return "Couldn't put Claude OS in \(target.path): \(error.localizedDescription)"
        }
        return nil
    }

    /// What `cos` reads to know this checkout came with a downloaded app, and what Remove Claude
    /// OS may take away again: ~/.claude-os/state/install.json, mode 0600.
    static func recordInstall(root: String, commit: String, version: String, base: URL = AppURL.base) {
        let record: [String: Any] = ["kind": "download", "root": root, "commit": commit, "version": version,
                                     "ts": Date().timeIntervalSince1970]
        let file = base.appendingPathComponent("state/install.json")
        guard let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]) else { return }
        AppURL.makeBase()
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.createFile(atPath: file.path, contents: data, attributes: [.posixPermissions: 0o600]) {
            log("couldn't write state/install.json")
        }
    }

    // MARK: processes

    struct Result {
        let status: Int32
        let output: String
        let error: String
    }

    /// Runs a program with exactly this environment, never through a shell. A timeout
    /// terminates it.
    static func run(_ path: String, _ args: [String], environment: [String: String], timeout: TimeInterval = 30) -> Result {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        p.environment = environment
        p.standardInput = FileHandle.nullDevice
        let out = Pipe(), err = Pipe()
        p.standardOutput = out
        p.standardError = err
        do { try p.run() } catch { return Result(status: -1, output: "", error: error.localizedDescription) }
        // Drain both pipes while it runs, so a chatty process can't fill one and stall.
        let outData = Drained(out), errData = Drained(err)
        let deadline = Date().addingTimeInterval(timeout)
        while p.isRunning && Date() < deadline { usleep(50_000) }
        if p.isRunning { p.terminate() }
        p.waitUntilExit()
        return Result(status: p.terminationStatus, output: String(decoding: outData.wait(), as: UTF8.self),
                      error: String(decoding: errData.wait(), as: UTF8.self))
    }

    /// A pipe read to its end on another thread.
    private final class Drained: @unchecked Sendable {
        private var data = Data()
        private let done = DispatchSemaphore(value: 0)

        init(_ pipe: Pipe) {
            DispatchQueue.global().async {
                self.data = pipe.fileHandleForReading.readDataToEndOfFile()
                self.done.signal()
            }
        }

        func wait() -> Data {
            done.wait()
            return data
        }
    }
}
