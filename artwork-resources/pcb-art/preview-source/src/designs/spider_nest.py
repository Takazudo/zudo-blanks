"""Spider Nest, revision 4: one large web reaching the perimeter and screws.

Seven different flat angular networks span a jagged, almost full-size well.
The top copper follows these very same structural paths and extends them
across the solid rail margins; it is not a separate small-scale texture.
"""

from math import atan2, cos, sin
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from build_common import (
    H, W, SCREWS, SLOTS, SLOT_DRILL, ensure_polygon, make_layer, plate,
    polyline_art, ribbon,
)

_PREVIOUS_OPENING_MM2 = 5228.408118015001
_PREVIOUS_BOUNDS = (10.5, 27.0, 90.8, 101.5)

# Four rays terminate in the actual mounting islands; the others enter the
# narrow side frames or the continuous upper/lower bridges.
_ANCHORS = (
    SCREWS[0], (31.0, 18.0), (59.0, 18.2), SCREWS[1],
    (99.7, 47.5), (99.7, 79.0), SCREWS[3],
    (66.0, 110.3), (34.5, 110.3), SCREWS[2],
    (1.6, 80.0), (1.6, 45.5),
)
_MOUNT_RAYS = {0, 3, 6, 9}
_CENTRES = (
    (46.0, 65.0), (55.0, 61.5), (43.5, 60.5), (53.0, 71.0),
    (44.0, 71.0), (56.0, 67.5), (48.0, 58.5),
)
_INNER_GAPS = ({2, 7}, {8}, {1, 5}, {4, 9}, {0, 8}, {3, 7}, {6, 10})
_OUTER_LINKS = (
    (0, 1, 3, 4, 6, 8, 10), (1, 3, 5, 7, 9, 11),
    (0, 2, 4, 5, 7, 9, 11), (0, 3, 5, 6, 8, 10),
    (1, 2, 4, 6, 8, 9, 11), (0, 2, 4, 7, 9, 10),
    (1, 3, 5, 6, 8, 10, 11),
)


def _mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _opening_envelope():
    """Asymmetric perimeter within the lower-board rectangle.

    The thinnest solid continuous upper/lower bridges are 1.9 mm.
    """
    return Polygon((
        (13.1, 22.1), (25.8, 19.0), (40.6, 21.0), (55.9, 19.5),
        (70.6, 21.4), (84.6, 19.8), (89.6, 29.5), (97.5, 33.6),
        (98.8, 47.0), (96.4, 60.6), (98.2, 78.4), (97.0, 94.6),
        (87.7, 99.3), (83.9, 108.8), (69.6, 107.0), (54.3, 109.5),
        (38.2, 107.2), (17.1, 109.1), (10.7, 97.8), (3.2, 94.9),
        (4.7, 80.8), (2.5, 65.1), (4.3, 49.0), (2.9, 36.1),
        (10.0, 31.0),
    ))


def _mount_material():
    """Square lands cover radius 3.05 mm and join the side frame."""
    parts = []
    for x, y in SCREWS:
        parts.append(box(x - 3.25, y - 3.25, x + 3.25, y + 3.25))
        edge_x = 0.0 if x < W / 2 else W
        parts.append(ribbon(((edge_x, y), (x, y)), 2.4, rounded=False))
    return unary_union(parts)


def _angular_joint(point, angle, radius):
    x, y = point
    dx, dy = radius * cos(angle), radius * sin(angle)
    return Polygon(((x + dx, y + dy), (x - dy, y + dx),
                    (x - dx, y - dy), (x + dy, y - dx)))


