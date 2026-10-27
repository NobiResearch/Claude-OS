import Foundation

/// Where a running `cos serve` can be reached. The token only ever travels over the
/// stdout pipe this app owns (never argv, never the environment), then into the web
/// view's URL fragment and the X-COS-Token header.
struct ServerEndpoint: Equatable {
    let port: Int
    let token: String

    var baseURL: URL { URL(string: "http://127.0.0.1:\(port)/")! }

    var desktopURL: URL {
        var c = URLComponents()
        c.scheme = "http"
        c.host = "127.0.0.1"
        c.port = port
        c.path = "/"
        c.fragment = "token=\(token)"
        return c.url!
    }

    /// Parses `COS_SERVE_READY port=<n> token=<t>`.
    static func parseReady(_ line: String) -> ServerEndpoint? {
        let parts = line.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: " ")
        guard parts.first == "COS_SERVE_READY" else { return nil }
        var kv: [String: String] = [:]
        for part in parts.dropFirst() {
            if let eq = part.firstIndex(of: "=") {
                kv[String(part[..<eq])] = String(part[part.index(after: eq)...])
            }
        }
        guard let port = kv["port"].flatMap({ Int($0) }), port > 0, port < 65536,
              let token = kv["token"], !token.isEmpty else { return nil }
        return ServerEndpoint(port: port, token: token)
    }
}

enum ServerFailure: Error {
    case launch(String)
    case exited(status: Int32, stderr: String)
    case timeout(stderr: String)

    var stderr: String {
        switch self {
        case .launch: return ""
        case .exited(_, let s), .timeout(let s): return s
        }
    }

    var summary: String {
        switch self {
        case .launch(let why): return "The server couldn't be launched: \(why)"
        case .exited(let status, _): return "The server exited with status \(status) before it was ready."
        case .timeout: return "The server didn't report ready within 15 seconds."
        }
    }
}

protocol ServerControllerDelegate: AnyObject {
    /// The server died after it had been ready (not because we stopped it).
    func serverDidExitUnexpectedly(status: Int32, stderr: String)
}

/// Runs `cos serve` as a child process. The child's stdin is a pipe we hold open for our
/// whole life: closing it (or this app dying, even by SIGKILL) makes the server exit
/// (`--exit-on-stdin-eof`). All state lives on the main thread.
final class ServerController {
    weak var delegate: ServerControllerDelegate?
    private(set) var endpoint: ServerEndpoint?

    private let config: AppConfig
    private var process: Process?
    private var stdinPipe: Pipe?
    private var stdoutBuffer = Data()
    private var stderrTail = Data()
    private var readyHandler: ((Result<ServerEndpoint, ServerFailure>) -> Void)?
    private var timeoutWork: DispatchWorkItem?
    /// Bumped on every start/stop so callbacks from an old process are ignored.
    private var generation = 0

    private static let stderrLimit = 16 * 1024

    init(config: AppConfig) {
        self.config = config
    }

