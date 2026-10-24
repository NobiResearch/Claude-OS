import AppKit
import ApplicationServices

/// Thin, never-throwing wrappers around the accessibility C API. Only reads
/// (AXUIElementCopy…) and AXUIElementPerformAction, each bounded by a short messaging
/// timeout, so a busy or hung Music can slow the helper down but never stop it.
enum AX {
    static let timeout: Float = 2.0
    static let musicBundleID = "com.apple.Music"

    static var isTrusted: Bool { AXIsProcessTrusted() }

    /// Asks macOS to show its own "allow accessibility" prompt (nothing happens once trusted).
    /// The key is kAXTrustedCheckOptionPrompt's value, spelled out so SDK changes to how the
    /// constant is imported can't break the build.
    static func requestTrust() -> Bool {
        AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
    }

    /// The messaging timeout for every element this process talks to.
    static func applyTimeout() {
        AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), timeout)
    }

    /// Music, if it's running. Never launches or activates it.
    static func music() -> Element? {
        let running = NSRunningApplication.runningApplications(withBundleIdentifier: musicBundleID)
        guard let app = running.first(where: { !$0.isTerminated }) else { return nil }
        let el = AXUIElementCreateApplication(app.processIdentifier)
        AXUIElementSetMessagingTimeout(el, timeout)
        return Element(el)
    }

    static func describe(_ err: AXError) -> String {
        switch err {
        case .success: return "ok"
        case .cannotComplete: return "Music didn't answer within \(Int(timeout)) s"
        case .actionUnsupported: return "the action isn't supported"
        case .invalidUIElement: return "the element went away"
        case .apiDisabled: return "accessibility access isn't granted"
        default: return "AXError \(err.rawValue)"
        }
    }
}

/// One accessibility element.
struct Element {
    let ref: AXUIElement

    init(_ ref: AXUIElement) { self.ref = ref }

    /// Fetches several attributes in one round trip. Attributes the element doesn't have
    /// (or that fail) are simply missing from the result.
    func attributes(_ names: [String]) -> [String: AnyObject] {
        var values: CFArray?
        let err = AXUIElementCopyMultipleAttributeValues(ref, names as CFArray, AXCopyMultipleAttributeOptions(rawValue: 0), &values)
        guard err == .success, let list = values as [AnyObject]?, list.count == names.count else { return [:] }
        var out: [String: AnyObject] = [:]
        for (name, value) in zip(names, list) where !isAXError(value) {
            out[name] = value
        }
        return out
    }

    func attribute(_ name: String) -> AnyObject? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(ref, name as CFString, &value) == .success else { return nil }
        return value
    }

    func actions() -> [String] {
        var names: CFArray?
        guard AXUIElementCopyActionNames(ref, &names) == .success, let list = names as? [String] else { return [] }
        return list
    }

    func perform(_ action: String) -> AXError {
        AXUIElementPerformAction(ref, action as CFString)
    }

    var children: [Element] { axElements(attribute("AXChildren")) }
}

// MARK: converting attribute values (CF types) into plain Swift values

private func isAXError(_ v: AnyObject) -> Bool {
    CFGetTypeID(v) == AXValueGetTypeID() && AXValueGetType(v as! AXValue) == .axError
}

func axString(_ v: AnyObject?) -> String? {
    guard let v = v, CFGetTypeID(v) == CFStringGetTypeID() else { return nil }
    return v as? String
}

func axBool(_ v: AnyObject?) -> Bool? {
    guard let v = v else { return nil }
    if CFGetTypeID(v) == CFBooleanGetTypeID() { return v as? Bool }
    if CFGetTypeID(v) == CFNumberGetTypeID() { return (v as? NSNumber)?.boolValue }
    return nil
}

func axElements(_ v: AnyObject?) -> [Element] {
    guard let v = v, CFGetTypeID(v) == CFArrayGetTypeID(), let list = v as? [AnyObject] else { return [] }
    return list.compactMap { CFGetTypeID($0) == AXUIElementGetTypeID() ? Element($0 as! AXUIElement) : nil }
}

func axElement(_ v: AnyObject?) -> Element? {
    guard let v = v, CFGetTypeID(v) == AXUIElementGetTypeID() else { return nil }
    return Element(v as! AXUIElement)
}

func axPoint(_ v: AnyObject?) -> CGPoint? {
    guard let v = v, CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
    var p = CGPoint.zero
    return AXValueGetValue(v as! AXValue, .cgPoint, &p) ? p : nil
}

func axSize(_ v: AnyObject?) -> CGSize? {
    guard let v = v, CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
    var s = CGSize.zero
    return AXValueGetValue(v as! AXValue, .cgSize, &s) ? s : nil
}

/// AXValue as JSON: text (cut to `limit` characters), a number or a bool. Anything else
/// (elements, ranges, …) is left out.
func axJSONValue(_ v: AnyObject?, limit: Int) -> Any? {
    guard let v = v else { return nil }
    let type = CFGetTypeID(v)
    if type == CFStringGetTypeID() { return (v as? String).map { truncate($0, limit) } }
    if type == CFAttributedStringGetTypeID() { return (v as? NSAttributedString).map { truncate($0.string, limit) } }
    if type == CFBooleanGetTypeID() { return v as? Bool }
    if type == CFNumberGetTypeID() {
        guard let n = v as? NSNumber, n.doubleValue.isFinite else { return nil }
        return n
    }
    if type == CFURLGetTypeID() { return (v as? URL).map { truncate($0.absoluteString, limit) } }
    return nil
}

func truncate(_ s: String, _ limit: Int) -> String {
    s.count <= limit ? s : String(s.prefix(limit - 1)) + "…"
}

/// [x, y, width, height] in whole points, or nil if the element has no usable frame.
func axFrame(position: AnyObject?, size: AnyObject?) -> [Int]? {
    guard let p = axPoint(position), let s = axSize(size),
          p.x.isFinite, p.y.isFinite, s.width.isFinite, s.height.isFinite else { return nil }
    return [Int(p.x.rounded()), Int(p.y.rounded()), Int(s.width.rounded()), Int(s.height.rounded())]
}
