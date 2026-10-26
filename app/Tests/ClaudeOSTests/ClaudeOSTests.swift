import XCTest
@testable import ClaudeOS

final class MusicCommandTests: XCTestCase {
    func command(_ s: String) -> MusicCommand? { MusicCommand(url: URL(string: s)!) }

    func testKnownCommands() {
        XCTAssertEqual(command("claude-os://music/pause"), .pause)
        XCTAssertEqual(command("claude-os://music/love"), .love)
        XCTAssertEqual(command("claude-os://music/play?id=1080574498"), .play(id: "1080574498"))
        XCTAssertEqual(command("claude-os://music/play-library?title=Paper%20Lanterns&artist=The%20Quiet%20Hours"),
                       .playLibrary(title: "Paper Lanterns", artist: "The Quiet Hours"))
        XCTAssertEqual(command("claude-os://music/radio?id=1080574498"), .radio(id: "1080574498"))
        XCTAssertEqual(command("claude-os://music/play-playlist?name=Deep%20Work&shuffle=1"),
                       .playPlaylist(name: "Deep Work", shuffle: true))
        XCTAssertEqual(command("claude-os://music/play-playlist?name=Focus"), .playPlaylist(name: "Focus", shuffle: nil))
        XCTAssertEqual(command("claude-os://music/next"), .next)
        XCTAssertEqual(command("claude-os://music/previous"), .previous)
        XCTAssertEqual(command("claude-os://music/shuffle?on=0"), .shuffle(on: false))
    }

    func testEverythingElseIsRefused() {
        XCTAssertNil(command("claude-os://music/keystroke"))
        XCTAssertNil(command("claude-os://music/play?id=12a3"))
        XCTAssertNil(command("claude-os://music/play?id=١٢٣"), "non-ASCII digits")
        XCTAssertNil(command("claude-os://music/play"))
        XCTAssertNil(command("claude-os://music/play-library?artist=x"))
        XCTAssertNil(command("claude-os://music/play-playlist"))
        XCTAssertNil(command("claude-os://music/radio"), "radio needs a catalog song")
        XCTAssertNil(command("claude-os://music/radio?id=i.abc123"), "library ids have no station")
        XCTAssertNil(command("claude-os://music/play-playlist?name=" + String(repeating: "x", count: 201)))
        XCTAssertNil(command("claude-os://music/shuffle?on=yes"))
        XCTAssertNil(command("claude-os://calendar/pause"))
        XCTAssertNil(command("https://music/pause"))
    }
}

final class WebBridgeTests: XCTestCase {
    func testOnlyTheDesktopMainFrame() {
        XCTAssertTrue(WebBridge.allows(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 7357, serverPort: 7357))
        XCTAssertFalse(WebBridge.allows(mainFrame: false, scheme: "http", host: "127.0.0.1", port: 7357, serverPort: 7357))
        XCTAssertFalse(WebBridge.allows(mainFrame: true, scheme: "http", host: "localhost", port: 7357, serverPort: 7357))
        XCTAssertFalse(WebBridge.allows(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 8080, serverPort: 7357))
        XCTAssertFalse(WebBridge.allows(mainFrame: true, scheme: "https", host: "127.0.0.1", port: 7357, serverPort: 7357))
        XCTAssertFalse(WebBridge.allows(mainFrame: true, scheme: "http", host: "127.0.0.1", port: 7357, serverPort: nil))
    }
}

final class ServerEndpointTests: XCTestCase {
    func testReadyLine() {
        let ep = ServerEndpoint.parseReady("COS_SERVE_READY port=7357 token=abc_DEF-123\n")
        XCTAssertEqual(ep?.port, 7357)
        XCTAssertEqual(ep?.token, "abc_DEF-123")
        XCTAssertEqual(ep?.desktopURL.absoluteString, "http://127.0.0.1:7357/#token=abc_DEF-123")
        XCTAssertNil(ServerEndpoint.parseReady("COS_SERVE_READY port=0 token=x"))
        XCTAssertNil(ServerEndpoint.parseReady("COS_SERVE_READY port=7357"))
        XCTAssertNil(ServerEndpoint.parseReady("hello port=1 token=x"))
    }
}

