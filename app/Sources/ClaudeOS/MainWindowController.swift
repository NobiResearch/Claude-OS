import AppKit
import WebKit

/// The main window: a native, draggable title strip over a WKWebView showing the desktop.
/// Closing it only hides it; the app keeps running in the menu bar.
final class MainWindowController: NSObject, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate {
    let window: NSWindow
    let webView: WKWebView

    private var endpoint: ServerEndpoint?
    private var pageLoaded = false
    private var pendingSummon = false
    private var loadRetries = 0

    private static let autosaveName = "ClaudeOSMainWindow"
    private static let summonJS = "window.cos && window.cos.summon && window.cos.summon(); void 0"

    init(config: AppConfig) {
        let wkConfig = WKWebViewConfiguration()
        wkConfig.websiteDataStore = .default()
        wkConfig.applicationNameForUserAgent = "ClaudeOS/\(config.version)"
        wkConfig.preferences.javaScriptCanOpenWindowsAutomatically = false

        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 1280, height: 820), configuration: wkConfig)
        webView.setValue(false, forKey: "drawsBackground")  // no white flash before the page paints
        webView.underPageBackgroundColor = Theme.background
        webView.allowsBackForwardNavigationGestures = false
        webView.allowsMagnification = true
        if #available(macOS 13.3, *) {
            webView.isInspectable = true  // Safari > Develop > Claude OS
        }

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],  // no .fullSizeContentView
            backing: .buffered,
            defer: false
        )
        window.title = "Claude OS"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.backgroundColor = Theme.background
        window.appearance = NSAppearance(named: .darkAqua)
        window.minSize = NSSize(width: 900, height: 600)
        window.isReleasedWhenClosed = false
        window.collectionBehavior.insert(.fullScreenPrimary)
        window.contentView = webView
        window.center()
        _ = window.setFrameUsingName(Self.autosaveName)
        _ = window.setFrameAutosaveName(Self.autosaveName)

        super.init()
        window.delegate = self
        webView.navigationDelegate = self
        webView.uiDelegate = self
    }

    // MARK: showing

    func show() {
        if window.isMiniaturized { window.deminiaturize(nil) }
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
        window.makeFirstResponder(webView)
    }

    /// Bring the window up and ask the desktop to open its prompt.
    func summon() {
        show()
        if pageLoaded {
            runSummon()
        } else {
            pendingSummon = true
        }
    }

    private func runSummon() {
        pendingSummon = false
        webView.evaluateJavaScript(Self.summonJS, completionHandler: nil)
    }

    // MARK: loading

    func load(_ ep: ServerEndpoint) {
        endpoint = ep
        pageLoaded = false
        loadRetries = 0
        webView.load(URLRequest(url: ep.desktopURL))
    }

    func serverWentAway() {
        endpoint = nil
        pageLoaded = false
    }

    func reload() {
        guard let ep = endpoint else { return }
        if webView.url == ep.desktopURL {
            webView.reload()
        } else {
            load(ep)
        }
    }

    // MARK: navigation policy

    /// In-app iff it's the desktop server itself; `about:` (blank/srcdoc frames) is inert.
    private func isInternal(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        if scheme == "about" { return true }
        guard scheme == "http" || scheme == "https", url.host == "127.0.0.1" else { return false }
        guard let ep = endpoint else { return true }
        return (url.port ?? (scheme == "https" ? 443 : 80)) == ep.port
    }

    /// Things we never hand to NSWorkspace: local files could launch apps or scripts.
    private func canOpenExternally(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        return !["file", "javascript", "data", "blob", "about", ""].contains(scheme)
    }

    private func openExternally(_ url: URL) {
        guard canOpenExternally(url) else {
            log("blocked navigation to a \(url.scheme ?? "schemeless") URL")
            return
        }
        NSWorkspace.shared.open(url)
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { return decisionHandler(.cancel) }
        if isInternal(url) { return decisionHandler(.allow) }
        let isMainFrame = action.targetFrame?.isMainFrame ?? true  // nil target = new window
        let scheme = url.scheme?.lowercased() ?? ""
        if !isMainFrame && (scheme == "data" || scheme == "blob") { return decisionHandler(.allow) }
        decisionHandler(.cancel)
        // Subframes that load external content on their own are just blocked; anything the
        // page or the human navigates to goes to the default browser.
        if isMainFrame || action.navigationType == .linkActivated {
            openExternally(url)
        }
    }

    // window.open and target=_blank
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url {
            if isInternal(url) && url.scheme?.lowercased() != "about" {
                webView.load(action.request)
            } else if !isInternal(url) {
                openExternally(url)
            }
        }
        return nil
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        pageLoaded = false
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pageLoaded = true
        loadRetries = 0
        if pendingSummon { runSummon() }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        let ns = error as NSError
        if ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled { return }
        if ns.domain == "WebKitErrorDomain" && ns.code == 102 { return }  // interrupted by policy change
        log("load failed: \(ns.domain) \(ns.code)")
        guard let ep = endpoint, loadRetries < 5 else { return }
        loadRetries += 1
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self = self, self.endpoint == ep else { return }
            self.webView.load(URLRequest(url: ep.desktopURL))
        }
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        log("web content process terminated; reloading")
        if let ep = endpoint { load(ep) }
    }

    // MARK: JavaScript panels and file inputs (WKWebView shows none of these by itself)

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "OK")
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Cancel")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String,
                 defaultText: String?, initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (String?) -> Void) {
        let alert = NSAlert()
        alert.messageText = prompt
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        field.stringValue = defaultText ?? ""
        alert.accessoryView = field
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Cancel")
        alert.window.initialFirstResponder = field
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }
}
