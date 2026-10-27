// Draws the Ovenbird app icon and writes every PNG an .iconset needs.
//   swift app/icon.swift <out.iconset>
//   iconutil -c icns <out.iconset> -o AppIcon.icns
//
// Design (1024-unit canvas, macOS icon grid): a continuous-corner rounded square
// ("squircle", 824 x 824 at a 100 inset) with a warm diagonal gradient, a faint highlight
// at the top, and a centered off-white diamond with a soft shadow. Each size is drawn
// from vectors rather than downscaled, so small sizes stay crisp.
import AppKit
import CoreGraphics
import ImageIO

let canvas: CGFloat = 1024
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

func drawIcon(_ ctx: CGContext, pixels: Int) {
    let s = CGFloat(pixels) / canvas
    ctx.scaleBy(x: s, y: s)  // note: shadow offset/blur ignore the CTM, so they're scaled by hand
    ctx.setShouldAntialias(true)
    ctx.interpolationQuality = .high

    let body = CGRect(x: 100, y: 100, width: 824, height: 824)
    let shape = squircle(body, radius: 185.4)

    // The body's own drop shadow, as in Apple's icon template.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10 * s), blur: 24 * s, color: rgb(0x000000, 0.30))
    ctx.addPath(shape)
    ctx.setFillColor(rgb(0xB4532F))
    ctx.fillPath()
    ctx.restoreGState()

    // Warm diagonal gradient, top-left to bottom-right.
    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()
    let warm = CGGradient(colorsSpace: srgb, colors: [rgb(0xE8896A), rgb(0xB4532F)] as CFArray, locations: [0, 1])!
    ctx.drawLinearGradient(warm, start: CGPoint(x: body.minX, y: body.maxY),
                           end: CGPoint(x: body.maxX, y: body.minY), options: [])

    // Faint highlight across the top half.
    let glow = CGGradient(colorsSpace: srgb, colors: [rgb(0xFFFFFF, 0.20), rgb(0xFFFFFF, 0)] as CFArray,
                          locations: [0, 1])!
    ctx.drawLinearGradient(glow, start: CGPoint(x: 0, y: body.maxY), end: CGPoint(x: 0, y: body.midY + 40), options: [])

    // A hairline of light along the top rim (inner half of a stroke, fading downwards).
    ctx.saveGState()
    ctx.addPath(shape)
    ctx.setLineWidth(6)
    ctx.replacePathWithStrokedPath()
    ctx.clip()
    let rim = CGGradient(colorsSpace: srgb, colors: [rgb(0xFFFFFF, 0.30), rgb(0xFFFFFF, 0)] as CFArray,
                         locations: [0, 1])!
    ctx.drawLinearGradient(rim, start: CGPoint(x: 0, y: body.maxY), end: CGPoint(x: 0, y: body.maxY - 260), options: [])
    ctx.restoreGState()
    ctx.restoreGState()

    // The diamond: a square rotated 45 degrees, 38% of the icon wide, tip to tip.
    let half = 0.38 * canvas / 2
    let c = CGPoint(x: canvas / 2, y: canvas / 2)
    let diamond = CGMutablePath()
    diamond.move(to: CGPoint(x: c.x, y: c.y + half))
    diamond.addLine(to: CGPoint(x: c.x + half, y: c.y))
    diamond.addLine(to: CGPoint(x: c.x, y: c.y - half))
    diamond.addLine(to: CGPoint(x: c.x - half, y: c.y))
    diamond.closeSubpath()

    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -14 * s), blur: 40 * s, color: rgb(0x4A1A08, 0.38))
    ctx.addPath(diamond)
    ctx.setFillColor(rgb(0xFFF8F1))
    ctx.fillPath()
    ctx.restoreGState()
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
