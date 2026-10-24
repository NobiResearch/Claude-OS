// swift-tools-version:5.9
// Claude OS.app: the native macOS shell around the `cos serve` desktop.
// Build the bundle with app/build.sh (this package only produces the executable).
import PackageDescription

let package = Package(
    name: "ClaudeOS",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "ClaudeOS", targets: ["ClaudeOS"]),
    ],
    targets: [
        .executableTarget(
            name: "ClaudeOS",
            path: "Sources/ClaudeOS",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("WebKit"),
                .linkedFramework("Carbon"),
            ]
        ),
    ]
)
