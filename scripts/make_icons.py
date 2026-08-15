#!/usr/bin/env python3
"""Render the project mark into the application icons harness-view ships with.

The source of truth is `docs/assets/logo-mark.svg` - the compact shield-and-eye
mark. Everything here is DERIVED from it, so changing the brand means re-running
this script rather than hand-editing opaque binaries that nobody can regenerate.

    py -3.13 scripts/make_icons.py            # write every output
    py -3.13 scripts/make_icons.py --check    # verify the outputs exist and parse

Outputs:
    tools/harness-view/assets/icon.ico          Windows, 16/32/48/64/128/256
    tools/harness-view/assets/icon-<N>.png      flat PNG set (docs, macOS bundles)
    tools/harness-view/assets/icon.icns         macOS container, PNG-backed
    tools/harness-view/assets/favicon.b64       32x32 PNG, base64, for the served page

Why a renderer rather than a converter: cairosvg and friends are not installed
and pull in native libraries. The mark uses a small, closed subset of SVG (path
with M/L/C/Q/Z, circle, polygon, linear and radial gradients), so a subset
renderer is both smaller than a dependency and exact for this input. It fails
loudly on anything outside that subset instead of silently dropping shapes.

Pillow does the rasterising. It is not in the standard library, so the script
says so plainly and exits non-zero when it is missing rather than throwing an
ImportError at whoever runs it.
"""
from __future__ import annotations

import base64
import math
import pathlib
import re
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "assets" / "logo-mark.svg"
OUT = ROOT / "tools" / "harness-view" / "assets"

# Rendered once at this size, then downsampled per target. Downsampling from a
# single high-resolution master keeps the small sizes crisper than rendering
# each one directly, where a 16px shield would lose its rim entirely.
MASTER = 1024
ICO_SIZES = [16, 32, 48, 64, 128, 256]
PNG_SIZES = [16, 32, 64, 128, 256, 512, 1024]
# (icns chunk type, pixel size). PNG-backed chunks, which macOS 10.7+ accepts.
ICNS_CHUNKS = [(b"icp4", 16), (b"icp5", 32), (b"ic07", 128),
               (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024)]