    var stderrText: String {
        String(decoding: stderrTail, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// The exit status `cos serve` uses for a restart it asked for (EX_TEMPFAIL; server.RESTART).
    static let plannedRestart: Int32 = 75

    func start(timeout: TimeInterval = 15, completion: @escaping (Result<ServerEndpoint, ServerFailure>) -> Void) {
        stop()
        generation += 1
        let gen = generation
        stdoutBuffer = Data()
        stderrTail = Data()

        if let problem = config.rootProblem {
            completion(.failure(.launch(problem)))  // a release with no checkout of Ovenbird yet
            return
        }
        let p = Process()
        if let cmd = config.serveCommandOverride {
            p.executableURL = URL(fileURLWithPath: "/bin/sh")
            p.arguments = ["-c", cmd]
        } else {
            guard FileManager.default.fileExists(atPath: config.cosScript.path) else {
                completion(.failure(.launch("\(config.cosScript.path) doesn't exist. "
                    + "If the repository moved, rebuild the app with app/build.sh.")))
                return
            }
            p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            p.arguments = ["python3", config.cosScript.path, "serve", "--port", "0", "--exit-on-stdin-eof"]
        }
        p.currentDirectoryURL = config.root
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = config.path
        env["PYTHONUNBUFFERED"] = "1"
        env.removeValue(forKey: "CLAUDE_OS_SERVE_CMD")
        p.environment = env

        let inPipe = Pipe(), outPipe = Pipe(), errPipe = Pipe()
        p.standardInput = inPipe
        p.standardOutput = outPipe
        p.standardError = errPipe

        outPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            DispatchQueue.main.async { self?.handleStdout(data, gen: gen) }
        }
        errPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            DispatchQueue.main.async { self?.handleStderr(data, gen: gen) }
        }
        p.terminationHandler = { [weak self] proc in
            let status = proc.terminationStatus
            DispatchQueue.main.async { self?.handleExit(status: status, gen: gen) }
        }

        readyHandler = completion
        do {
            try p.run()
        } catch {
            readyHandler = nil
            completion(.failure(.launch(error.localizedDescription)))
            return
        }
        process = p
        stdinPipe = inPipe
        log("server starting (pid \(p.processIdentifier))")

        let work = DispatchWorkItem { [weak self] in
            guard let self = self, gen == self.generation, let handler = self.readyHandler else { return }
            let stderr = self.stderrText
            self.stop()
            handler(.failure(.timeout(stderr: stderr)))
        }
        timeoutWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + timeout, execute: work)
    }

    /// Stops the server: close its stdin (it exits on EOF), then SIGTERM, then SIGKILL.
    func stop() {
        generation += 1
        timeoutWork?.cancel()
        timeoutWork = nil
        readyHandler = nil
        endpoint = nil
        let p = process
        process = nil
        try? stdinPipe?.fileHandleForWriting.close()
        stdinPipe = nil
        guard let proc = p, proc.isRunning else { return }
        if !waitForExit(proc, seconds: 1.0) {
            proc.terminate()
            if !waitForExit(proc, seconds: 1.0) {
                kill(proc.processIdentifier, SIGKILL)
            }
        }
    }

    private func waitForExit(_ proc: Process, seconds: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while proc.isRunning && Date() < deadline { usleep(20_000) }
        return !proc.isRunning
    }

    private func handleStdout(_ data: Data, gen: Int) {
        guard gen == generation else { return }
        stdoutBuffer.append(data)
        while let nl = stdoutBuffer.firstIndex(of: UInt8(ascii: "\n")) {
            let lineData = stdoutBuffer[stdoutBuffer.startIndex..<nl]
            stdoutBuffer.removeSubrange(stdoutBuffer.startIndex...nl)
            let line = String(decoding: lineData, as: UTF8.self)
            if let ep = ServerEndpoint.parseReady(line) {
                guard endpoint == nil else { continue }
                endpoint = ep
                log("server ready on port \(ep.port)")  // never log the token
                timeoutWork?.cancel()
                timeoutWork = nil
                let handler = readyHandler
                readyHandler = nil
                handler?(.success(ep))
            } else if !line.isEmpty {
                log("server: \(line)")
            }
        }
    }

    private func handleStderr(_ data: Data, gen: Int) {
        guard gen == generation else { return }
        FileHandle.standardError.write(data)
        stderrTail.append(data)
        if stderrTail.count > Self.stderrLimit {
            stderrTail = stderrTail.suffix(Self.stderrLimit)
        }
    }

    private func handleExit(status: Int32, gen: Int) {
        guard gen == generation else { return }
        log("server exited with status \(status)")
        process = nil
        try? stdinPipe?.fileHandleForWriting.close()
        stdinPipe = nil
        let wasReady = endpoint != nil
        endpoint = nil
        timeoutWork?.cancel()
        timeoutWork = nil
        // Give the pipes a moment to drain so the alert shows the server's last words.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
            guard let self = self, gen == self.generation else { return }
            if let handler = self.readyHandler {
                self.readyHandler = nil
                handler(.failure(.exited(status: status, stderr: self.stderrText)))
            } else if wasReady {
                self.delegate?.serverDidExitUnexpectedly(status: status, stderr: self.stderrText)
            }
        }
    }
}