def _nodes(index):
    cx, cy = _CENTRES[index]
    phase = index * 1.19
    inner, outer, anchors = [], [], []
    for j, (ax, ay) in enumerate(_ANCHORS):
        if j not in _MOUNT_RAYS:
            shift = 2.6 * sin(phase + j * 1.71)
            if j in (1, 2, 7, 8):
                ax += shift
            else:
                ay += shift
        angle = atan2(ay - cy, ax - cx)
        a_inner = angle + 0.15 * sin(j * 1.83 + phase)
        a_outer = angle - 0.10 * cos(j * 1.37 - phase)
        r_inner = 18.0 + 4.2 * sin(j * 1.53 + phase) + 0.9 * cos(j * 2.1)
        r_outer = 34.0 + 4.8 * cos(j * 1.61 + phase * 0.81)
        inner.append((cx + r_inner * cos(a_inner), cy + r_inner * 0.98 * sin(a_inner)))
        outer.append((cx + r_outer * cos(a_outer), cy + r_outer * 1.01 * sin(a_outer)))
        anchors.append((ax, ay))
    return inner, outer, anchors


def _network(index):
    inner, outer, anchors = _nodes(index)
    shapes, traces = [], []
    count = len(inner)

    def add(path, width):
        shapes.append(ribbon(path, width, rounded=False))
        traces.append(LineString(path))

    for j, anchor in enumerate(anchors):
        add((anchor, outer[j], inner[j]), 1.76 + 0.12 * sin(j * 1.37 + index * 0.8))
    for j in range(count):
        k = (j + 1) % count
        if j not in _INNER_GAPS[index]:
            mid = _mix(inner[j], inner[k], 0.46)
            bend = (mid[0] + 0.75 * sin(j + index), mid[1] + 0.65 * cos(j * 1.4 - index))
            add((inner[j], bend, inner[k]), 1.57 + 0.07 * cos(j + index))
        if j in _OUTER_LINKS[index]:
            mid = _mix(_mix(outer[j], outer[k], 0.52), _CENTRES[index], 0.045)
            add((outer[j], mid, outer[k]), 1.48)

    # One crossing link breaks the radial rhythm into unequal triangular cells.
    j = (2 + index * 3) % count
    end = _mix(outer[(j + 1) % count], inner[(j + 1) % count], 0.43)
    add((outer[j], end), 1.50)
    for j in range(count):
        angle = atan2(outer[j][1] - inner[j][1], outer[j][0] - inner[j][0])
        shapes.append(_angular_joint(inner[j], angle, 1.20))
        if j in _OUTER_LINKS[index] or (j - 1) % count in _OUTER_LINKS[index]:
            shapes.append(_angular_joint(outer[j], angle, 1.24))
    return unary_union(shapes), traces, inner, outer, anchors


def _art_keepouts():
    # Flat-sided clearances around screw hardware; the real functional holes
    # are the only curves and are added by the common build pipeline.
    holes = [box(x - 3.65, y - 3.65, x + 3.65, y + 3.65) for x, y in SCREWS]
    hx, hy = SLOT_DRILL[0] / 2 + 0.65, SLOT_DRILL[1] / 2 + 0.65
    holes.extend(box(x - hx, y - hy, x + hx, y + hy) for x, y in SLOTS)
    return unary_union(holes)


def _structural_art(body, traces, outer, anchors):
    """Copper rays continue the actual large web over every solid margin."""
    keepouts = _art_keepouts()

    def clip(paths, width):
        safe = body.buffer(-(0.24 + width / 2), join_style=2)
        safe = safe.difference(keepouts.buffer(width / 2, join_style=2))
        return polyline_art(unary_union(paths).intersection(safe), width)

    paths = list(traces)
    for middle, anchor in zip(outer, anchors):
        # This continuation is collinear with the final physical web span.
        far = _mix(middle, anchor, 4.5)
        paths.append(LineString((middle, anchor, far)))

    # Three broad crosslink circuits continue the same rays. Their cells are
    # large and related to the cut geometry, not an independent tiled fill.
    for distance in (0.18, 0.44, 0.76):
        circuit = [_mix(middle, anchor, 1.0 + distance)
                   for middle, anchor in zip(outer, anchors)]
        for j, start in enumerate(circuit):
            end = circuit[(j + 1) % len(circuit)]
            mid = _mix(start, end, 0.48)
            mid = (mid[0] + 0.8 * sin(j * 1.4 + distance),
                   mid[1] + 0.7 * cos(j * 1.7 - distance))
            paths.append(LineString((start, mid, end)))
    strokes = clip(paths, 0.28)

    # Fine copper follows the real void edges and narrow perimeter frame.
    # This ties side margins to the web without introducing a second motif.
    inset = body.buffer(-0.38, join_style=2)
    edges = []
    for polygon in getattr(inset, 'geoms', [inset]):
        edges.extend(LineString(ring.coords) for ring in polygon.interiors)
    if edges:
        strokes.extend(clip(edges, 0.22))
    return strokes