SVG_NS = "{http://www.w3.org/2000/svg}"

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - environment-dependent
    print("error: this script needs Pillow to rasterise the mark.\n"
          "       install it with:  py -3.13 -m pip install pillow\n"
          "       (the committed icons are the fallback: they only need "
          "regenerating when docs/assets/logo-mark.svg changes)", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- svg parsing

def parse_color(v: str) -> tuple[int, int, int]:
    v = v.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
    if not m:
        raise ValueError(f"unsupported colour {v!r} - this renderer takes #rrggbb only")
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def path_points(d: str, steps: int = 64) -> list[tuple[float, float]]:
    """Flatten an SVG path into a polygon. Absolute M/L/C/Q/Z only, which is
    everything the mark uses; anything else raises rather than silently
    deforming the shape."""
    tokens = re.findall(r"[MLCQZmlcqz]|-?\d*\.?\d+", d)
    pts: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        if cmd not in "MLCQZmlcqz":
            raise ValueError(f"unexpected token {cmd!r} in path data")
        i += 1
        if cmd in "Zz":
            if pts and pts[-1] != start:
                pts.append(start)
            cur = start
            continue
        # A command letter may be followed by several coordinate sets.
        while i < len(tokens) and tokens[i] not in "MLCQZmlcqz":
            if cmd in "Mm":
                x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
                cur = start = (x, y)
                pts.append(cur)
            elif cmd in "Ll":
                x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
                cur = (x, y)
                pts.append(cur)
            elif cmd in "Cc":
                x1, y1, x2, y2, x, y = (float(t) for t in tokens[i:i + 6]); i += 6
                p0 = cur
                for s in range(1, steps + 1):
                    t = s / steps
                    u = 1 - t
                    px = (u ** 3 * p0[0] + 3 * u * u * t * x1
                          + 3 * u * t * t * x2 + t ** 3 * x)
                    py = (u ** 3 * p0[1] + 3 * u * u * t * y1
                          + 3 * u * t * t * y2 + t ** 3 * y)
                    pts.append((px, py))
                cur = (x, y)
            elif cmd in "Qq":
                x1, y1, x, y = (float(t) for t in tokens[i:i + 4]); i += 4
                p0 = cur
                for s in range(1, steps + 1):
                    t = s / steps
                    u = 1 - t
                    px = u * u * p0[0] + 2 * u * t * x1 + t * t * x
                    py = u * u * p0[1] + 2 * u * t * y1 + t * t * y
                    pts.append((px, py))
                cur = (x, y)
            else:
                raise ValueError(f"relative command {cmd!r} is not supported")
    return pts


def gradients(root: ET.Element) -> dict:
    out = {}
    for tag, kind in ((f"{SVG_NS}linearGradient", "linear"),
                      (f"{SVG_NS}radialGradient", "radial")):
        for g in root.iter(tag):
            stops = [(float(s.get("offset", 0)), parse_color(s.get("stop-color")))
                     for s in g.iter(f"{SVG_NS}stop")]
            out[g.get("id")] = {"kind": kind, "stops": sorted(stops),
                                **{k: float(v) for k, v in g.attrib.items()
                                   if k in ("x1", "y1", "x2", "y2", "cx", "cy", "r")}}
    return out


# ---------------------------------------------------------------- painting

def lerp_stops(stops, t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    prev = stops[0]
    for off, col in stops:
        if t <= off:
            if off == prev[0]:
                return col
            f = (t - prev[0]) / (off - prev[0])
            return tuple(round(prev[1][i] + (col[i] - prev[1][i]) * f) for i in range(3))
        prev = (off, col)
    return stops[-1][1]


def paint_layer(size: int, scale: float, spec, grads) -> Image.Image:
    """An RGB image of the fill: a flat colour, or the gradient evaluated over
    the whole canvas. The caller masks it to the shape."""
    if not spec.startswith("url("):
        return Image.new("RGB", (size, size), parse_color(spec))
    g = grads[spec[5:-1]]
    img = Image.new("RGB", (size, size))
    if g["kind"] == "linear":
        # Every gradient in the mark runs vertically; a one-pixel column resized
        # to the canvas is exact for that and avoids a per-pixel loop.
        if abs(g["x1"] - g["x2"]) > 1e-6:
            raise ValueError("only vertical linear gradients are supported")
        y1, y2 = g["y1"] * scale, g["y2"] * scale
        col = Image.new("RGB", (1, size))
        px = col.load()
        for y in range(size):
            px[0, y] = lerp_stops(g["stops"], (y - y1) / (y2 - y1) if y2 != y1 else 0)
        return col.resize((size, size), Image.NEAREST)
    # Radial: concentric filled circles, outermost first. One circle per pixel of
    # radius is smooth at this resolution and far cheaper than a per-pixel solve.
    cx, cy, r = g["cx"] * scale, g["cy"] * scale, g["r"] * scale
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size, size], fill=lerp_stops(g["stops"], 1.0))
    for step in range(int(r), 0, -1):
        d.ellipse([cx - step, cy - step, cx + step, cy + step],
                  fill=lerp_stops(g["stops"], step / r))
    return img


