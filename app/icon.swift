// Draws the Ovenbird app icon and writes every PNG an .iconset needs.
//   swift app/icon.swift <out.iconset>
//   iconutil -c icns <out.iconset> -o AppIcon.icns
//
// Design: Courses, the dark variant (decision 0022; every number is from docs/brand/README.md).
// On the macOS icon grid (1024 canvas, a continuous-corner 824 x 824 body at a 100 inset): a flat
// #0F0F0F body and the oven-nest's dome as four round-ended courses, the top one in Crown, the
// doorway a gap in the lower two. Each size is drawn from vectors rather than downscaled; 16 and
// 32 px use the designer's hand-drawn bars on whole pixels.
import AppKit
import CoreGraphics
import ImageIO

let srgb = CGColorSpace(name: CGColorSpace.sRGB)!

func rgb(_ hex: UInt32, _ alpha: CGFloat = 1) -> CGColor {
    CGColor(colorSpace: srgb, components: [
        CGFloat((hex >> 16) & 0xff) / 255, CGFloat((hex >> 8) & 0xff) / 255, CGFloat(hex & 0xff) / 255, alpha,
    ])!
}

/// Rounded rect with Apple-style continuous corners (curvature eases into the straight
/// edges instead of jumping, as a circular arc does). Coefficients are the well-known
/// fit of UIKit's continuous corner curve, in units of the corner radius.
func squircle(_ rect: CGRect, radius: CGFloat) -> CGPath {
    let k: CGFloat = 1.52866483
    let r = min(radius, min(rect.width, rect.height) / 2 / k)
    // Each corner: its point, the unit vector back along the incoming edge, and along the outgoing one.
    let corners: [(CGPoint, CGVector, CGVector)] = [
        (CGPoint(x: rect.maxX, y: rect.maxY), CGVector(dx: -1, dy: 0), CGVector(dx: 0, dy: -1)),
        (CGPoint(x: rect.maxX, y: rect.minY), CGVector(dx: 0, dy: 1), CGVector(dx: -1, dy: 0)),
        (CGPoint(x: rect.minX, y: rect.minY), CGVector(dx: 1, dy: 0), CGVector(dx: 0, dy: 1)),
        (CGPoint(x: rect.minX, y: rect.maxY), CGVector(dx: 0, dy: -1), CGVector(dx: 1, dy: 0)),
    ]
    let path = CGMutablePath()
    for (i, (c, a, b)) in corners.enumerated() {
        func p(_ s: CGFloat, _ t: CGFloat) -> CGPoint {
            CGPoint(x: c.x + (s * a.dx + t * b.dx) * r, y: c.y + (s * a.dy + t * b.dy) * r)
        }
        if i == 0 { path.move(to: p(k, 0)) } else { path.addLine(to: p(k, 0)) }
        path.addCurve(to: p(0.66993427, 0.06549600), control1: p(1.08849323, 0), control2: p(0.86840689, 0))
        path.addLine(to: p(0.63149399, 0.07491100))
        path.addCurve(to: p(0.07491100, 0.63149399), control1: p(0.37282392, 0.16905899), control2: p(0.16905899, 0.37282392))
        path.addLine(to: p(0.06549600, 0.66993427))
        path.addCurve(to: p(0, k), control1: p(0, 0.86840689), control2: p(0, 1.08849323))
    }
    path.closeSubpath()
    return path
}

/// One drawing of the mark (Courses), in its own grid's units with y down, as in the brand note's SVGs.
/// Every course is a bar with fully rounded ends: a rect whose corner radius is half its height
/// (on the master, the note's round-capped stroke of 88 around each centre line).
struct Mark {
    let grid: CGFloat
    let body: CGRect
    let radius: CGFloat
    let courses: [CGRect]  // top to bottom; the first is the Crown course
    let handDrawn: Bool    // whole pixels: plain corners, no shadow
}

