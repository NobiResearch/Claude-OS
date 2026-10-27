import WebKit

/// What the desktop page can ask the native app for, as `window.webkit.messageHandlers.cos`.
/// Every message gets exactly one reply, and expected failures are replies too
/// (`{"error": "…"}`, plain language), so the page's `await` only throws if WebKit does.
/// Only the desktop itself is answered: the main frame of http://127.0.0.1:<server port>.
///
///   await window.webkit.messageHandlers.cos.postMessage({type: "locate"})
///     → {"lat": 48.86, "lon": 2.35, "accuracy_m": 65}  (rounded to ~1 km)
///     → {"error": "Ovenbird isn't allowed to use your location. …"}
final class WebBridge: NSObject, WKScriptMessageHandlerWithReply {
    static let name = "cos"

    /// The desktop server's port; nil while no server is up, which refuses everything.
    var port: Int?

    private let locator = Locator()

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage,
                               replyHandler: @escaping (Any?, String?) -> Void) {
        guard isFromDesktop(message) else {
            log("refused a bridge message from outside the desktop")
            replyHandler(["error": "Only the Ovenbird desktop can ask for this."], nil)
            return
        }
        switch (message.body as? [String: Any])?["type"] as? String {
        case "locate":
            locator.locate { replyHandler($0, nil) }
        default:
            replyHandler(["error": "Ovenbird doesn't know that request."], nil)
        }
    }

    private func isFromDesktop(_ message: WKScriptMessage) -> Bool {
        let origin = message.frameInfo.securityOrigin
        return Self.allows(mainFrame: message.frameInfo.isMainFrame, scheme: origin.protocol,
                           host: origin.host, port: origin.port, serverPort: port)
    }

    /// Only the desktop's own main frame: http://127.0.0.1:<the live server port>.
    static func allows(mainFrame: Bool, scheme: String, host: String, port: Int, serverPort: Int?) -> Bool {
        guard let serverPort = serverPort, mainFrame else { return false }
        return scheme == "http" && host == "127.0.0.1" && port == serverPort
    }
}
