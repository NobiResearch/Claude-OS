// Claude OS Music Helper: the one small app that holds an Accessibility grant, so that
// Claude OS.app (and every Claude session it spawns) never needs one. Launched with
// `open`, it's its own responsible process, so macOS charges the grant to it alone.
//
//   open -n -g -W --stdout <out> --stderr <err> "<…>/Claude OS Music Helper.app" --args <command>
//
// It takes exactly one fixed command, prints exactly one JSON line on stdout and exits
// (0 on success, 1 on failure). Diagnostics go to stderr. It never activates itself or
// Music, never synthesizes keystrokes, and takes no free-form input.
//
//   status       {"trusted": bool}                                     always exit 0
//   request      shows macOS's Accessibility prompt, then {"trusted": bool}, exit 0
//   inspect      Music's windows as an accessibility tree (see Inspect.swift);
//                {"trusted": false} / {"trusted": true, "running": false} exit 1
//   press-play   {"ok": bool, "trusted": bool, "strategy": "identifier" | "selected-row" | "none",
//                 "detail": "…"} (see PressPlay.swift); exit 0 iff ok
//
// Anything else, or a run that takes longer than 40 s, prints {"ok": false, "error": "…"}
// and exits 1.
import Foundation

enum Output {
    private static let lock = NSLock()
    private static var written = false

    /// Writes `object` as the single JSON line on stdout. Returns false (and writes
    /// nothing) if a line was already written.
    @discardableResult
    static func emit(_ object: [String: Any]) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard !written else { return false }
        written = true
        var data = Data(#"{"ok":false,"error":"couldn't encode the result"}"#.utf8)
        if JSONSerialization.isValidJSONObject(object),
           let encoded = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) {
            data = encoded
        }
        data.append(UInt8(ascii: "\n"))
        FileHandle.standardOutput.write(data)
        return true
    }

    /// `open -W` looks the process up just after launching it; one that has already exited
    /// makes it print "Unable to block on application" (the output is complete anyway).
    /// Lingering a moment lets it block and return normally.
    static func finish(_ object: [String: Any], ok: Bool) -> Never {
        emit(object)
        usleep(100_000)
        exit(ok ? 0 : 1)
    }
}

func log(_ message: String) {
    FileHandle.standardError.write(Data("ClaudeOSMusicHelper: \(message)\n".utf8))
}

enum Command: String {
    case status, request, inspect
    case pressPlay = "press-play"
}

// LaunchServices may add a process serial number argument on older systems.
let args = CommandLine.arguments.dropFirst().filter { !$0.hasPrefix("-psn_") }
guard args.count == 1, let command = Command(rawValue: args[args.startIndex]) else {
    log("expected exactly one command")
    Output.finish(["ok": false, "error": "usage: status | request | inspect | press-play"], ok: false)
}

// Whatever happens (a wedged Music, a stuck accessibility call), answer and exit.
let watchdog = DispatchSource.makeTimerSource(queue: .global())
watchdog.schedule(deadline: .now() + 40)
watchdog.setEventHandler {
    if Output.emit(["ok": false, "error": "timed out"]) { _exit(1) }
}
watchdog.resume()

AX.applyTimeout()

switch command {
case .status:
    Output.finish(["trusted": AX.isTrusted], ok: true)

case .request:
    Output.finish(["trusted": AX.requestTrust()], ok: true)

case .inspect:
    guard AX.isTrusted else { Output.finish(["trusted": false], ok: false) }
    guard let music = AX.music() else { Output.finish(["trusted": true, "running": false], ok: false) }
    Output.finish(Inspector.run(music: music), ok: true)

case .pressPlay:
    guard AX.isTrusted else {
        Output.finish(["ok": false, "trusted": false, "strategy": "none",
                       "detail": "Claude OS Music Helper isn't allowed to use accessibility"], ok: false)
    }
    guard let music = AX.music() else {
        Output.finish(["ok": false, "trusted": true, "strategy": "none", "detail": "Music isn't running"], ok: false)
    }
    let outcome = PlayPresser.run(music: music)
    Output.finish(outcome.json, ok: outcome.ok)
}
