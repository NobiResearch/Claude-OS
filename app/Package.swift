// swift-tools-version:5.9
// Claude OS.app: the native macOS shell around the `cos serve` desktop, and
// Claude OS Music Helper.app, the small app that holds the Accessibility grant.
// Build the bundles with app/build.sh (this package only produces the executables).
import PackageDescription

let package = Package(
    name: "ClaudeOS",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "ClaudeOS", targets: ["ClaudeOS"]),
        .executable(name: "ClaudeOSMusicHelper", targets: ["MusicHelper"]),
    ],
    targets: [
        .executableTarget(
            name: "ClaudeOS",
            path: "Sources/ClaudeOS",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("WebKit"),
                .linkedFramework("Carbon"),
                .linkedFramework("CoreLocation"),
            ]
        ),
        .executableTarget(
            name: "MusicHelper",
            path: "Sources/MusicHelper",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("ApplicationServices"),
            ]
        ),
    ]
)
