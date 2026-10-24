import AppKit
import Carbon

final class AppDelegate: NSObject, NSApplicationDelegate, ServerControllerDelegate {
    private var config: AppConfig!
    private var server: ServerController!
    private var windowController: MainWindowController!
    private var statusController: StatusItemController!
    private var hotKey: HotKey?
    private var sigtermSource: DispatchSourceSignal?
    /// When we last restarted a crashed server. One automatic restart is allowed; a second
    /// crash within `restartWindow` shows an alert instead.
    private var restartedAt: Date?
    private static let restartWindow: TimeInterval = 300

    /// Posting this distributed notification summons the desktop, like the hotkey. It
    /// carries no data, needs no permission, and lets `cos` (or a test) summon the app:
    ///   osascript -l JavaScript -e 'ObjC.import("Foundation"); $.NSDistributedNotificationCenter.defaultCenter
    ///     .postNotificationNameObjectUserInfoDeliverImmediately("local.claude-os.desktop.summon", $(), $(), true)'
    static let summonNotification = Notification.Name("local.claude-os.desktop.summon")

    func applicationDidFinishLaunching(_ notification: Notification) {
        config = AppConfig.load()
        NSApp.mainMenu = MainMenu.build(appName: "Claude OS", target: self)

        windowController = MainWindowController(config: config)
        statusController = StatusItemController(
            onOpen: { [weak self] in self?.openMainWindow(nil) },
            onAsk: { [weak self] in self?.summon() }
        )
        server = ServerController(config: config)
        server.delegate = self

        // ⌃⌥Space
        hotKey = HotKey(keyCode: kVK_Space, modifiers: controlKey | optionKey) { [weak self] in self?.summon() }
        if hotKey == nil { log("couldn't register ⌃⌥Space (another app may own it)") }

        DistributedNotificationCenter.default().addObserver(
            self, selector: #selector(summonRequested(_:)), name: Self.summonNotification,
            object: nil, suspensionBehavior: .deliverImmediately)

        // `kill <pid>` quits cleanly (and stops the server) instead of dying mid-flight.
        signal(SIGTERM, SIG_IGN)
        let src = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        src.setEventHandler { NSApp.terminate(nil) }
        src.resume()
        sigtermSource = src

        windowController.show()
        activate()
        startServer()
    }

    func applicationWillTerminate(_ notification: Notification) {
        server?.stop()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// claude-os://music/… commands for the built-in Apple Music player.
    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls {
            Task { @MainActor in Player.shared.handle(url) }
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        windowController.show()
        return true
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { true }

    // MARK: actions

    @objc func openMainWindow(_ sender: Any?) {
        activate()
        windowController.show()
    }

    @objc func reload(_ sender: Any?) {
        windowController.reload()
        statusController.refresh()
    }

    @objc private func summonRequested(_ note: Notification) {
        summon()
    }

    /// Hotkey and "Ask Claude…": bring the desktop forward and open its prompt.
    func summon() {
        activate()
        windowController.summon()
    }

    private func activate() {
        if #available(macOS 14.0, *) {
            NSApp.activate()
        } else {
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    // MARK: server lifecycle

    private func startServer() {
        statusController.endpoint = nil
        server.start { [weak self] result in
            guard let self = self else { return }
            switch result {
            case .success(let ep):
                self.windowController.load(ep)
                self.statusController.endpoint = ep
            case .failure(let failure):
                self.showServerAlert(title: "Claude OS couldn't start its server",
                                     summary: failure.summary, stderr: failure.stderr)
            }
        }
    }

    func serverDidExitUnexpectedly(status: Int32, stderr: String) {
        statusController.endpoint = nil
        windowController.serverWentAway()
        if let last = restartedAt, Date().timeIntervalSince(last) < Self.restartWindow {
            showServerAlert(title: "The Claude OS server stopped",
                            summary: "It exited (status \(status)) again soon after being restarted.",
                            stderr: stderr)
            return
        }
        log("server died unexpectedly; restarting it once")
        restartedAt = Date()
        startServer()
    }

    private func showServerAlert(title: String, summary: String, stderr: String) {
        activate()
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = title
        alert.informativeText = summary + (stderr.isEmpty ? "" : "\n\nThe server said:")
        if !stderr.isEmpty {
            alert.accessoryView = Self.scrollingText(String(stderr.suffix(6000)))
        }
        alert.addButton(withTitle: "Try Again")
        alert.addButton(withTitle: "Quit Claude OS")
        if alert.runModal() == .alertFirstButtonReturn {
            restartedAt = nil
            startServer()
        } else {
            NSApp.terminate(nil)
        }
    }

    private static func scrollingText(_ text: String) -> NSView {
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 480, height: 180))
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        let tv = NSTextView(frame: scroll.bounds)
        tv.isEditable = false
        tv.isSelectable = true
        tv.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        tv.string = text
        tv.autoresizingMask = [.width]
        tv.textContainerInset = NSSize(width: 4, height: 4)
        scroll.documentView = tv
        tv.scrollToEndOfDocument(nil)
        return scroll
    }
}
