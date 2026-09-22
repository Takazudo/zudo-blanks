"""Output-level copper gap/width measurement for check-pcbs.mjs.

Usage: python copper-check.py [--png DIR] BOARD.svg...
Reads kicad-cli F.Cu SVG exports (--black-and-white: black = copper, white = drilled holes) and
prints one JSON object per file:
  minGap    smallest edge-to-edge distance between two separate copper islands (mm), computed
            exactly from the plotted primitives (round-capped segments, polygons, discs); null
            when no two islands come within GAP_SEARCH of each other
  islands   copper islands (primitives joined wherever they touch or overlap)
  rasterIslands  8-connected copper components of the 20 px/mm raster, as a cross-check
  minWidth  widest disk diameter whose morphological opening of the raster removes no copper
            beyond corner rounding, i.e. the thinnest copper feature on the layer (mm)
A 20 px/mm raster misplaces every edge by up to half a pixel, so a pixel distance transform
reads a 0.40 mm gap as 0.30-0.35 mm depending on angle; that is why the gap is measured on
the primitives and only the width uses the raster.
Needs Pillow, numpy and scipy (install them in a venv outside the repo).
"""

import json
import math
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

PX_PER_MM = 20
MARGIN_MM = 1.0
WIDTH_PROBE_PX = range(3, 13)
GAP_SEARCH = 1.0
SVG_NS = "{http://www.w3.org/2000/svg}"


def parse_style(text, inherited):
    style = dict(inherited)
    for part in (text or "").split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            style[key.strip()] = value.strip()
    return style


def paint(value):
    if not value or value == "none":
        return None
    return 0 if value.upper() in ("#FFFFFF", "WHITE") else 255


def shapes(svg_path):
    """Yield ('stroke', pts, width, colour) / ('fill', pts, colour) / ('disc', c, r, colour)."""

    def walk(node, style):
        style = parse_style(node.get("style"), style)
        transform = node.get("transform")
        if transform and not re.fullmatch(r"\s*translate\(0 0\)\s*scale\(1 1\)\s*", transform):
            raise ValueError(f"unsupported transform {transform!r}")
        tag = node.tag.replace(SVG_NS, "")
        fill, stroke = paint(style.get("fill")), paint(style.get("stroke"))
        width = float(style.get("stroke-width", "0") or 0)
        if tag == "path":
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", node.get("d"))]
            if set(re.findall(r"[A-Za-z]", node.get("d"))) - {"M", "L", "Z", "z"}:
                raise ValueError(f"unsupported path command in {node.get('d')[:40]!r}")
            pts = list(zip(nums[0::2], nums[1::2]))
            if fill is not None and len(pts) >= 3:
                yield ("fill", pts, fill)
            if stroke is not None and width > 0:
                yield ("stroke", pts, width, stroke)
        elif tag == "circle":
            c, r = (float(node.get("cx")), float(node.get("cy"))), float(node.get("r"))
            if fill is not None:
                yield ("disc", c, r, fill)
            if stroke is not None and width > 0:
                ring = [(c[0] + r * math.cos(a), c[1] + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 73)]
                yield ("stroke", ring, width, stroke)
        for child in node:
            yield from walk(child, style)

    yield from walk(ET.parse(svg_path).getroot(), {})


def rasterise(svg_path):
    items = list(shapes(svg_path))
    xs, ys = [], []
    for item in items:
        pts = [item[1]] if item[0] == "disc" else item[1]
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    x0, y0 = min(xs) - MARGIN_MM - 3, min(ys) - MARGIN_MM - 3
    w = math.ceil((max(xs) - x0 + MARGIN_MM + 3) * PX_PER_MM)
    h = math.ceil((max(ys) - y0 + MARGIN_MM + 3) * PX_PER_MM)
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    # Pixel (i, j) covers [i, i+1) px, so its centre sits at i + 0.5.
    to_px = lambda p: ((p[0] - x0) * PX_PER_MM - 0.5, (p[1] - y0) * PX_PER_MM - 0.5)

    def disc(c, r, colour):
        cx, cy = to_px(c)
        rp = r * PX_PER_MM
        draw.ellipse([cx - rp, cy - rp, cx + rp, cy + rp], fill=colour)

    for item in items:
        if item[0] == "fill":
            draw.polygon([to_px(p) for p in item[1]], fill=item[2])
        elif item[0] == "disc":
            disc(item[1], item[2], item[3])
        else:
            _, pts, width, colour = item
            half = width / 2 * PX_PER_MM
            for a, b in zip(pts, pts[1:]):
                (ax, ay), (bx, by) = to_px(a), to_px(b)
                length = math.hypot(bx - ax, by - ay)
                if length > 1e-9:
                    nx, ny = -(by - ay) / length * half, (bx - ax) / length * half
                    draw.polygon([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)], fill=colour)
            for p in pts:  # round caps and joins
                disc(p, width / 2, colour)
    to_mm = lambda j, i: [round(x0 + (i + 0.5) / PX_PER_MM, 3), round(y0 + (j + 0.5) / PX_PER_MM, 3)]
    return np.asarray(img) > 127, img, to_mm, items


def disk(diameter_px):
    r = diameter_px / 2
    k = math.floor(r)
    yy, xx = np.mgrid[-k : k + 1, -k : k + 1]
    return xx * xx + yy * yy <= r * r


