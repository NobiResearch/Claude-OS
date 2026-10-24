import EventKit
import Foundation

/// Today's calendar and reminders, read with EventKit (recurring events come out expanded)
/// and written to ~/.claude-os/state/agenda.json for `cos cal`, the desktop and the brief.
/// Nothing is read until the human clicks Connect (decision 0002): access is requested only
/// for claude-os://calendar/connect, never at launch.
///
///   claude-os://calendar/connect   ask macOS for Calendars + Reminders access, then refresh
///   claude-os://calendar/refresh   rewrite agenda.json (only if access was already granted)
@MainActor
final class Agenda {
    static let shared = Agenda()

    private let store = EKEventStore()
    private var timer: Timer?
    private var observing = false

    private lazy var stateURL: URL = {
        let env = ProcessInfo.processInfo.environment["CLAUDE_OS_HOME"]
        let base = env.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude-os")
        return base.appendingPathComponent("state/agenda.json")
    }()

    /// Called at launch: keep the agenda fresh, but only if the human connected it before.
    func start() {
        guard Self.eventsAuthorized else { return }
        begin()
    }

    func handle(_ url: URL) {
        let command = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        Task { @MainActor in
            switch command {
            case "connect":
                _ = try? await store.requestFullAccessToEvents()
                _ = try? await store.requestFullAccessToReminders()
                begin()
            case "refresh":
                await refresh()
            default:
                break
            }
        }
    }

    private func begin() {
        if !observing {
            observing = true
            NotificationCenter.default.addObserver(forName: .EKEventStoreChanged, object: store, queue: .main) { [weak self] _ in
                Task { @MainActor in await self?.refresh() }
            }
        }
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 15 * 60, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
        Task { @MainActor in await refresh() }
    }

    private static var eventsAuthorized: Bool {
        EKEventStore.authorizationStatus(for: .event) == .fullAccess
    }

    private static var remindersAuthorized: Bool {
        EKEventStore.authorizationStatus(for: .reminder) == .fullAccess
    }

    private func refresh() async {
        var state: [String: Any] = [
            "ts": Date().timeIntervalSince1970,
            "calendar": Self.describe(EKEventStore.authorizationStatus(for: .event)),
            "reminders": Self.describe(EKEventStore.authorizationStatus(for: .reminder)),
        ]
        let cal = Calendar.current
        let startOfToday = cal.startOfDay(for: Date())
        let endOfTomorrow = cal.date(byAdding: .day, value: 2, to: startOfToday)!

        if Self.eventsAuthorized {
            let predicate = store.predicateForEvents(withStart: startOfToday, end: endOfTomorrow, calendars: nil)
            state["events"] = store.events(matching: predicate)
                .filter { $0.status != .canceled }
                .sorted { $0.startDate < $1.startDate }
                .prefix(40)
                .map { e -> [String: Any] in
                    [
                        "title": e.title ?? "(no title)",
                        "start": e.startDate.timeIntervalSince1970,
                        "end": e.endDate.timeIntervalSince1970,
                        "all_day": e.isAllDay,
                        "calendar": e.calendar?.title ?? "",
                        "location": e.location ?? "",
                    ]
                }
        }
        if Self.remindersAuthorized {
            let predicate = store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: endOfTomorrow, calendars: nil)
            let reminders: [EKReminder] = await withCheckedContinuation { cont in
                store.fetchReminders(matching: predicate) { cont.resume(returning: $0 ?? []) }
            }
            state["reminders_due"] = reminders
                .compactMap { r -> [String: Any]? in
                    guard let due = r.dueDateComponents.flatMap({ cal.date(from: $0) }) else { return nil }
                    return ["title": r.title ?? "(no title)", "due": due.timeIntervalSince1970,
                            "list": r.calendar?.title ?? ""]
                }
                .sorted { ($0["due"] as? Double ?? 0) < ($1["due"] as? Double ?? 0) }
                .prefix(30)
                .map { $0 }
        }
        do {
            try FileManager.default.createDirectory(at: stateURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: state, options: [.sortedKeys])
            try data.write(to: stateURL, options: [.atomic])
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: stateURL.path)
        } catch {
            log("couldn't write the agenda: \(error.localizedDescription)")
        }
    }

    private static func describe(_ status: EKAuthorizationStatus) -> String {
        switch status {
        case .fullAccess: return "connected"
        case .writeOnly: return "write only"
        case .denied: return "denied"
        case .restricted: return "restricted"
        case .notDetermined: return "not connected"
        @unknown default: return "unknown"
        }
    }
}
