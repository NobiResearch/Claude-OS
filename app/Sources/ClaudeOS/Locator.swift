import CoreLocation

/// Finds roughly where this Mac is, for the desktop's weather. It asks macOS for Location
/// only when the page asks (never at launch: the manager isn't even created until then),
/// wants no better than kilometre accuracy, and answers with coordinates rounded to two
/// decimals (about a kilometre). Nothing is stored or logged here; the page decides what
/// to keep. All state lives on the main thread.
final class Locator: NSObject, CLLocationManagerDelegate {
    typealias Reply = ([String: Any]) -> Void

    /// How long a location fix may take once macOS allows it.
    static let fixTimeout: TimeInterval = 15
    /// How long to wait for the human to answer macOS's own permission prompt.
    static let promptTimeout: TimeInterval = 120

    private var manager: CLLocationManager?
    private var waiting: [Reply] = []
    private var timer: DispatchWorkItem?
    /// Whether this request already showed the permission prompt.
    private var asked = false
    /// A fix (or a final answer) is on its way; authorization callbacks mustn't start another.
    private var busy = false

    func locate(_ reply: @escaping Reply) {
        waiting.append(reply)
        guard waiting.count == 1 else { return }  // one request in flight answers every caller
        asked = false
        busy = false
        advance(manager ?? makeManager())
    }

    private func makeManager() -> CLLocationManager {
        let m = CLLocationManager()
        m.desiredAccuracy = kCLLocationAccuracyKilometer
        m.delegate = self
        manager = m
        return m
    }

    /// Moves the pending request along, given the current authorization.
    private func advance(_ m: CLLocationManager) {
        guard !waiting.isEmpty, !busy else { return }
        switch m.authorizationStatus {
        case .notDetermined:
            // Ask once, then wait for locationManagerDidChangeAuthorization.
            guard !asked else { return }
            asked = true
            arm(Self.promptTimeout, "There's no answer to macOS's location prompt yet.")
            m.requestWhenInUseAuthorization()
        case .restricted:
            finish(error: "Location is restricted on this Mac, for example by a management profile.")
        case .denied:
            finishDenied()
        case .authorizedAlways:  // on macOS, every grant (including "when in use") reports this
            busy = true
            arm(Self.fixTimeout, "Finding your location took too long.")
            m.requestLocation()
        @unknown default:
            finish(error: "Location isn't available on this Mac.")
        }
    }

    /// Denied can mean this app was refused or Location Services are off for the whole Mac.
    /// locationServicesEnabled() can block, so it's asked off the main thread.
    private func finishDenied() {
        busy = true
        DispatchQueue.global(qos: .userInitiated).async {
            let enabled = CLLocationManager.locationServicesEnabled()
            DispatchQueue.main.async {
                self.finish(error: enabled
                    ? "Claude OS isn't allowed to use your location. You can allow it in System Settings › "
                        + "Privacy & Security › Location Services."
                    : "Location Services are turned off. You can turn them on in System Settings › "
                        + "Privacy & Security › Location Services.")
            }
        }
    }

    private func arm(_ seconds: TimeInterval, _ message: String) {
        timer?.cancel()
        let work = DispatchWorkItem { [weak self] in
            self?.manager?.stopUpdatingLocation()  // also cancels a pending requestLocation()
            self?.finish(error: message)
        }
        timer = work
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: work)
    }

    private func finish(_ result: [String: Any]) {
        timer?.cancel()
        timer = nil
        busy = false
        let replies = waiting
        waiting = []
        replies.forEach { $0(result) }
    }

    private func finish(error: String) { finish(["error": error]) }

    private static func round2(_ x: CLLocationDegrees) -> Double { (x * 100).rounded() / 100 }

    // MARK: CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        advance(manager)
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard busy, !waiting.isEmpty,
              let loc = locations.last(where: { $0.horizontalAccuracy >= 0 && CLLocationCoordinate2DIsValid($0.coordinate) })
        else { return }
        finish([
            "lat": Self.round2(loc.coordinate.latitude),
            "lon": Self.round2(loc.coordinate.longitude),
            "accuracy_m": Int(loc.horizontalAccuracy.rounded()),
        ])
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        guard busy, !waiting.isEmpty else { return }
        switch (error as? CLError)?.code {
        case .denied?:
            finishDenied()
        case .locationUnknown?:
            finish(error: "Your Mac couldn't work out where it is right now. It finds itself from nearby "
                + "Wi-Fi networks, so check that Wi-Fi is on.")
        default:
            finish(error: "Your location isn't available right now.")
        }
    }
}
