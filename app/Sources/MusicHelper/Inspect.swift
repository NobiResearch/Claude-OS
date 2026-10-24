import ApplicationServices
import Foundation

/// `inspect`: Music's windows as a JSON tree, for finding stable, language-independent
/// handles (AXIdentifier, roles, structure) to build `press-play` on. Each node has `role`,
/// `actions` and `children`, plus `subrole`, `identifier`, `title`, `description`, `value`
/// (cut to 80 characters), `selected`, `enabled` and `frame` ([x, y, w, h]) when the
/// element has them. `more: n` means n children were cut off by the limits.
///
/// The dump shows what Music shows, library and song names included, so it's private: it
/// belongs in ~/.claude-os or a temp file, never in the repository.
struct Inspector {
    static let maxDepth = 14
    static let maxNodes = 4000
    static let timeBudget: TimeInterval = 25

    private static let attributeNames = ["AXRole", "AXSubrole", "AXIdentifier", "AXTitle", "AXDescription", "AXValue",
                                         "AXSelected", "AXEnabled", "AXPosition", "AXSize", "AXChildren"]

    private(set) var nodes = 0
    private(set) var truncated = false
    private let deadline = Date().addingTimeInterval(timeBudget)

    static func run(music: Element) -> [String: Any] {
        var inspector = Inspector()
        let main = axElement(music.attribute("AXMainWindow"))
        var windows: [[String: Any]] = []
        for window in axElements(music.attribute("AXWindows")) {
            guard inspector.hasBudget else { inspector.truncated = true; break }
            var node = inspector.dump(window, depth: 0)
            if let main = main, CFEqual(main.ref, window.ref) { node["main"] = true }
            windows.append(node)
        }
        return ["trusted": true, "running": true, "windows": windows,
                "nodes": inspector.nodes, "truncated": inspector.truncated]
    }

    private var hasBudget: Bool { nodes < Self.maxNodes && Date() < deadline }

    private mutating func dump(_ el: Element, depth: Int) -> [String: Any] {
        nodes += 1
        let a = el.attributes(Self.attributeNames)
        var node: [String: Any] = ["role": axString(a["AXRole"]) ?? "?"]
        for (key, attr) in [("subrole", "AXSubrole"), ("identifier", "AXIdentifier")] {
            if let s = axString(a[attr]), !s.isEmpty { node[key] = s }
        }
        for (key, attr) in [("title", "AXTitle"), ("description", "AXDescription")] {
            if let s = axString(a[attr]), !s.isEmpty { node[key] = truncate(s, 200) }
        }
        if let v = axJSONValue(a["AXValue"], limit: 80) { node["value"] = v }
        if let b = axBool(a["AXSelected"]) { node["selected"] = b }
        if let b = axBool(a["AXEnabled"]) { node["enabled"] = b }
        if let f = axFrame(position: a["AXPosition"], size: a["AXSize"]) { node["frame"] = f }
        node["actions"] = el.actions()

        let kids = axElements(a["AXChildren"])
        var children: [[String: Any]] = []
        if depth < Self.maxDepth {
            for kid in kids {
                guard hasBudget else { break }
                children.append(dump(kid, depth: depth + 1))
            }
        }
        if children.count < kids.count {
            truncated = true
            node["more"] = kids.count - children.count
        }
        node["children"] = children
        return node
    }
}
