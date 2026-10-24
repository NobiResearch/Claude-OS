import Carbon
import Foundation

/// A system-wide hotkey via Carbon's RegisterEventHotKey. Unlike event taps or
/// NSEvent global monitors, this needs no Accessibility or Input Monitoring permission.
final class HotKey {
    private static let signature: OSType = 0x434F_5331  // 'COS1'
    private static var nextID: UInt32 = 1

    private let id: UInt32
    private let action: () -> Void
    private var hotKeyRef: EventHotKeyRef?
    private var handlerRef: EventHandlerRef?

    /// `keyCode` is a virtual key code (e.g. kVK_Space); `modifiers` are Carbon masks
    /// (controlKey, optionKey, cmdKey, shiftKey). Returns nil if the combination is taken.
    init?(keyCode: Int, modifiers: Int, action: @escaping () -> Void) {
        self.id = HotKey.nextID
        HotKey.nextID += 1
        self.action = action

        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let me = Unmanaged.passUnretained(self).toOpaque()
        let installed = InstallEventHandler(GetApplicationEventTarget(), { _, event, userData in
            guard let event = event, let userData = userData else { return OSStatus(eventNotHandledErr) }
            var hkID = EventHotKeyID()
            let err = GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID),
                                        nil, MemoryLayout<EventHotKeyID>.size, nil, &hkID)
            let hotKey = Unmanaged<HotKey>.fromOpaque(userData).takeUnretainedValue()
            guard err == noErr, hkID.signature == HotKey.signature, hkID.id == hotKey.id else {
                return OSStatus(eventNotHandledErr)
            }
            DispatchQueue.main.async { hotKey.action() }
            return noErr
        }, 1, &spec, me, &handlerRef)
        guard installed == noErr else { return nil }

        let hkID = EventHotKeyID(signature: HotKey.signature, id: id)
        let registered = RegisterEventHotKey(UInt32(keyCode), UInt32(modifiers), hkID,
                                             GetApplicationEventTarget(), 0, &hotKeyRef)
        guard registered == noErr else {
            if let h = handlerRef { RemoveEventHandler(h) }
            handlerRef = nil
            return nil
        }
    }

    deinit {
        if let r = hotKeyRef { UnregisterEventHotKey(r) }
        if let h = handlerRef { RemoveEventHandler(h) }
    }
}