def seg_point(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) if l2 else 0.0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def seg_seg(a, b, c, d):
    if cross(c, d, a) * cross(c, d, b) < 0 and cross(a, b, c) * cross(a, b, d) < 0:
        return 0.0
    return min(seg_point(c, d, a), seg_point(c, d, b), seg_point(a, b, c), seg_point(a, b, d))


def inside(p, poly):
    hit = False
    for (xi, yi), (xj, yj) in zip(poly, poly[-1:] + poly[:-1]):
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            hit = not hit
    return hit


def copper_primitives(items):
    """Copper as capsules (segment core + radius) and polygons; white holes only remove copper."""
    prims = []
    for item in items:
        if item[-1] != 255:
            continue
        if item[0] == "stroke":
            pts, r = item[1], item[2] / 2
            prims += [("cap", (a, b), r) for a, b in zip(pts, pts[1:])] or [("cap", (pts[0], pts[0]), r)]
        elif item[0] == "disc":
            prims.append(("cap", (item[1], item[1]), item[2]))
        else:
            prims.append(("poly", item[1], 0.0))
    return prims


def prim_dist(p, q):
    """Edge-to-edge distance, <= 0 when the two primitives touch or overlap."""
    if p[0] == "poly" and q[0] == "cap":
        p, q = q, p
    if p[0] == "cap" and q[0] == "cap":
        return seg_seg(*p[1], *q[1]) - p[2] - q[2]
    edges = list(zip(q[1], q[1][1:] + q[1][:1]))
    if p[0] == "cap":
        if inside(p[1][0], q[1]):
            return -p[2]
        return min(seg_seg(*p[1], a, b) for a, b in edges) - p[2]
    if inside(p[1][0], q[1]) or inside(q[1][0], p[1]):
        return 0.0
    return min(seg_seg(a, b, c, d) for a, b in zip(p[1], p[1][1:] + p[1][:1]) for c, d in edges)


def min_gap(items):
    prims = copper_primitives(items)
    boxes = []
    for kind, geo, r in prims:
        pts = geo if kind == "poly" else list(geo)
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        boxes.append((min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r))
    cell, grid = 2.0, {}
    for k, (x0, y0, x1, y1) in enumerate(boxes):
        for i in range(int(x0 // cell), int(x1 // cell) + 1):
            for j in range(int(y0 // cell), int(y1 // cell) + 1):
                grid.setdefault((i, j), []).append(k)
    parent = list(range(len(prims)))

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    near = []
    for k, (x0, y0, x1, y1) in enumerate(boxes):
        seen = set()
        for i in range(int((x0 - GAP_SEARCH) // cell), int((x1 + GAP_SEARCH) // cell) + 1):
            for j in range(int((y0 - GAP_SEARCH) // cell), int((y1 + GAP_SEARCH) // cell) + 1):
                for m in grid.get((i, j), ()):
                    if m <= k or m in seen:
                        continue
                    seen.add(m)
                    bx0, by0, bx1, by1 = boxes[m]
                    if bx0 - x1 > GAP_SEARCH or x0 - bx1 > GAP_SEARCH or by0 - y1 > GAP_SEARCH or y0 - by1 > GAP_SEARCH:
                        continue
                    d = prim_dist(prims[k], prims[m])
                    if d <= 1e-9:
                        parent[find(k)] = find(m)
                    elif d < GAP_SEARCH:
                        near.append((d, k, m))
    islands = len({find(k) for k in range(len(prims))})
    best = min(((d, k, m) for d, k, m in near if find(k) != find(m)), default=None)
    if best is None:
        return None, islands, None
    at = lambda p: [round(v, 3) for v in p[1][0]]
    return best[0], islands, [at(prims[best[1]]), at(prims[best[2]])]


def min_width(copper, to_mm):
    passed, worst = 0, None
    for d in WIDTH_PROBE_PX:
        opened = ndimage.binary_opening(copper, structure=disk(d))
        residue = copper & ~opened
        # A disk rounds convex 90 degree corners off by up to (sqrt(2) - 1) * r; anything that
        # sticks out further than that is a feature thinner than the disk.
        tolerance = (math.sqrt(2) - 1) * d / 2 + 1
        depth = ndimage.distance_transform_edt(~opened)
        depth[~residue] = 0
        j, i = np.unravel_index(int(np.argmax(depth)), depth.shape)
        if depth[j, i] > tolerance:
            worst = {"probeMm": d / PX_PER_MM, "depthMm": round(float(depth[j, i]) / PX_PER_MM, 3), "at": to_mm(j, i)}
            break
        passed = d
    return passed / PX_PER_MM, worst


def main(argv):
    png_dir = None
    if argv[:1] == ["--png"]:
        png_dir, argv = argv[1], argv[2:]
    for path in argv:
        copper, img, to_mm, items = rasterise(path)
        gap, islands, gap_at = min_gap(items)
        raster_islands = ndimage.label(copper, structure=np.ones((3, 3), bool))[1]
        width, thin_at = min_width(copper, to_mm)
        if png_dir:
            img.save(f"{png_dir}/{path.rsplit('/', 1)[-1].rsplit('.', 1)[0]}-fcu.png")
        print(json.dumps({"file": path, "pxPerMm": PX_PER_MM, "islands": islands, "rasterIslands": raster_islands,
                          "minGap": gap, "gapAt": gap_at,
                          "minWidth": width, "widthLimitedBy": thin_at}))


if __name__ == "__main__":
    main(sys.argv[1:])
