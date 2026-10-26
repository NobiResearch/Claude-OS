import AppKit

/// Remove Claude OS (decision 0015, step 5): a downloaded copy undoes only what it added. Its
/// background jobs and links go through `cos uninstall` (which leaves another checkout's alone),
/// its code goes to the Trash, and ~/.claude-os, with the journal and what Claude learned,
/// goes to the Trash only after its own yes.
enum Remover {
    /// The checkout this app downloaded, if ~/.claude-os/state/install.json says so: only that
    /// one may be removed from here.
    static func downloadedRoot(config: AppConfig, base: URL = AppURL.base) -> URL? {
        guard config.release, let data = try? Data(contentsOf: base.appendingPathComponent("state/install.json")),
              let record = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              record["kind"] as? String == "download", let root = record["root"] as? String,
              sameFolder(URL(fileURLWithPath: root), config.root)
        else { return nil }
        return config.root
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
        guard let root = downloadedRoot(config: config) else { return }
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let place = root.path.hasPrefix(home + "/") ? "~" + root.path.dropFirst(home.count) : root.path
        let ask = NSAlert()
        ask.messageText = "Remove Claude OS from this Mac?"
        ask.informativeText = "This turns off Claude OS's background jobs, removes the links it added for Claude Code, "
            + "and moves its code (\(place)) to the Trash. Your journal and what Claude learned about you stay in "
            + "~/.claude-os unless you choose to remove them next."
        ask.alertStyle = .warning
        ask.addButton(withTitle: "Remove")
        ask.addButton(withTitle: "Cancel")
        guard ask.runModal() == .alertFirstButtonReturn else { return }

        stopServer()
        var problems: [String] = []
        let r = FirstLaunch.run("/usr/bin/python3", [root.appendingPathComponent("bin/cos").path, "uninstall"],
                                environment: ["HOME": home, "PATH": AppConfig.releasePath(home: home), "LANG": "en_US.UTF-8"],
                                timeout: 60)
        if r.status != 0 { problems.append("cos uninstall: \((r.error + r.output).suffix(300))") }
        do {
            try FileManager.default.trashItem(at: root, resultingItemURL: nil)
        } catch {
            problems.append("Couldn't move \(place) to the Trash: \(error.localizedDescription)")
        }
        try? FileManager.default.removeItem(at: AppURL.base.appendingPathComponent("state/install.json"))

        let data = NSAlert()
        data.messageText = "Also move your Claude OS journal and memory to the Trash?"
        data.informativeText = "~/.claude-os holds your journal, what Claude learned about you, and Claude OS's settings. "
            + "Keep them if you might come back."
        data.addButton(withTitle: "Keep Them")
        data.addButton(withTitle: "Move to Trash")
        if data.runModal() == .alertSecondButtonReturn {
            do {
                try FileManager.default.trashItem(at: AppURL.base, resultingItemURL: nil)
            } catch {
                problems.append("Couldn't move ~/.claude-os to the Trash: \(error.localizedDescription)")
            }
        }

        let done = NSAlert()
        done.messageText = problems.isEmpty ? "Claude OS is removed" : "Claude OS is mostly removed"
        done.informativeText = (problems.isEmpty ? "" : problems.joined(separator: "\n\n") + "\n\n")
            + "To finish, drag Claude OS.app to the Trash."
        done.addButton(withTitle: "Quit")
        done.runModal()
        NSApp.terminate(nil)
    }
}