final class PlayerTests: XCTestCase {
    func testLibraryDurationsInMillisecondsAreNormalized() {
        XCTAssertEqual(Player.seconds(147_227), 147.227, accuracy: 0.001)
        XCTAssertEqual(Player.seconds(237.0), 237.0)
        XCTAssertEqual(Player.seconds(nil), 0)
    }
}

final class AppURLTests: XCTestCase {
    func testLinksNeedThisLaunchesNonce() {
        let url = URL(string: "claude-os://music/play?id=1&nonce=abc123&rid=r1")!
        XCTAssertTrue(AppURL.authorized(url, nonce: "abc123"))
        XCTAssertFalse(AppURL.authorized(url, nonce: "other"))
        XCTAssertFalse(AppURL.authorized(URL(string: "claude-os://music/play?id=1")!, nonce: "abc123"))
        XCTAssertFalse(AppURL.authorized(url, nonce: ""), "an empty nonce never matches")
    }

    func testRequestIDs() {
        XCTAssertEqual(AppURL.requestID(URL(string: "claude-os://music/pause?rid=abc123DEF")!), "abc123DEF")
        XCTAssertNil(AppURL.requestID(URL(string: "claude-os://music/pause?rid=a%22b")!))
        XCTAssertNil(AppURL.requestID(URL(string: "claude-os://music/pause")!))
    }
}

final class ExternalLinkTests: XCTestCase {
    func testOnlyWebAndMailLeaveTheApp() {
        for ok in ["https://example.com", "http://example.com", "mailto:a@example.com"] {
            XCTAssertTrue(MainWindowController.opensExternally(URL(string: ok)!), ok)
        }
        for bad in ["claude-os://music/love", "file:///etc/passwd", "ssh://host", "shortcuts://run-shortcut?name=x", "smb://srv"] {
            XCTAssertFalse(MainWindowController.opensExternally(URL(string: bad)!), bad)
        }
    }
}

final class NotificationTargetTests: XCTestCase {
    func testOnlyKnownTargets() {
        XCTAssertEqual(NotifyTarget.allCases.map(\.rawValue), ["board", "brief", "evolve", "daemons"])
        for bad in ["", "Board", "board ", "javascript:alert(1)", "board');alert(1);('", "settings"] {
            XCTAssertNil(NotifyTarget(rawValue: bad), bad)
        }
    }

    func testEachTargetIsAFixedScript() {
        for target in NotifyTarget.allCases {
            XCTAssertEqual(MainWindowController.openJS(target),
                           "window.cos && window.cos.show && window.cos.show('\(target.rawValue)'); void 0")
        }
    }
}

/// Decision 0015, step 4: a release finds its code without baked paths, and runs only a
/// checkout of this repository.
final class ReleaseRootTests: XCTestCase {
    let config = "[core]\n\tbare = false\n[remote \"origin\"]\n\turl = https://github.com/NobiResearch/Claude-OS.git\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n"

    func testCandidatesInOrderNeverTheEnvironmentOrTheCurrentFolder() {
        XCTAssertEqual(AppConfig.releaseCandidates(home: "/Users/x", linkedRoot: "/Users/x/src/Claude-OS"),
                       ["/Users/x/src/Claude-OS", "/Users/x/Library/Application Support/Claude OS"])
        XCTAssertEqual(AppConfig.releaseCandidates(home: "/Users/x", linkedRoot: nil),
                       ["/Users/x/Library/Application Support/Claude OS"])
    }

    func testOnlyThisRepositorysOrigin() {
        XCTAssertEqual(AppConfig.originURL(gitConfig: config), "https://github.com/NobiResearch/Claude-OS.git")
        for ok in ["https://github.com/NobiResearch/Claude-OS.git", "https://github.com/NobiResearch/Claude-OS",
                   "git@github.com:NobiResearch/Claude-OS.git", "ssh://git@github.com/NobiResearch/Claude-OS.git"] {
            XCTAssertTrue(AppConfig.isRepository(ok), ok)
        }
        for bad in ["https://github.com/someone/Claude-OS.git", "https://example.com/NobiResearch/Claude-OS.git",
                    "https://github.com/NobiResearch/Claude-OS-evil.git",
                    "https://github.com/NobiResearch-evil/Claude-OS.git", ""] {
            XCTAssertFalse(AppConfig.isRepository(bad), bad)
        }
        XCTAssertNil(AppConfig.originURL(gitConfig: "[remote \"upstream\"]\n\turl = https://github.com/NobiResearch/Claude-OS.git\n"))
    }

