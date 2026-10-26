import AppKit
import Carbon

final class AppDelegate: NSObject, NSApplicationDelegate, ServerControllerDelegate {
    private var config: AppConfig!
    private var server: ServerController!
    private var windowController: MainWindowController!
    private var statusController: StatusItemController!
    private var hotKey: HotKey?
    private var setup: SetupWindowController?
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
        _ = AppURL.nonce  // write this launch's link nonce before any claude-os:// link is handled
        Task { @MainActor in Agenda.shared.start() }  // only reads if the human connected it before
        Task { @MainActor [weak self] in
            Notifier.shared.onOpen = { target in self?.openFromNotification(target) }
            Notifier.shared.start()
        }
        config = AppConfig.load()
        config.record()  // so `cos` reaches this copy of the app (state/app.json)
        NSApp.mainMenu = MainMenu.build(appName: "Claude OS", target: self)

        if config.release && config.rootProblem != nil {
            // A downloaded app with no Claude OS on this Mac yet: the first-launch checklist.
            let setup = SetupWindowController(config: config) { [weak self] in self?.setupFinished() }
            self.setup = setup
            setup.show()
            activate()
            return
        }
        startDesktop()
    }

    private func setupFinished() {
        setup = nil
        config = AppConfig.load()
        config.record()
        startDesktop()
    }

    private func startDesktop() {
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

    /// Quitting while the first launch downloads Claude OS: stop the download, which removes
    /// its half-finished copy, then quit.
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let setup = setup, setup.busy else { return .terminateNow }
        setup.cancel { NSApp.reply(toApplicationShouldTerminate: true) }
        return .terminateLater
    }

    func applicationWillTerminate(_ notification: Notification) {
        server?.stop()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// claude-os:// commands: music/… for the built-in player, calendar/… for the agenda.
    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls where url.scheme == "claude-os" {
            let trusted = AppURL.authorized(url)
            Task { @MainActor in
                switch url.host {
                case "music": Player.shared.handle(url, trusted: trusted)
                case "calendar": Agenda.shared.handle(url, trusted: trusted)
                case "notify": Notifier.shared.handle(url, trusted: trusted)
                case "confirm": Confirm.handle(url, trusted: trusted)
                default: log("ignored an unknown claude-os:// link")
                }
            }
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if let setup = setup { setup.show() } else { windowController?.show() }
        return true
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { true }

    // MARK: actions

    @objc func openMainWindow(_ sender: Any?) {
        activate()
        if let setup = setup { setup.show() } else { windowController?.show() }
    }

    @objc func reload(_ sender: Any?) {
        windowController?.reload()
        statusController?.refresh()
    }

    @objc private func summonRequested(_ note: Notification) {
        summon()
    }

    /// Hotkey and "Ask Claude…": bring the desktop forward and open its prompt.
    func summon() {
        activate()
        if let setup = setup { setup.show() } else { windowController?.summon() }
    }

    /// A click on a notification: the view it names (the board's minutes, the brief…), or
    /// the desktop's prompt when it names none.
    func openFromNotification(_ target: NotifyTarget?) {
        guard let target = target, setup == nil else { return summon() }
        activate()
        windowController?.open(target)
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
        if status == ServerController.plannedRestart {
            // The desktop's Update: only the server restarts (it catches up first), the
            // player keeps playing, and it doesn't count as a crash.
            log("server restarting to update")
            startServer()
            return
        }
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