def build():
    envelope = _opening_envelope()
    supports = _mount_material()
    layers = []
    colours = ('black', 'white', 'gold', 'white', 'gold', 'white', 'gold', 'red')
    front_opening = None
    for index, colour in enumerate(colours):
        if index == 7:
            layers.append(make_layer(index, colour, plate(index), solid=True,
                note='切り抜きのない赤い底板。大きな巣の空洞全体を奥で閉じる。'))
            continue
        network, traces, inner, outer, anchors = _network(index)
        body = ensure_polygon(unary_union((
            plate(index).difference(envelope), network, supports,
        )).intersection(plate(index)), f'Spider Nest L{index + 1}')
        for x, y in SCREWS:
            if not body.covers(Point(x, y).buffer(3.05, quad_segs=24)):
                raise ValueError(f'Spider Nest L{index + 1}: mounting support lost')
        artwork = _structural_art(body, traces, outer, anchors) if index == 0 else []
        if index == 0:
            front_opening = plate(0).difference(body)
        layers.append(make_layer(index, colour, body, strokes=artwork,
            note='側面・上下の接続部・4か所の固定部へ巣の帯が直接つながる、広い不規則な開口。'))

    bounds = list(front_opening.bounds)
    ratio = front_opening.area / _PREVIOUS_OPENING_MM2
    if ratio < 1.25:
        raise ValueError(f'Spider Nest opening expansion too small: {ratio:.3f}')
    return {
        'id': 'spider-nest', 'number': '01', 'name': 'Spider Nest',
        'artStyle': 'angular',
        'topPattern': {
            'type': 'structural-web-and-extended-rays', 'coverage': 'full-face',
            'revision': 4, 'motifScale': 'same-large-web-as-the-cutouts',
            'strokeWidthMm': 0.28, 'edgeClearanceMm': 0.24,
        },
        'apertureExpansion': {
            'previousRevision': 3,
            'previousAreaMm2': round(_PREVIOUS_OPENING_MM2, 4),
            'previousBoundsMm': list(_PREVIOUS_BOUNDS),
            'newAreaMm2': round(front_opening.area, 4),
            'newBoundsMm': [round(v, 4) for v in bounds],
            'areaRatio': round(ratio, 4),
            'nominalEnvelopeMm': [2.5, 19.0, 98.8, 109.5],
            'supportRadiusMm': 3.05, 'minimumContinuousEndBridgeMm': 1.9,
        },
        'subtitle': '固定部と側面まで伸びる、大きな立体の蜘蛛の巣',
        'description': '七層の不規則な巣が側面と固定部の近くまで広がる大きな空洞。'
                       '黒い最上層の金線は、その巣の帯と横糸を上下の余白へ延長している。',
        'notes': [
            '第4改訂：開口を側面と固定部の近くまで広げ、角張った不規則な外周で構成した。',
            '8枚構成：黒・白・金・白・金・白・金・赤。最奥は赤い一枚の底板。',
            '4本の巣の帯が固定部へ直接つながる。各固定穴の周囲は半径3.05 mmの支持面を確保した。',
            '下層板の範囲内に開口を収め、全層で上下の連続した接続部を残している。',
            '銅箔は大きな巣の線をそのまま余白へ延長し、開口の縁にも沿わせた平面の金線。',
            '各層で交点と横糸を変え、ほぼ同じ広さの空洞に白と金の帯が重なる。',
            'ENIGは第1・3・5・7層。白い3枚と赤い底板には露出銅箔の模様を設けない。',
        ],
        'layers': layers,
    }
