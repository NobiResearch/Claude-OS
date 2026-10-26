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
