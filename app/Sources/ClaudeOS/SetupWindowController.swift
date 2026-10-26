import AppKit

/// The first-launch checklist of a downloaded Claude OS.app (decision 0015, step 5): one native
/// window, nothing done before a click. The command line tools, Claude Code and Claude OS's own
/// code, each with what it's for and the one button that gets it; two opt-ins that start off.
final class SetupWindowController: NSObject, NSWindowDelegate {
    let window: NSWindow

    private let config: AppConfig
    private let home: String
    private let target: URL
    private let onReady: () -> Void
    private var tools: String?
    private var claude: String?
    private var folder: FirstLaunch.Folder = .absent
    private var working = false
    private var problem: String?
    private var poll: Timer?
    private var job: FirstLaunch.Download?
    private var downloading: DispatchGroup?

    private let toolsRow = Row(title: "Apple's command line tools")
    private let claudeRow = Row(title: "Claude Code")
    private let codeRow = Row(title: "Claude OS itself")
    private let skillsBox = NSButton(checkboxWithTitle: "Use /music, /tidy, /update and /startup in Claude Code from any folder "
                                     + "(adds the `cos` command to ~/.local/bin)", target: nil, action: nil)
    private let pulseBox = NSButton(checkboxWithTitle: "Check this Mac's vitals every 2 hours in the background (no AI, no cost)",
                                    target: nil, action: nil)
    private let moveNote = NSTextField(wrappingLabelWithString: "")
    private let openButton = NSButton(title: "Open Claude OS", target: nil, action: nil)

