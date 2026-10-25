import Foundation
import UserNotifications

/// Notifications with Claude OS's own name and icon (decision 0004).
///
/// Text never travels in a URL, so a web page or stray process can't make Claude OS say
/// anything: `cos` writes each notification to ~/.claude-os/state/outbox/*.json and then
/// opens claude-os://notify/flush, which carries nothing. Permission is asked only when the
/// human turns the setting on (claude-os://notify/authorize).
@MainActor
final class Notifier: NSObject, UNUserNotificationCenterDelegate {
    static let shared = Notifier()

    /// What clicking a notification does (the app delegate brings the desktop up).
    var onOpen: (() -> Void)?

    private let center = UNUserNotificationCenter.current()
    private static let maxPerFlush = 20

    private lazy var base: URL = {
        let env = ProcessInfo.processInfo.environment["CLAUDE_OS_HOME"]
        return env.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude-os")
    }()
    private var outbox: URL { base.appendingPathComponent("state/outbox") }
    private var statusURL: URL { base.appendingPathComponent("state/notify.json") }

    func start() {
        center.delegate = self
        Task { await writeStatus() }
    }

    func handle(_ url: URL, trusted: Bool) {
        Task { @MainActor in
            switch url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/")) {
            case "authorize" where trusted:  // a permission prompt: only for `cos`
                _ = try? await center.requestAuthorization(options: [.alert, .sound])
                await writeStatus()
            case "flush":
                await flush()
            default:
                break
            }
        }
    }

    private func flush() async {
        let status = await center.notificationSettings().authorizationStatus
        let files = ((try? FileManager.default.contentsOfDirectory(at: outbox, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "json" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        for file in files.prefix(Self.maxPerFlush) {
            defer { try? FileManager.default.removeItem(at: file) }
            guard status == .authorized || status == .provisional,
                  let data = try? Data(contentsOf: file),
                  let note = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
            let content = UNMutableNotificationContent()
            content.title = String((note["title"] as? String ?? "Claude OS").prefix(120))
            content.subtitle = String((note["subtitle"] as? String ?? "").prefix(120))
            content.body = String((note["body"] as? String ?? "").prefix(600))
            if note["sound"] as? Bool == true { content.sound = .default }
            let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
            try? await center.add(request)
        }
        await writeStatus()
    }

    private func writeStatus() async {
        let status = await center.notificationSettings().authorizationStatus
        let names: [UNAuthorizationStatus: String] = [.authorized: "authorized", .provisional: "authorized",
                                                     .denied: "denied", .notDetermined: "not determined"]
        let state: [String: Any] = ["ts": Date().timeIntervalSince1970, "authorization": names[status] ?? "unknown"]
        do {
            try FileManager.default.createDirectory(at: statusURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try JSONSerialization.data(withJSONObject: state, options: [.sortedKeys]).write(to: statusURL, options: .atomic)
        } catch {
            log("couldn't write notification status: \(error.localizedDescription)")
        }
    }

    // Show banners even while Claude OS is in front; a click brings the desktop up.
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification)
        async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        await MainActor.run { onOpen?() }
    }
}
