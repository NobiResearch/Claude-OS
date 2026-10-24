import XCTest
@testable import ClaudeOS

final class MusicCommandTests: XCTestCase {
    func command(_ s: String) -> MusicCommand? { MusicCommand(url: URL(string: s)!) }

    func testKnownCommands() {
        XCTAssertEqual(command("claude-os://music/pause"), .pause)
        XCTAssertEqual(command("claude-os://music/love"), .love)
        XCTAssertEqual(command("claude-os://music/play?id=1080574498"), .play(id: "1080574498"))
        XCTAssertEqual(command("claude-os://music/play-library?title=Respect&artist=Aretha%20Franklin"),
                       .playLibrary(title: "Respect", artist: "Aretha Franklin"))
    }

    func testEverythingElseIsRefused() {
        XCTAssertNil(command("claude-os://music/keystroke"))
        XCTAssertNil(command("claude-os://music/play?id=12a3"))
        XCTAssertNil(command("claude-os://music/play?id=١٢٣"), "non-ASCII digits")
        XCTAssertNil(command("claude-os://music/play"))
        XCTAssertNil(command("claude-os://music/play-library?artist=x"))
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
