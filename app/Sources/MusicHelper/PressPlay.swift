import ApplicationServices
import Foundation

/// `press-play`: starts the album or song page Music is showing by pressing Music's own
/// controls through the accessibility API. Elements are found by AXIdentifier, role and
/// structure only, never by their labels (which are localized), and only a fixed kind of
/// control is ever pressed. Strategies, in order:
///
///   identifier    an AXButton whose AXIdentifier contains "play" (not "playlist",
///                 "display", "play next", …), outside the transport controls (any
///                 AXToolbar, transport-like identifiers, and the window's top band, where
///                 Music's toolbar sits) and outside track rows: the page's own Play button.
///   selected-row  the selected row of the content area's track list (the widest
///                 AXTable/AXOutline with a selection, so not the sidebar): AXPress on the
///                 row, else on its first descendant that supports AXPress and is either
///                 a play-identified button or not a button at all. Other buttons in a row
///                 (download, love, add, "…") are never pressed.
///   none          nothing suitable was found, and nothing was pressed.
///
/// If Music doesn't confirm a press in time, it stops there rather than trying the next
/// strategy, so a slow Music never gets pressed twice.
struct PlayPresser {
    static let maxDepth = 20
    static let maxNodes = 6000
    static let timeBudget: TimeInterval = 15

    /// Identifier fragments marking the transport controls, the mini player and the queue.
    /// Subtrees under these (and under any AXToolbar) are skipped.
    static let transportMarks = ["transport", "playback", "nowplaying", "now-playing", "now_playing",
                                 "miniplayer", "mini-player", "upnext", "up-next", "queue", "toolbar"]
    /// Identifiers that contain "play" without being a play button.
    static let notPlayMarks = ["playlist", "display", "playnext", "play-next", "play_next", "playlater",
                               "play-later", "play_later", "autoplay", "replay", "playback", "playpause",
                               "play-pause", "play_pause", "player", "shuffle"]
    static let sidebarMarks = ["sidebar", "source"]
    /// Buttons centred this close to the window's top edge are in the title bar/toolbar.
    static let toolbarBand: Double = 60
    /// Roles never pressed inside a row: they open menus, toggle state or take text.
    static let rowSkipRoles: Set<String> = ["AXMenuButton", "AXPopUpButton", "AXCheckBox", "AXRadioButton",
                                            "AXDisclosureTriangle", "AXTextField", "AXTextArea", "AXLink",
                                            "AXSlider", "AXIncrementor", "AXComboBox", "AXMenu", "AXMenuItem"]

    struct Outcome {
        var ok: Bool
        var strategy: String
        var detail: String
        var json: [String: Any] { ["ok": ok, "trusted": true, "strategy": strategy, "detail": detail] }
    }

    private struct Candidate {
        let element: Element
        let role: String
        let identifier: String
        let width: Double
        var midY: Double? = nil
    }

    private var buttons: [Candidate] = []
    private var lists: [Candidate] = []
    private var visited = 0
    private var truncated = false
    private let deadline = Date().addingTimeInterval(timeBudget)

    static func isPlayIdentifier(_ id: String) -> Bool {
        let s = id.lowercased()
        return s.contains("play") && !notPlayMarks.contains { s.contains($0) }
    }

    private static func marked(_ id: String, _ marks: [String]) -> Bool {
        let s = id.lowercased()
        return marks.contains { s.contains($0) }
    }

    static func run(music: Element) -> Outcome {
        guard let window = mainWindow(of: music) else {
            return Outcome(ok: false, strategy: "none", detail: "Music has no window open")
        }
        var presser = PlayPresser()
        presser.walk(window, depth: 0, inRow: false)
        var tried: [String] = []

        // (a) the page's own play button
        let top = axPoint(window.attribute("AXPosition")).map { Double($0.y) }
        let buttons = presser.buttons.filter { c in
            guard let top = top, let mid = c.midY else { return true }
            return mid - top >= Self.toolbarBand
        }
        if buttons.count < presser.buttons.count {
            tried.append("skipped \(presser.buttons.count - buttons.count) play-identified button(s) in the toolbar band")
        }
        for c in buttons.prefix(3) {
            guard c.element.actions().contains("AXPress") else { continue }
            let err = c.element.perform("AXPress")
            let what = "AXPress on AXButton \(c.identifier)"
            if err == .success { return Outcome(ok: true, strategy: "identifier", detail: what) }
            if err == .cannotComplete { return unconfirmed("identifier", what) }
            tried.append("\(what): \(AX.describe(err))")
        }

        // (b) the selected track row
        switch presser.pressSelectedRow() {
        case .pressed(let what):
            return Outcome(ok: true, strategy: "selected-row", detail: what)
        case .unconfirmed(let what):
            return unconfirmed("selected-row", what)
        case .failed(let why):
            tried.append(why)
        }

        // (c) give up
        var detail = "no usable play-identified button and no pressable selected track row"
        if !tried.isEmpty { detail += "; tried: " + tried.joined(separator: "; ") }
        if presser.truncated { detail += "; the window was only partly searched" }
        return Outcome(ok: false, strategy: "none", detail: detail)
    }