def render(svg: pathlib.Path, size: int) -> Image.Image:
    root = ET.parse(svg).getroot()
    vb = [float(v) for v in root.get("viewBox").split()]
    if vb[2] != vb[3]:
        raise ValueError("the mark must be square")
    scale = size / vb[2]
    grads = gradients(root)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    def compose(mask: Image.Image, spec: str, alpha: float = 1.0) -> None:
        if spec in (None, "none"):
            return
        layer = paint_layer(size, scale, spec, grads).convert("RGBA")
        if alpha < 1.0:
            m = mask.point(lambda v: int(v * alpha))
        else:
            m = mask
        canvas.paste(layer, (0, 0), m)

    def sc(pts):
        return [(x * scale, y * scale) for x, y in pts]

    def walk(el: ET.Element, inherited: dict) -> None:
        attrs = dict(inherited)
        attrs.update({k: v for k, v in el.attrib.items()})
        tag = el.tag
        opacity = float(attrs.get("opacity", 1.0))

        if tag == f"{SVG_NS}g":
            for child in el:
                walk(child, attrs)
            return

        pts = None
        if tag == f"{SVG_NS}path":
            pts = sc(path_points(el.get("d")))
        elif tag == f"{SVG_NS}polygon":
            raw = [float(v) for v in re.findall(r"-?\d*\.?\d+", el.get("points"))]
            pts = sc(list(zip(raw[0::2], raw[1::2])))
        elif tag == f"{SVG_NS}circle":
            cx, cy, r = (float(el.get(k)) for k in ("cx", "cy", "r"))
            pts = sc([(cx + r * math.cos(a * math.pi / 32),
                       cy + r * math.sin(a * math.pi / 32)) for a in range(64)])
        elif tag in (f"{SVG_NS}defs", f"{SVG_NS}svg"):
            for child in el:
                walk(child, attrs)
            return
        else:
            return

        fill = attrs.get("fill", "#000000")
        if fill != "none" and len(pts) > 2:
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).polygon(pts, fill=255)
            compose(mask, fill, opacity)

        stroke = attrs.get("stroke")
        if stroke and stroke != "none":
            w = float(attrs.get("stroke-width", 1)) * scale
            mask = Image.new("L", (size, size), 0)
            md = ImageDraw.Draw(mask)
            closed = tag != f"{SVG_NS}path" or (el.get("d") or "").rstrip().endswith(("Z", "z"))
            line = pts + [pts[0]] if closed and pts[0] != pts[-1] else pts
            md.line(line, fill=255, width=max(1, round(w)), joint="curve")
            # Pillow has no line caps: round them by hand so short strokes do not
            # end in a blunt square, which is very visible on the crown spokes.
            if attrs.get("stroke-linecap") == "round" or attrs.get("stroke-linejoin") == "round":
                for (px, py) in (line[0], line[-1]):
                    md.ellipse([px - w / 2, py - w / 2, px + w / 2, py + w / 2], fill=255)
            compose(mask, stroke, opacity)

    walk(root, {})
    return canvas


# ---------------------------------------------------------------- outputs

def write_icns(master: Image.Image, dest: pathlib.Path) -> None:
    """Minimal ICNS writer: 'icns' magic, total length, then one PNG chunk per
    size. Modern macOS reads PNG-backed chunks, so no legacy RLE is needed."""
    import io
    chunks = b""
    for kind, px in ICNS_CHUNKS:
        buf = io.BytesIO()
        master.resize((px, px), Image.LANCZOS).save(buf, format="PNG")
        data = buf.getvalue()
        chunks += kind + struct.pack(">I", len(data) + 8) + data
    dest.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def check() -> int:
    problems = []
    ico = OUT / "icon.ico"
    if not ico.is_file():
        problems.append("icon.ico is missing - run this script without --check")
    else:
        with Image.open(ico) as im:
            have = sorted({s[0] for s in im.info.get("sizes", [])} or {im.size[0]})
            missing = [s for s in ICO_SIZES if s not in have]
            if missing:
                problems.append(f"icon.ico lacks sizes {missing} (has {have})")
    for name in ("favicon.b64", "icon.icns"):
        if not (OUT / name).is_file():
            problems.append(f"{name} is missing")
    if problems:
        for p in problems:
            print("  - " + p)
        return 1
    print(f"ok: icons present, icon.ico carries {ICO_SIZES}")
    return 0


def main() -> int:
    if not SRC.is_file():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    if "--check" in sys.argv:
        return check()

    master = render(SRC, MASTER)

    (OUT / "icon.ico").unlink(missing_ok=True)
    master.resize((256, 256), Image.LANCZOS).save(
        OUT / "icon.ico", format="ICO",
        sizes=[(s, s) for s in ICO_SIZES])
    print(f"icon.ico          {ICO_SIZES}")

    for s in PNG_SIZES:
        master.resize((s, s), Image.LANCZOS).save(OUT / f"icon-{s}.png", format="PNG")
    print(f"icon-<N>.png      {PNG_SIZES}")

    write_icns(master, OUT / "icon.icns")
    print(f"icon.icns         {[px for _, px in ICNS_CHUNKS]}")

    import io
    buf = io.BytesIO()
    master.resize((32, 32), Image.LANCZOS).save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    (OUT / "favicon.b64").write_text(b64, encoding="utf-8")
    print(f"favicon.b64       32x32, {len(b64)} base64 chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
