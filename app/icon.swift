// Draws the Ovenbird app icon and writes every PNG an .iconset needs.
//   swift app/icon.swift <out.iconset>
//   iconutil -c icns <out.iconset> -o AppIcon.icns
//
// Design: the Nest (decision 0021; every number is from docs/brand/README.md). On the macOS
// icon grid (1024 canvas, a continuous-corner 824 x 824 body at a 100 inset): an olive-to-night
// gradient, a faint Crown glow under the doorway, a Moss ground line, a cream dome taller than
// a half circle, and its diamond doorway in Crown. Each size is drawn from vectors rather than
// downscaled; 16 and 32 px use the designer's hand-drawn shapes on whole pixels.
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

/// One drawing of the Nest, in its own grid's units with y down, as in the brand note's SVGs.
struct Nest {
    let grid: CGFloat
    let body: CGRect
    let radius: CGFloat
    let ground: CGRect  // the ground line as a bar (round-capped on the master)
    let dome: [CGFloat]  // M x y, C x y x y x y, C x y x y x y
    let door: [CGFloat]  // the diamond: top, right, bottom, left
    let handDrawn: Bool  // whole pixels: plain corners, no shadow, no glow
}

let master = Nest(grid: 1024, body: CGRect(x: 100, y: 100, width: 824, height: 824), radius: 185.4,
                  ground: CGRect(x: 184, y: 748, width: 656, height: 24),
                  dome: [232, 760, 232, 462, 316, 280, 512, 280, 708, 280, 792, 462, 792, 760],
                  door: [620, 460, 720, 610, 620, 760, 520, 610], handDrawn: false)
let at32 = Nest(grid: 32, body: CGRect(x: 3, y: 3, width: 26, height: 26), radius: 6,
                ground: CGRect(x: 6, y: 23, width: 20, height: 1),
                dome: [7, 24, 7, 14.7, 9.7, 9, 16, 9, 22.3, 9, 25, 14.7, 25, 24],
                door: [19, 16, 22, 20, 19, 24, 16, 20], handDrawn: true)
let at16 = Nest(grid: 16, body: CGRect(x: 1, y: 1, width: 14, height: 14), radius: 3,
                ground: CGRect(x: 2, y: 12, width: 12, height: 1),
                dome: [3, 13, 3, 8, 4.5, 5, 8, 5, 11.5, 5, 13, 8, 13, 13],
                door: [9, 7, 11, 10, 9, 13, 7, 10], handDrawn: true)

func point(_ v: [CGFloat], _ i: Int) -> CGPoint { CGPoint(x: v[i], y: v[i + 1]) }

func drawIcon(_ ctx: CGContext, pixels: Int) {
    let nest = pixels == 16 ? at16 : pixels == 32 ? at32 : master
    let s = CGFloat(pixels) / nest.grid
    ctx.scaleBy(x: s, y: s)  // note: shadow offset/blur ignore the CTM, so they're scaled by hand
    ctx.translateBy(x: 0, y: nest.grid)
    ctx.scaleBy(x: 1, y: -1)  // y down, like the SVGs
    ctx.setShouldAntialias(true)
    ctx.interpolationQuality = .high

    let shape = nest.handDrawn
        ? CGPath(roundedRect: nest.body, cornerWidth: nest.radius, cornerHeight: nest.radius, transform: nil)
        : squircle(nest.body, radius: nest.radius)

    // The body's own drop shadow, as in Apple's icon template.
    if !nest.handDrawn {
        ctx.saveGState()
        ctx.setShadow(offset: CGSize(width: 0, height: -10 * s), blur: 24 * s, color: rgb(0x000000, 0.30))
        ctx.addPath(shape)
        ctx.setFillColor(rgb(0x27241A))
        ctx.fillPath()
        ctx.restoreGState()
    }

    // Olive at the top to night at the bottom, and a faint Crown glow under the doorway.
    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()
    let night = CGGradient(colorsSpace: srgb, colors: [rgb(0x4F4B34), rgb(0x27241A)] as CFArray, locations: [0, 1])!
    ctx.drawLinearGradient(night, start: CGPoint(x: 0, y: nest.body.minY), end: CGPoint(x: 0, y: nest.body.maxY), options: [])
    if !nest.handDrawn {
        let glow = CGGradient(colorsSpace: srgb, colors: [rgb(0xE0912F, 0.22), rgb(0xE0912F, 0)] as CFArray,
                              locations: [0, 1])!
        ctx.drawRadialGradient(glow, startCenter: CGPoint(x: 620, y: 700), startRadius: 0,
                               endCenter: CGPoint(x: 620, y: 700), endRadius: 260, options: [])
    }
    ctx.restoreGState()

    // The ground line in Moss, then the cream dome on it, then the doorway in Crown.
    let cap = nest.handDrawn ? 0 : nest.ground.height / 2
    ctx.addPath(CGPath(roundedRect: nest.ground, cornerWidth: cap, cornerHeight: cap, transform: nil))
    ctx.setFillColor(rgb(0x8F8A5A))
    ctx.fillPath()

    let d = nest.dome
    let dome = CGMutablePath()
    dome.move(to: point(d, 0))
    dome.addCurve(to: point(d, 6), control1: point(d, 2), control2: point(d, 4))
    dome.addCurve(to: point(d, 12), control1: point(d, 8), control2: point(d, 10))
    dome.closeSubpath()
    ctx.addPath(dome)
    ctx.setFillColor(rgb(0xF3EADA))
    ctx.fillPath()

    let door = CGMutablePath()
    door.addLines(between: stride(from: 0, to: 8, by: 2).map { point(nest.door, $0) })
    door.closeSubpath()
    ctx.addPath(door)
    ctx.setFillColor(rgb(0xE0912F))
    ctx.fillPath()
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
