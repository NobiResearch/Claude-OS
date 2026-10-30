import AppKit

/// Yes/no questions only the human can answer, asked in a native dialog (decisions 0006, 0011).
///
/// Turning Keep Ovenbird up to date on lets merged code reach this Mac by itself, so the
/// desktop page can't do it alone: code in the page could call the API, but it can't click
/// this dialog. `cos serve` opens claude-os://confirm/catch-up?rid=…&nonce=… (the nonce is this
/// launch's, which the page never sees), and the answer goes to
/// ~/.claude-os/state/confirm-catch-up.json with the request's id, a file the page can't write.
@MainActor
enum Confirm {
    private struct Question {
        let title: String
        let body: String
        let yes: String
    }

    private static let questions: [String: Question] = [
        "catch-up": Question(
            title: "Keep Ovenbird up to date?",
            body: "When a pull request is merged on GitHub, Ovenbird brings it to this Mac by itself: when the app "
                + "starts, when a terminal session starts, and in the background while the app is closed. Some of "
                + "those changes are merged by Claude on its own, without a person's review. It only moves a clean "
                + "main forward, only over GitHub's own pull request merges, and each update is in your journal "
                + "with the way back. You can turn it off any time in Settings.",
            yes: "Keep Up to Date"),
    ]

    static func handle(_ url: URL, trusted: Bool) {
        let what = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard trusted, let question = questions[what], let rid = AppURL.requestID(url) else {
            log("ignored a confirm link")
            return
        }
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = question.title
        alert.informativeText = question.body
        alert.alertStyle = .warning
        alert.addButton(withTitle: question.yes)
        alert.addButton(withTitle: "Cancel")
        let approved = alert.runModal() == .alertFirstButtonReturn
        write(what: what, rid: rid, approved: approved)
    }

    private static func write(what: String, rid: String, approved: Bool) {
        let file = AppURL.base.appendingPathComponent("state/confirm-\(what).json")
        let answer: [String: Any] = ["rid": rid, "approved": approved, "ts": Date().timeIntervalSince1970]
        do {
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: answer, options: [.sortedKeys])
            try data.write(to: file, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: file.path)
        } catch {
            log("couldn't write the answer: \(error.localizedDescription)")
        }
    }
}