    func testAFolderIsClaudeOSOnlyWithItsFilesAndOrigin() {
        let files: Set<String> = ["/r/bin/cos", "/r/lib/cos/__init__.py"]
        XCTAssertTrue(AppConfig.isClaudeOS("/r", fileExists: files.contains, read: { $0 == "/r/.git/config" ? self.config : nil }))
        XCTAssertFalse(AppConfig.isClaudeOS("/r", fileExists: { _ in false }, read: { _ in self.config }))
        XCTAssertFalse(AppConfig.isClaudeOS("/r", fileExists: files.contains, read: { _ in nil }), "no .git/config")
        let fork = config.replacingOccurrences(of: "NobiResearch", with: "someone")
        XCTAssertFalse(AppConfig.isClaudeOS("/r", fileExists: files.contains, read: { _ in fork }))
    }

    func testAReleasesPathIsFixed() {
        let path = AppConfig.releasePath(home: "/Users/x")
        XCTAssertTrue(path.hasPrefix("/Users/x/.local/bin:/opt/homebrew/bin:"))
        XCTAssertTrue(path.hasSuffix(":/usr/bin:/bin:/usr/sbin:/sbin"))
    }
}

/// Decision 0015, step 5: a downloaded app's first launch checks without prompting, and
/// downloads only this repository, only with a hardened git.
final class FirstLaunchTests: XCTestCase {
    func testTheToolsNeedGitAndPython() {
        let both: Set<String> = ["/L/CLT/usr/bin/git", "/L/CLT/usr/bin/python3"]
        XCTAssertEqual(FirstLaunch.toolsReady("/L/CLT", isExecutable: both.contains), "/L/CLT")
        XCTAssertNil(FirstLaunch.toolsReady("/L/CLT", isExecutable: { $0.hasSuffix("/git") }), "no python3")
        XCTAssertNil(FirstLaunch.toolsReady("", isExecutable: { _ in true }), "xcode-select said nothing")
        XCTAssertNil(FirstLaunch.toolsReady("relative", isExecutable: { _ in true }))
    }

    func testClaudeCodeFromAFixedList() {
        XCTAssertEqual(FirstLaunch.claudeCode(home: "/Users/x", isExecutable: { $0 == "/opt/homebrew/bin/claude" }),
                       "/opt/homebrew/bin/claude")
        XCTAssertEqual(FirstLaunch.claudeCode(home: "/Users/x", isExecutable: { _ in true }), "/Users/x/.local/bin/claude")
        XCTAssertNil(FirstLaunch.claudeCode(home: "/Users/x", isExecutable: { _ in false }))
    }

    func testTheInstallFolderIsUsedOnlyWhenEmpty() {
        func folder(_ entries: [String]?, claudeOS: Bool = false) -> FirstLaunch.Folder {
            FirstLaunch.folder("/f", entries: { _ in entries }, isClaudeOS: { _ in claudeOS })
        }
        XCTAssertEqual(folder(nil), .absent)
        XCTAssertEqual(folder([]), .empty)
        XCTAssertEqual(folder([".DS_Store"]), .empty)
        XCTAssertEqual(folder(["bin", "lib", ".git"], claudeOS: true), .claudeOS)
        XCTAssertEqual(folder(["notes.txt"]), .other)
        XCTAssertEqual(folder(["bin", "lib", ".git"]), .other, "a fork or a half copy is left alone")
    }