    private static func unconfirmed(_ strategy: String, _ what: String) -> Outcome {
        Outcome(ok: false, strategy: strategy,
                detail: "\(what): \(AX.describe(.cannotComplete)), so it may or may not have pressed; check what's playing")
    }

    private static func mainWindow(of music: Element) -> Element? {
        if let w = axElement(music.attribute("AXMainWindow")) { return w }
        if let w = axElement(music.attribute("AXFocusedWindow")) { return w }
        let windows = axElements(music.attribute("AXWindows"))
        return windows.first { axString($0.attribute("AXSubrole")) == "AXStandardWindow" } ?? windows.first
    }

    // MARK: finding candidates

    private mutating func walk(_ el: Element, depth: Int, inRow: Bool) {
        guard depth <= Self.maxDepth, visited < Self.maxNodes, Date() < deadline else { truncated = true; return }
        visited += 1
        let a = el.attributes(["AXRole", "AXIdentifier", "AXEnabled", "AXPosition", "AXSize", "AXChildren"])
        let role = axString(a["AXRole"]) ?? ""
        let id = axString(a["AXIdentifier"]) ?? ""
        if role == "AXToolbar" || Self.marked(id, Self.transportMarks) { return }

        let size = axSize(a["AXSize"])
        let width = Double(size?.width ?? 0)
        let enabled = axBool(a["AXEnabled"]) ?? true
        if role == "AXButton" && !inRow && enabled && Self.isPlayIdentifier(id) {
            let midY = axPoint(a["AXPosition"]).flatMap { p in size.map { Double(p.y + $0.height / 2) } }
            buttons.append(Candidate(element: el, role: role, identifier: id, width: width, midY: midY))
        } else if (role == "AXTable" || role == "AXOutline") && !Self.marked(id, Self.sidebarMarks) {
            lists.append(Candidate(element: el, role: role, identifier: id, width: width))
        }

        let rowHere = inRow || role == "AXRow"
        for kid in axElements(a["AXChildren"]) {
            walk(kid, depth: depth + 1, inRow: rowHere)
        }
    }

    // MARK: the selected row

    private enum RowResult {
        case pressed(String)
        case unconfirmed(String)
        case failed(String)
    }

    private func pressSelectedRow() -> RowResult {
        // The widest list with a selection is the content area; the sidebar is narrow.
        var best: (list: Candidate, row: Element)?
        for list in lists {
            guard let row = Self.selectedRow(of: list.element) else { continue }
            if best == nil || list.width > best!.list.width { best = (list, row) }
        }
        guard let (list, row) = best else { return .failed("no track list has a selected row") }
        let listName = list.role + (list.identifier.isEmpty ? "" : " \(list.identifier)")

        if row.actions().contains("AXPress") {
            return press(row, "AXPress on the selected AXRow of \(listName)")
        }
        guard let target = Self.pressableDescendant(of: row) else {
            return .failed("the selected AXRow of \(listName) has nothing pressable")
        }
        return press(target.element, "AXPress on \(target.role)\(target.identifier.isEmpty ? "" : " \(target.identifier)") "
                     + "in the selected AXRow of \(listName)")
    }

    private func press(_ el: Element, _ what: String) -> RowResult {
        let err = el.perform("AXPress")
        if err == .success { return .pressed(what) }
        if err == .cannotComplete { return .unconfirmed(what) }
        return .failed("\(what): \(AX.describe(err))")
    }

    private static func selectedRow(of list: Element) -> Element? {
        if let row = axElements(list.attribute("AXSelectedRows")).first { return row }
        for row in axElements(list.attribute("AXChildren")).prefix(500) {
            let a = row.attributes(["AXRole", "AXSelected"])
            if axString(a["AXRole"]) == "AXRow" && axBool(a["AXSelected"]) == true { return row }
        }
        return nil
    }

    /// Breadth-first through the row (three levels, 200 elements): a play-identified button
    /// wins; otherwise the first non-button element that supports AXPress.
    private static func pressableDescendant(of row: Element) -> Candidate? {
        var level = row.children
        var seen = 0
        var fallback: Candidate?
        for _ in 0..<3 {
            var next: [Element] = []
            for el in level {
                seen += 1
                if seen > 200 { return fallback }
                let a = el.attributes(["AXRole", "AXIdentifier", "AXChildren"])
                let role = axString(a["AXRole"]) ?? ""
                let id = axString(a["AXIdentifier"]) ?? ""
                next.append(contentsOf: axElements(a["AXChildren"]))
                if rowSkipRoles.contains(role) { continue }
                let isPlayButton = role == "AXButton" && isPlayIdentifier(id)
                guard isPlayButton || (role != "AXButton" && fallback == nil) else { continue }
                guard el.actions().contains("AXPress") else { continue }
                let c = Candidate(element: el, role: role, identifier: id, width: 0)
                if isPlayButton { return c }
                fallback = c
            }
            level = next
        }
        return fallback
    }
}