    init(config: AppConfig, onReady: @escaping () -> Void) {
        self.config = config
        self.home = FileManager.default.homeDirectoryForCurrentUser.path
        self.target = URL(fileURLWithPath: home + "/" + AppConfig.installFolder, isDirectory: true)
        self.onReady = onReady
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 620, height: 560),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        super.init()
        window.title = "Welcome to Claude OS"
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.contentView = layout()
        render()
        window.center()
        NotificationCenter.default.addObserver(self, selector: #selector(refresh), name: NSApplication.didBecomeActiveNotification,
                                               object: nil)
    }

    func show() {
        if !working { FirstLaunch.removeLeftovers(beside: target) }
        refresh()
        window.makeKeyAndOrderFront(nil)
    }

    var busy: Bool { working }

    /// Quitting mid-download: stop git, let the download clean up after itself, then `done`.
    func cancel(then done: @escaping () -> Void) {
        guard let job = job, let downloading = downloading else { return done() }
        job.cancel()
        downloading.notify(queue: .main, execute: done)
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool { !working }

    func windowWillClose(_ notification: Notification) {
        NSApp.terminate(nil)  // there's nothing to run until it's set up
    }

    // MARK: layout

    private func layout() -> NSView {
        let heading = NSTextField(labelWithString: "Welcome to Claude OS")
        heading.font = .systemFont(ofSize: 22, weight: .semibold)
        let intro = NSTextField(wrappingLabelWithString:
            "Claude OS needs three things on this Mac before it starts. Nothing is installed until you click, "
            + "and it never asks for Full Disk Access, Accessibility or Screen Recording.")
        intro.textColor = .secondaryLabelColor

        toolsRow.button.target = self
        toolsRow.button.action = #selector(installTools)
        claudeRow.button.target = self
        claudeRow.button.action = #selector(getClaudeCode)
        codeRow.button.target = self
        codeRow.button.action = #selector(download)

        let optional = NSTextField(labelWithString: "Optional, and off unless you tick them:")
        optional.font = .systemFont(ofSize: 13, weight: .semibold)
        for box in [skillsBox, pulseBox] { box.state = .off }

        moveNote.textColor = .systemOrange
        moveNote.isHidden = true

        let quit = NSButton(title: "Quit", target: NSApp, action: #selector(NSApplication.terminate(_:)))
        openButton.target = self
        openButton.action = #selector(open)
        openButton.keyEquivalent = "\r"
        let buttons = NSStackView(views: [NSView(), quit, openButton])
        buttons.orientation = .horizontal
        buttons.setHuggingPriority(.defaultLow, for: .horizontal)

        let stack = NSStackView(views: [heading, intro, toolsRow.view, claudeRow.view, codeRow.view,
                                        optional, skillsBox, pulseBox, moveNote, buttons])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 14
        stack.setCustomSpacing(6, after: heading)
        stack.setCustomSpacing(22, after: intro)
        stack.setCustomSpacing(24, after: codeRow.view)
        stack.setCustomSpacing(6, after: optional)
        stack.setCustomSpacing(6, after: skillsBox)
        stack.setCustomSpacing(22, after: pulseBox)
        stack.edgeInsets = NSEdgeInsets(top: 28, left: 32, bottom: 24, right: 32)
        for view in [intro, toolsRow.view, claudeRow.view, codeRow.view, moveNote, buttons] {
            view.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -64).isActive = true
        }
        stack.widthAnchor.constraint(equalToConstant: 620).isActive = true
        return stack
    }

    // MARK: state

    @objc func refresh() {
        tools = FirstLaunch.developerDir()
        claude = FirstLaunch.claudeCode(home: home)
        if !working { folder = FirstLaunch.folder(target.path) }
        if tools != nil { poll?.invalidate(); poll = nil }
        render()
    }

    private func render() {
        if let dir = tools {
            toolsRow.set(.done, "Installed (\(dir)). Claude OS runs on the git and Python that come with them.", button: nil)
        } else if poll != nil {
            toolsRow.set(.working, "Follow Apple's installer. This continues by itself when it's done.", button: nil)
        } else {
            toolsRow.set(.todo, "Claude OS runs on the git and Python that come with them. Apple installs them in a few minutes.",
                         button: "Install…")
        }

        if let path = claude {
            claudeRow.set(.done, "Found (\(tilde(path))). Claude OS talks with you through it, on your Claude plan.", button: nil)
        } else {
            claudeRow.set(.todo, "Claude OS talks with you through Claude Code, on your Claude plan. Install it from Anthropic's "
                          + "page, then come back here. The desktop works without it; the chat doesn't.", button: "Get Claude Code…")
        }

        let place = "~/" + AppConfig.installFolder
        let version = config.commit.map { String($0.prefix(7)) } ?? "?"
        switch folder {
        case _ where working:
            codeRow.set(.working, "Downloading Claude OS from \(AppConfig.repository)…", button: nil)
        case .claudeOS:
            codeRow.set(.done, "In \(place).", button: nil)
        case .other:
            codeRow.set(.blocked, "\(place) already holds something that isn't this Claude OS, so it was left alone. "
                        + "Move it somewhere else, then come back.", button: "Show in Finder")
        case .absent, .empty:
            if let problem = problem {
                codeRow.set(.blocked, problem, button: "Try Again")
            } else if !FirstLaunch.isCommit(config.commit) {
                codeRow.set(.blocked, "This copy of the app doesn't say which Claude OS it belongs to. Download Claude OS.app again.",
                            button: nil)
            } else {
                codeRow.set(.todo, "Downloads Claude OS \(version) from GitHub into \(place) (about 5 MB). "
                            + "Its Claude doesn't push to GitHub or open pull requests.", button: "Download")
            }
            codeRow.button.isEnabled = tools != nil && FirstLaunch.isCommit(config.commit)
        }
        codeRow.button.action = folder == .other ? #selector(showFolder) : #selector(download)

        let bundle = Bundle.main.bundlePath
        if FirstLaunch.translocated(bundle) || !FirstLaunch.inApplications(bundle, home: home) {
            moveNote.stringValue = "Move Claude OS to your Applications folder and open it from there: macOS runs a "
                + "downloaded app from a temporary copy until it's moved."
            moveNote.isHidden = false
        } else {
            moveNote.isHidden = true
        }

        let ready = folder == .claudeOS && !working
        openButton.isEnabled = ready
        for box in [skillsBox, pulseBox] { box.isEnabled = !working }
        fit()
    }

    /// The window as tall as what it says, its top edge where it was.
    private func fit() {
        guard let content = window.contentView else { return }
        let size = window.frameRect(forContentRect: NSRect(origin: .zero, size: content.fittingSize)).size
        var frame = window.frame
        frame.origin.y += frame.height - size.height
        frame.size = size
        window.setFrame(frame, display: window.isVisible)
    }

    // MARK: actions

    @objc private func installTools() {
        // Apple's own installer dialog: the human decides there.
        _ = FirstLaunch.run("/usr/bin/xcode-select", ["--install"], environment: ["PATH": "/usr/bin:/bin"], timeout: 10)
        poll?.invalidate()
        poll = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in self?.refresh() }
        render()
    }

    @objc private func getClaudeCode() {
        NSWorkspace.shared.open(FirstLaunch.claudeCodePage)
    }

    @objc private func showFolder() {
        NSWorkspace.shared.activateFileViewerSelecting([target])
    }

    @objc private func download() {
        guard let dir = tools, let commit = config.commit, FirstLaunch.isCommit(commit), !working,
              folder == .absent || folder == .empty else { return }
        working = true
        problem = nil
        render()
        let target = self.target, home = self.home, version = config.version, job = FirstLaunch.Download()
        let group = DispatchGroup()
        group.enter()
        self.job = job
        downloading = group
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let why = FirstLaunch.download(commit: commit, git: dir + "/usr/bin/git", target: target, home: home, job: job)
            if why == nil { FirstLaunch.recordInstall(root: target.path, commit: commit, version: version) }
            group.leave()  // the staging folder is gone by now
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.job = nil
                self.downloading = nil
                self.working = false
                self.problem = why
                if why == nil { log("downloaded Claude OS \(commit.prefix(7))") }
                self.refresh()
            }
        }
    }

    /// The opt-ins the human ticked, through `cos` itself, then the desktop.
    @objc private func open() {
        guard folder == .claudeOS, !working, tools != nil else { return }
        var steps: [[String]] = []
        if skillsBox.state == .on { steps.append(["install", "--no-daemons"]) }
        if pulseBox.state == .on { steps.append(["daemon", "install", "pulse"]) }
        guard !steps.isEmpty else { return finish() }
        working = true
        render()
        let cos = target.appendingPathComponent("bin/cos").path
        let env = ["HOME": home, "PATH": AppConfig.releasePath(home: home), "LANG": "en_US.UTF-8"]
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let failed = steps.compactMap { args -> String? in
                let r = FirstLaunch.run("/usr/bin/python3", [cos] + args, environment: env, timeout: 60)
                return r.status == 0 ? nil : "cos \(args.joined(separator: " ")): \((r.error + r.output).suffix(300))"
            }
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.working = false
                if !failed.isEmpty {
                    let alert = NSAlert()
                    alert.messageText = "Claude OS is ready, but an option didn't take"
                    alert.informativeText = failed.joined(separator: "\n\n") + "\n\nYou can turn it on later in Settings."
                    alert.beginSheetModal(for: self.window) { _ in self.finish() }
                } else {
                    self.finish()
                }
            }
        }
    }

    private func finish() {
        poll?.invalidate()
        NotificationCenter.default.removeObserver(self)
        window.delegate = nil  // it's done: hiding it mustn't quit
        window.orderOut(nil)
        onReady()
    }

    private func tilde(_ path: String) -> String {
        path.hasPrefix(home + "/") ? "~" + path.dropFirst(home.count) : path
    }

    // MARK: a row of the checklist

    private final class Row {
        enum State { case done, todo, working, blocked }

        let view: NSStackView
        let button = NSButton(title: "", target: nil, action: nil)
        private let icon = NSImageView()
        private let spinner = NSProgressIndicator()
        private let detail = NSTextField(wrappingLabelWithString: "")

        init(title: String) {
            let name = NSTextField(labelWithString: title)
            name.font = .systemFont(ofSize: 14, weight: .semibold)
            detail.textColor = .secondaryLabelColor
            detail.font = .systemFont(ofSize: 12)
            let text = NSStackView(views: [name, detail])
            text.orientation = .vertical
            text.alignment = .leading
            text.spacing = 3
            text.setContentHuggingPriority(.defaultLow, for: .horizontal)
            detail.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
            spinner.style = .spinning
            spinner.controlSize = .small
            spinner.isDisplayedWhenStopped = false
            icon.symbolConfiguration = .init(pointSize: 18, weight: .regular)
            for v in [icon, spinner] as [NSView] {
                v.widthAnchor.constraint(equalToConstant: 22).isActive = true
            }
            button.bezelStyle = .rounded
            button.setContentHuggingPriority(.required, for: .horizontal)
            button.setContentCompressionResistancePriority(.required, for: .horizontal)
            view = NSStackView(views: [icon, spinner, text, button])
            view.orientation = .horizontal
            view.alignment = .top
            view.spacing = 10
        }

        func set(_ state: State, _ text: String, button title: String?) {
            detail.stringValue = text
            let (symbol, color): (String, NSColor) = {
                switch state {
                case .done: return ("checkmark.circle.fill", .systemGreen)
                case .todo: return ("circle", .tertiaryLabelColor)
                case .working: return ("circle.dotted", .secondaryLabelColor)
                case .blocked: return ("exclamationmark.triangle.fill", .systemOrange)
                }
            }()
            icon.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
            icon.contentTintColor = color
            icon.isHidden = state == .working
            if state == .working { spinner.startAnimation(nil) } else { spinner.stopAnimation(nil) }
            spinner.isHidden = state != .working
            button.title = title ?? ""
            button.isHidden = title == nil
            button.isEnabled = true
        }
    }
}