    func testAFileOrALinkWhereTheFolderGoesIsLeftAlone() throws {
        let fm = FileManager.default
        let dir = fm.temporaryDirectory.appendingPathComponent("cos-fl-\(UUID().uuidString)")
        try fm.createDirectory(at: dir.appendingPathComponent("empty"), withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: dir) }
        let file = dir.appendingPathComponent("file")
        try Data().write(to: file)
        XCTAssertEqual(FirstLaunch.folder(file.path), .other)
        let link = dir.appendingPathComponent("link")
        try fm.createSymbolicLink(at: link, withDestinationURL: dir.appendingPathComponent("empty"))
        XCTAssertEqual(FirstLaunch.folder(link.path), .other, "a link to an empty folder isn't ours to remove")
        XCTAssertEqual(FirstLaunch.folder(dir.appendingPathComponent("empty").path), .empty)
        XCTAssertEqual(FirstLaunch.folder(dir.appendingPathComponent("absent").path), .absent)
    }

    func testOnlyOurLeftoversAreCleanedUp() throws {
        let fm = FileManager.default
        let parent = fm.temporaryDirectory.appendingPathComponent("cos-left-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: parent) }
        func staging(_ name: String, origin: String?) throws -> URL {
            let dir = parent.appendingPathComponent(name)
            try fm.createDirectory(at: dir.appendingPathComponent(".git"), withIntermediateDirectories: true)
            if let origin = origin {
                try "[remote \"origin\"]\n\turl = \(origin)\n".write(to: dir.appendingPathComponent(".git/config"), atomically: true, encoding: .utf8)
            }
            return dir
        }
        let ours = try staging(".Claude OS download 1", origin: "https://github.com/NobiResearch/Claude-OS.git")
        let strange = try staging(".Claude OS download 2", origin: "https://github.com/someone/else.git")
        let unknown = try staging(".Claude OS download 3", origin: nil)
        let other = try staging("Something", origin: "https://github.com/NobiResearch/Claude-OS.git")
        FirstLaunch.removeLeftovers(beside: parent.appendingPathComponent("Claude OS"))
        XCTAssertFalse(fm.fileExists(atPath: ours.path))
        for kept in [strange, unknown, other] { XCTAssertTrue(fm.fileExists(atPath: kept.path), kept.lastPathComponent) }
    }

    func testACancelledDownloadNeverStarts() {
        let job = FirstLaunch.Download()
        job.cancel()
        let r = FirstLaunch.run("/bin/sleep", ["5"], environment: [:], launch: job.launch)
        XCTAssertEqual(r.status, -1)
        XCTAssertTrue(job.cancelled)
    }

    func testCancellingStopsTheRunningStep() {
        let job = FirstLaunch.Download()
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.5) { job.cancel() }
        let started = Date()
        let r = FirstLaunch.run("/bin/sleep", ["30"], environment: [:], timeout: 60, launch: job.launch)
        XCTAssertNotEqual(r.status, 0)
        XCTAssertLessThan(Date().timeIntervalSince(started), 10, "stopped, not run to the end")
    }

    func testWhereTheAppRunsFrom() {
        XCTAssertTrue(FirstLaunch.translocated("/private/var/folders/xy/T/AppTranslocation/1234/d/Claude OS.app"))
        XCTAssertFalse(FirstLaunch.translocated("/Applications/Claude OS.app"))
        XCTAssertTrue(FirstLaunch.inApplications("/Applications/Claude OS.app", home: "/Users/x"))
        XCTAssertTrue(FirstLaunch.inApplications("/Users/x/Applications/Claude OS.app", home: "/Users/x"))
        XCTAssertFalse(FirstLaunch.inApplications("/Users/x/Downloads/Claude OS.app", home: "/Users/x"))
    }

    func testOnlyAFullCommitIsUsed() {
        XCTAssertTrue(FirstLaunch.isCommit(String(repeating: "a1", count: 20)))
        for bad in [nil, "", "abc1234", String(repeating: "A1", count: 20), String(repeating: "g1", count: 20),
                    String(repeating: "a1", count: 20) + " "] {
            XCTAssertFalse(FirstLaunch.isCommit(bad), bad ?? "nil")
        }
    }

    func testTheCloneIsThisRepositoryWithAHardenedGit() {
        let commit = String(repeating: "ab", count: 20)
        let steps = FirstLaunch.cloneSteps(commit: commit, into: "/tmp/x")
        for step in steps {
            XCTAssertEqual(Array(step.prefix(FirstLaunch.safeGit.count)), FirstLaunch.safeGit)
        }
        for flag in ["core.hooksPath=/dev/null", "credential.helper=", "protocol.allow=never", "protocol.https.allow=always"] {
            XCTAssertTrue(FirstLaunch.safeGit.contains(flag), flag)
        }
        XCTAssertTrue(steps[0].contains("https://github.com/NobiResearch/Claude-OS.git"))
        XCTAssertTrue(steps[0].contains("--no-recurse-submodules"))
        XCTAssertEqual(Array(steps[1].suffix(4)), ["merge-base", "--is-ancestor", commit, "origin/main"])
        XCTAssertEqual(Array(steps[2].suffix(4)), ["--quiet", "-B", "main", commit])
        let env = FirstLaunch.gitEnvironment(home: "/Users/x")
        XCTAssertEqual(env["GIT_CONFIG_GLOBAL"], "/dev/null")
        XCTAssertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        XCTAssertEqual(env["GIT_TERMINAL_PROMPT"], "0")
    }

    func testADownloadedCopysClaudeDoesntUseGitHub() {
        let deny = (FirstLaunch.localSettings["permissions"] as? [String: [String]])?["deny"] ?? []
        XCTAssertEqual(Set(deny), ["Bash(gh *)", "Bash(gh-axi *)", "Bash(git push*)", "Bash(git * push*)"])
        let steps = FirstLaunch.cloneSteps(commit: String(repeating: "ab", count: 20), into: "/tmp/x")
        XCTAssertTrue(steps.contains { $0.suffix(2) == ["core.hooksPath", "githooks"] }, "the Guardian's hooks")
        XCTAssertTrue(steps.contains { $0.suffix(2) == ["remote.origin.pushurl", FirstLaunch.noPush] }, "origin can't push")
    }

    /// The real download, from GitHub: only with COS_NETWORK_TESTS=1 and COS_TEST_COMMIT=<a commit on main>.
    func testTheDownloadFromGitHub() throws {
        let env = ProcessInfo.processInfo.environment
        guard env["COS_NETWORK_TESTS"] == "1", let commit = env["COS_TEST_COMMIT"],
              let dir = FirstLaunch.developerDir() else { throw XCTSkip("needs COS_NETWORK_TESTS=1 and COS_TEST_COMMIT") }
        let parent = FileManager.default.temporaryDirectory.appendingPathComponent("cos-download-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: parent) }
        let target = parent.appendingPathComponent("Claude OS")
        XCTAssertNil(FirstLaunch.download(commit: commit, git: dir + "/usr/bin/git", target: target, home: NSHomeDirectory()))
        XCTAssertEqual(FirstLaunch.folder(target.path), .claudeOS)
        XCTAssertTrue(FileManager.default.fileExists(atPath: target.appendingPathComponent(".claude/settings.local.json").path))
        let branch = FirstLaunch.run(dir + "/usr/bin/git", ["-C", target.path, "rev-parse", "--abbrev-ref", "main@{upstream}"],
                                     environment: FirstLaunch.gitEnvironment(home: NSHomeDirectory()))
        XCTAssertEqual(branch.output.trimmingCharacters(in: .whitespacesAndNewlines), "origin/main")
        let env2 = FirstLaunch.gitEnvironment(home: NSHomeDirectory())
        func config(_ key: String) -> String {
            FirstLaunch.run(dir + "/usr/bin/git", ["-C", target.path, "config", "--get", key], environment: env2)
                .output.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        XCTAssertEqual(config("core.hooksPath"), "githooks")
        XCTAssertEqual(config("remote.origin.pushurl"), FirstLaunch.noPush)
        let push = FirstLaunch.run(dir + "/usr/bin/git", ["-C", target.path, "push", "--dry-run", "origin", "main"], environment: env2)
        XCTAssertNotEqual(push.status, 0, "a downloaded copy can't push to origin")
        let leftovers = try FileManager.default.contentsOfDirectory(atPath: parent.path)
        XCTAssertEqual(leftovers, ["Claude OS"], "the staging folder is gone")
        XCTAssertNotNil(FirstLaunch.download(commit: commit, git: dir + "/usr/bin/git", target: target, home: NSHomeDirectory()),
                        "a folder that's already there is never replaced")
        let bogus = String(repeating: "0", count: 40)
        let other = parent.appendingPathComponent("Other")
        XCTAssertNotNil(FirstLaunch.download(commit: bogus, git: dir + "/usr/bin/git", target: other, home: NSHomeDirectory()))
        XCTAssertFalse(FileManager.default.fileExists(atPath: other.path), "a failed download leaves nothing behind")
    }

    /// A picture of the checklist for a human to look at: only with COS_SNAPSHOT_DIR=<folder>.
    func testSnapshotOfTheChecklist() throws {
        guard let dir = ProcessInfo.processInfo.environment["COS_SNAPSHOT_DIR"] else { throw XCTSkip("needs COS_SNAPSHOT_DIR") }
        let config = AppConfig(root: URL(fileURLWithPath: "/nonexistent"), path: "", version: "0.8.0", release: true,
                               commit: String(repeating: "c0", count: 20), rootProblem: "none yet", serveCommandOverride: nil)
        let setup = SetupWindowController(config: config, onReady: {})
        let appearance = try XCTUnwrap(NSAppearance(named: .aqua))
        setup.window.appearance = appearance
        setup.refresh()
        let view = try XCTUnwrap(setup.window.contentView)
        view.wantsLayer = true
        appearance.performAsCurrentDrawingAppearance { view.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor }
        setup.window.layoutIfNeeded()
        view.layoutSubtreeIfNeeded()
        let rep = try XCTUnwrap(view.bitmapImageRepForCachingDisplay(in: view.bounds))
        appearance.performAsCurrentDrawingAppearance { view.cacheDisplay(in: view.bounds, to: rep) }
        let png = try XCTUnwrap(rep.representation(using: .png, properties: [:]))
        try png.write(to: URL(fileURLWithPath: dir).appendingPathComponent("first-launch.png"))
    }
}

/// Decision 0015, step 5: Remove Claude OS is offered only for the checkout this app downloaded.
final class RemoverTests: XCTestCase {
    func testOnlyTheDownloadedCheckoutOfARelease() throws {
        let fm = FileManager.default
        let home = fm.temporaryDirectory.appendingPathComponent("cos-rm-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: home) }
        let base = home.appendingPathComponent(".claude-os")
        try fm.createDirectory(at: base.appendingPathComponent("state"), withIntermediateDirectories: true)
        let root = home.appendingPathComponent(AppConfig.installFolder, isDirectory: true)
        try fm.createDirectory(at: root.appendingPathComponent("bin"), withIntermediateDirectories: true)
        try Data().write(to: root.appendingPathComponent("bin/cos"))
        let dev = home.appendingPathComponent("dev")
        try fm.createDirectory(at: dev.appendingPathComponent("bin"), withIntermediateDirectories: true)
        try Data().write(to: dev.appendingPathComponent("bin/cos"))
        func config(release: Bool = true, root: URL = root) -> AppConfig {
            AppConfig(root: root, path: "", version: "0.8.0", release: release, commit: nil, rootProblem: nil, serveCommandOverride: nil)
        }
        func record(_ d: [String: Any]) throws {
            try JSONSerialization.data(withJSONObject: d).write(to: base.appendingPathComponent("state/install.json"))
        }
        func offered(_ c: AppConfig) -> URL? { Remover.downloadedRoot(config: c, base: base, home: home.path) }
        XCTAssertNil(offered(config()), "no record")
        try record(["kind": "download", "root": root.path])
        XCTAssertEqual(offered(config())?.path, root.path)
        XCTAssertNil(offered(config(release: false)), "someone's own build")
        XCTAssertNil(offered(config(root: dev)), "the app runs another checkout (a developer's): never that one")
        try record(["kind": "download", "root": dev.path])
        XCTAssertNil(offered(config(root: dev)), "only the folder first launch downloads into")
        try record(["kind": "clone", "root": root.path])
        XCTAssertNil(offered(config()))

        // The install folder as a link to a developer's checkout: never offered.
        try fm.removeItem(at: root)
        try fm.createSymbolicLink(at: root, withDestinationURL: dev)
        try record(["kind": "download", "root": root.path])
        XCTAssertNil(offered(config()), "a link to somewhere else")
        try fm.removeItem(at: root)
        try fm.createDirectory(at: root.appendingPathComponent("bin"), withIntermediateDirectories: true)
        try fm.createSymbolicLink(at: root.appendingPathComponent("bin/cos"), withDestinationURL: dev.appendingPathComponent("bin/cos"))
        XCTAssertNil(offered(config()), "its cos a link to somewhere else")
    }
}
