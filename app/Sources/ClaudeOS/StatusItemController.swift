import AppKit

/// The menu bar item: the Nest and "362 GB", with the server's signals in its menu.
/// Polls GET /api/status every 60 seconds (and when the menu opens).
final class StatusItemController: NSObject, NSMenuDelegate {
    var endpoint: ServerEndpoint? {
        didSet {
            guard endpoint != oldValue else { return }
            lastStatus = nil
            refreshFailed = false
            render()
            if endpoint != nil { refresh() }
        }
    }

    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private let onOpen: () -> Void
    private let onAsk: () -> Void
    private let session: URLSession
    private var timer: Timer?
    private var lastStatus: [String: Any]?
    private var lastFetch = Date.distantPast
    private var refreshFailed = false
    private var inFlight = false

    init(onOpen: @escaping () -> Void, onAsk: @escaping () -> Void) {
        self.onOpen = onOpen
        self.onAsk = onAsk
        let cfg = URLSessionConfiguration.ephemeral
        cfg.connectionProxyDictionary = [:]  // 127.0.0.1 must never go through a proxy
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        cfg.timeoutIntervalForRequest = 30
        session = URLSession(configuration: cfg)
        super.init()

        item.button?.image = Self.nest
        item.button?.imagePosition = .imageLeading
        item.button?.toolTip = "Ovenbird"
        menu.delegate = self
        menu.autoenablesItems = false
        item.menu = menu
        render()

        let t = Timer(timeInterval: 60, repeats: true) { [weak self] _ in self?.refresh() }
        t.tolerance = 5
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func refresh() {
        guard let ep = endpoint, !inFlight else { return }
        inFlight = true
        lastFetch = Date()
        var req = URLRequest(url: ep.baseURL.appendingPathComponent("api/status"))
        req.setValue(ep.token, forHTTPHeaderField: "X-COS-Token")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        session.dataTask(with: req) { [weak self] data, response, error in
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            let json = (code == 200 ? data : nil).flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.inFlight = false
                guard self.endpoint == ep else { return }  // server restarted meanwhile
                if let json = json {
                    self.lastStatus = json
                    self.refreshFailed = false
                } else {
                    self.refreshFailed = true
                    log("status poll failed: HTTP \(code) \(error.map { ($0 as NSError).code } ?? 0)")
                }
                self.render()
            }
        }.resume()
    }

    // MARK: rendering

    /// The Nest as a template image (decision 0021): the filled dome with its doorway cut out at
    /// the base, on docs/brand's 18 pt grid. Drawn when shown, so it's sharp at 1x and 2x, and
    /// macOS tints it for a light, dark or highlighted menu bar.
    static let nest: NSImage = {
        let image = NSImage(size: NSSize(width: 18, height: 18), flipped: true) { _ in
            let path = NSBezierPath()
            path.move(to: NSPoint(x: 1, y: 16))
            path.curve(to: NSPoint(x: 9, y: 2), controlPoint1: NSPoint(x: 1, y: 7.3), controlPoint2: NSPoint(x: 3.4, y: 2))
            path.curve(to: NSPoint(x: 17, y: 16), controlPoint1: NSPoint(x: 14.6, y: 2), controlPoint2: NSPoint(x: 17, y: 7.3))
            path.close()
            path.move(to: NSPoint(x: 12, y: 8))
            path.line(to: NSPoint(x: 15, y: 12))
            path.line(to: NSPoint(x: 12, y: 16))
            path.line(to: NSPoint(x: 9, y: 12))
            path.close()
            path.windingRule = .evenOdd
            NSColor.black.setFill()
            path.fill()
            return true
        }
        image.isTemplate = true
        image.accessibilityDescription = "Ovenbird"
        return image
    }()

    private func render() {
        var title = ""
        var tip = ["Ovenbird"]
        if let s = lastStatus {
            if let free = number((s["disk"] as? [String: Any])?["free"]) {
                let gb = Self.gigabytes(free)
                title += " " + gb
                tip.append("\(gb) free")
            }
            if let pct = number((s["battery"] as? [String: Any])?["percent"]) {
                tip.append("battery \(Int(pct))%")
            }
        } else if endpoint == nil {
            tip.append("starting…")
        }
        if refreshFailed { tip.append("status unavailable") }
        item.button?.title = title
        item.button?.toolTip = tip.joined(separator: " · ")
        buildMenu()
    }

    /// Same units as `cos status` (powers of 1024, labelled GB), rounded for the menu bar.
    static func gigabytes(_ bytes: Double) -> String {
        let gb = bytes / 1_073_741_824
        return gb >= 10 ? String(format: "%.0f GB", gb) : String(format: "%.1f GB", gb)
    }

    private func number(_ v: Any?) -> Double? {
        if let n = v as? NSNumber, CFGetTypeID(n) != CFBooleanGetTypeID() { return n.doubleValue }
        return nil
    }

    private func buildMenu() {
        menu.removeAllItems()
        for line in signalLines() {
            let mi = NSMenuItem(title: line, action: nil, keyEquivalent: "")
            mi.isEnabled = false
            menu.addItem(mi)
        }
        menu.addItem(.separator())

        let open = NSMenuItem(title: "Open Ovenbird", action: #selector(openClicked), keyEquivalent: "o")
        open.keyEquivalentModifierMask = [.command]
        open.target = self
        menu.addItem(open)

        // Shows the global hotkey; the hotkey itself is registered with Carbon (HotKey.swift).
        let ask = NSMenuItem(title: "Ask Claude…", action: #selector(askClicked), keyEquivalent: " ")
        ask.keyEquivalentModifierMask = [.control, .option]
        ask.target = self
        menu.addItem(ask)

        menu.addItem(.separator())
        let quit = NSMenuItem(title: "Quit Ovenbird", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quit.keyEquivalentModifierMask = [.command]
        quit.target = NSApp
        menu.addItem(quit)
    }

    private func signalLines() -> [String] {
        guard let s = lastStatus else {
            if endpoint == nil { return ["Starting…"] }
            return [refreshFailed ? "Status unavailable" : "Checking…"]
        }
        let signals = (s["signals"] as? [[String: Any]]) ?? []
        if signals.isEmpty { return ["All quiet"] }
        return signals.map { sig in
            let msg = (sig["msg"] as? String) ?? ""
            let level = (sig["level"] as? String) ?? ""
            return (level == "warn" ? "⚠ " : "· ") + msg  // same marks as `cos status`
        }
    }

    // MARK: actions

    @objc private func openClicked() { onOpen() }
    @objc private func askClicked() { onAsk() }

    func menuWillOpen(_ menu: NSMenu) {
        if Date().timeIntervalSince(lastFetch) > 10 { refresh() }
    }
}
