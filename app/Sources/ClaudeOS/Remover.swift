import AppKit

/// Remove Claude OS (decision 0015, step 5): a downloaded copy undoes only what it added. Its
/// background jobs and links go through `cos uninstall` (which leaves another checkout's alone),
/// its code goes to the Trash, and ~/.claude-os, with the journal and memory, goes to the Trash
/// only after its own yes. Anything that fails stops it with everything left in place, so it can
/// be tried again.
enum Remover {
    /// The checkout this app downloaded, if ~/.claude-os/state/install.json says so: only the
    /// folder first launch downloads into, and only when it's a real folder, never a link to
    /// somewhere else (a developer's checkout).
    static func downloadedRoot(config: AppConfig, base: URL = AppURL.base,
                               home: String = FileManager.default.homeDirectoryForCurrentUser.path) -> URL? {
        let install = URL(fileURLWithPath: home + "/" + AppConfig.installFolder, isDirectory: true)
        guard config.release, let data = try? Data(contentsOf: base.appendingPathComponent("state/install.json")),
              let record = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              record["kind"] as? String == "download", record["root"] as? String == install.path,
              !isLink(install), !isLink(install.appendingPathComponent("bin/cos")),
              sameFolder(install, config.root)
        else { return nil }
        return install
    }

    static func isLink(_ url: URL) -> Bool {
        (try? FileManager.default.attributesOfItem(atPath: url.path))?[.type] as? FileAttributeType == .typeSymbolicLink
    }

    /// The same folder on disk, however its path is spelled (macOS ignores a path's case).
    static func sameFolder(_ a: URL, _ b: URL) -> Bool {
        let key: Set<URLResourceKey> = [.fileResourceIdentifierKey]
        guard let x = try? a.resourceValues(forKeys: key).fileResourceIdentifier,
              let y = try? b.resourceValues(forKeys: key).fileResourceIdentifier else { return false }
        return x.isEqual(y)
    }

    /// Asks, then removes. `stopServer` runs before anything is touched.
    static func run(config: AppConfig, stopServer: () -> Void) {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        guard let root = downloadedRoot(config: config, home: home) else { return }
        let place = "~/" + AppConfig.installFolder
        let ask = NSAlert()
        ask.messageText = "Remove Claude OS from this Mac?"
        ask.informativeText = "This turns off Claude OS's background jobs, removes the links it added for Claude Code, "
            + "and moves its code (\(place)) to the Trash. Your journal and memory stay unless you choose to remove "
            + "them next."
        ask.alertStyle = .warning
        ask.addButton(withTitle: "Remove").hasDestructiveAction = true
        ask.addButton(withTitle: "Cancel")
        guard ask.runModal() == .alertFirstButtonReturn else { return }

        stopServer()
        let env = ["HOME": home, "PATH": AppConfig.releasePath(home: home), "LANG": "en_US.UTF-8",
                   "CLAUDE_OS_HOME": AppURL.base.path]
        let r = FirstLaunch.run("/usr/bin/python3", [root.appendingPathComponent("bin/cos").path, "uninstall"],
                                environment: env, timeout: 60)
        if r.status != 0 {
            return stop("Claude OS couldn't turn off its background jobs and links, so nothing was moved to the Trash. "
                        + "Open Claude OS and try again.\n\n\((r.error + r.output).suffix(400))")
        }
        do {
            try FileManager.default.trashItem(at: root, resultingItemURL: nil)
        } catch {
            return stop("Claude OS's background jobs and links are off, but \(place) couldn't be moved to the Trash: "
                        + "\(error.localizedDescription)\n\nMove it to the Trash yourself, or open Claude OS and try again.")
        }
        try? FileManager.default.removeItem(at: AppURL.base.appendingPathComponent("state/install.json"))

        // The journal and memory: only the usual ~/.claude-os, and only on its own yes, last of all.
        var trashData = false
        if AppURL.base.standardizedFileURL.path == home + "/.claude-os" {
            let data = NSAlert()
            data.messageText = "Also move your Claude OS journal and memory to the Trash?"
            data.informativeText = "~/.claude-os holds Claude OS's journal, what it learned about you, and its settings. "
                + "Keep them if you might come back. Your conversations with Claude stay in Claude Code's own "
                + "history (~/.claude/projects) either way."
            data.addButton(withTitle: "Keep Them")
            data.addButton(withTitle: "Move to Trash").hasDestructiveAction = true
            trashData = data.runModal() == .alertSecondButtonReturn
        }
        let done = NSAlert()
        done.messageText = "Claude OS is removed"
        done.informativeText = (trashData ? "Its journal and memory go to the Trash as it quits. " : "")
            + "To finish, drag Claude OS.app to the Trash."
        done.addButton(withTitle: "Quit")
        done.runModal()
        if trashData {
            do {
                try FileManager.default.trashItem(at: AppURL.base, resultingItemURL: nil)
            } catch {
                log("couldn't move ~/.claude-os to the Trash: \(error.localizedDescription)")
            }
        }
        NSApp.terminate(nil)
    }

    /// Something failed: say what, leave everything as it is, and quit (the server is stopped).
    private static func stop(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Claude OS wasn't removed"
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.addButton(withTitle: "Quit")
        alert.runModal()
        NSApp.terminate(nil)
    }
}