let master = Mark(grid: 1024, body: CGRect(x: 100, y: 100, width: 824, height: 824), radius: 185.4, courses: [
    CGRect(x: 380, y: 270, width: 264, height: 88),
    CGRect(x: 281, y: 402, width: 462, height: 88),
    CGRect(x: 226, y: 534, width: 385, height: 88), CGRect(x: 699, y: 534, width: 99, height: 88),
    CGRect(x: 204, y: 666, width: 407, height: 88), CGRect(x: 699, y: 666, width: 121, height: 88),
], handDrawn: false)
let at32 = Mark(grid: 32, body: CGRect(x: 3, y: 3, width: 26, height: 26), radius: 6, courses: [
    CGRect(x: 13, y: 8, width: 6, height: 3),
    CGRect(x: 10, y: 13, width: 12, height: 3),
    CGRect(x: 8, y: 18, width: 10, height: 3), CGRect(x: 22, y: 18, width: 3, height: 3),
    CGRect(x: 7, y: 23, width: 11, height: 3), CGRect(x: 22, y: 23, width: 4, height: 3),
], handDrawn: true)
let at16 = Mark(grid: 16, body: CGRect(x: 1, y: 1, width: 14, height: 14), radius: 3, courses: [
    CGRect(x: 6, y: 3, width: 4, height: 2),
    CGRect(x: 4, y: 6, width: 8, height: 2),
    CGRect(x: 3, y: 9, width: 6, height: 2), CGRect(x: 11, y: 9, width: 2, height: 2),
    CGRect(x: 3, y: 12, width: 6, height: 2), CGRect(x: 11, y: 12, width: 2, height: 2),
], handDrawn: true)

func drawIcon(_ ctx: CGContext, pixels: Int) {
    let icon = pixels == 16 ? at16 : pixels == 32 ? at32 : master
    let s = CGFloat(pixels) / icon.grid
    ctx.scaleBy(x: s, y: s)  // note: shadow offset/blur ignore the CTM, so they're scaled by hand
    ctx.translateBy(x: 0, y: icon.grid)
    ctx.scaleBy(x: 1, y: -1)  // y down, like the SVGs
    ctx.setShouldAntialias(true)

    let shape = icon.handDrawn
        ? CGPath(roundedRect: icon.body, cornerWidth: icon.radius, cornerHeight: icon.radius, transform: nil)
        : squircle(icon.body, radius: icon.radius)

    // The dark body, flat (no gradient, no glow), with its drop shadow as in Apple's icon template.
    ctx.saveGState()
    if !icon.handDrawn {
        ctx.setShadow(offset: CGSize(width: 0, height: -10 * s), blur: 24 * s, color: rgb(0x000000, 0.30))
    }
    ctx.addPath(shape)
    ctx.setFillColor(rgb(0x0F0F0F))
    ctx.fillPath()
    ctx.restoreGState()

    // The courses: Crown on top, white below, the doorway the gap in the lower two.
    for (i, bar) in icon.courses.enumerated() {
        let r = bar.height / 2
        ctx.addPath(CGPath(roundedRect: bar, cornerWidth: r, cornerHeight: r, transform: nil))
        ctx.setFillColor(i == 0 ? rgb(0xE0912F) : rgb(0xFFFFFF))
        ctx.fillPath()
    }
}

func render(pixels: Int) -> CGImage {
    let ctx = CGContext(data: nil, width: pixels, height: pixels, bitsPerComponent: 8, bytesPerRow: 0,
                        space: srgb, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.clear(CGRect(x: 0, y: 0, width: pixels, height: pixels))
    drawIcon(ctx, pixels: pixels)
    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, to url: URL, scale: Int) {
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, "public.png" as CFString, 1, nil) else {
        fatalError("can't write \(url.path)")
    }
    let dpi = 72 * scale
    CGImageDestinationAddImage(dest, image, [kCGImagePropertyDPIWidth: dpi, kCGImagePropertyDPIHeight: dpi] as CFDictionary)
    guard CGImageDestinationFinalize(dest) else { fatalError("can't write \(url.path)") }
}

let args = CommandLine.arguments
guard args.count == 2, args[1].hasSuffix(".iconset") else {
    FileHandle.standardError.write(Data("usage: swift app/icon.swift <out.iconset>\n".utf8))
    exit(2)
}
let out = URL(fileURLWithPath: args[1], isDirectory: true)
try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)

for points in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let name = "icon_\(points)x\(points)" + (scale == 2 ? "@2x" : "") + ".png"
        writePNG(render(pixels: points * scale), to: out.appendingPathComponent(name), scale: scale)
    }
}
print("wrote \(out.path)")
