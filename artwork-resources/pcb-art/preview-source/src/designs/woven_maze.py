"""Wide orthogonal PCB ribbons: the weave is formed by separate flat sheets."""
from shapely.ops import unary_union

from shapely.geometry import LineString, Point, Polygon, box

from build_common import W, H, KEEP_OUT, SCREWS, art_window, plate, frame, ribbon, make_layer, ensure_polygon, stroke, fill


# Route families use the same 15–16 mm grid rhythm to leave common sightlines,
# but their connectivity, branches, loops and rooms are drawn independently.
# Each route reaches the perimeter or joins another connected route in THIS
# sheet.  No lower sheet is a translated copy of another sheet.
MAZES = [
    {
        'id': 'front-weave', 'name': 'Front Weave', 'nameJa': '手前の編み込み',
        'width': 4.5,
        'routes': [
            [(-3, 40), (33, 40), (33, 55), (82, 55), (82, 38), (105, 38)],
            [(-3, 77), (20, 77), (20, 94), (52, 94), (52, 72), (79, 72), (79, 114)],
            [(58, 15), (58, 30), (75, 30), (75, 43)],
        ],
    },
    {
        'id': 'stair-and-fork', 'name': 'Stair & Fork', 'nameJa': '段状経路と分岐',
        'width': 3.85,
        'routes': [
            [(34, 15), (34, 34), (50, 34), (50, 49), (66, 49), (66, 79), (82, 79), (82, 114)],
            [(-3, 64), (34, 64), (34, 94), (66, 94), (66, 114)],
            [(50, 49), (20, 49), (20, 34), (-3, 34)],
            [(34, 79), (50, 79), (50, 64)],
        ],
    },
    {
        'id': 'double-courtyard', 'name': 'Double Courtyard', 'nameJa': '二つの中庭',
        'width': 3.50,
        'routes': [
            [(20, 34), (66, 34), (66, 64), (20, 64), (20, 34)],
            [(20, 34), (20, 15)],
            [(34, 79), (82, 79), (82, 94), (34, 94), (34, 79)],
            [(82, 79), (105, 79)],
            [(34, 79), (34, 64)],
            [(66, 49), (82, 49), (82, 34), (105, 34)],
        ],
    },
    {
        'id': 'branched-spine', 'name': 'Branched Spine', 'nameJa': '幹から広がる経路',
        'width': 3.70,
        'routes': [
            [(20, 15), (20, 49), (50, 49), (50, 94), (82, 94), (82, 114)],
            [(50, 49), (82, 49), (82, 34), (66, 34), (66, 15)],
            [(50, 64), (34, 64), (34, 79), (-3, 79)],
            [(50, 79), (66, 79), (66, 64), (105, 64)],
        ],
    },
    {
        'id': 'nested-hook', 'name': 'Nested Hook', 'nameJa': '内側へ折り返す経路',
        'width': 3.40,
        'routes': [
            [(-3, 34), (82, 34), (82, 94), (20, 94), (20, 49), (66, 49), (66, 79), (34, 79), (34, 64), (50, 64)],
            [(82, 64), (105, 64)],
            [(20, 79), (-3, 79)],
        ],
    },
    {
        'id': 'cross-canal', 'name': 'Cross Canal', 'nameJa': '交差する水路',
        'width': 3.55,
        'routes': [
            [(-3, 49), (34, 49), (34, 64), (66, 64), (66, 49), (105, 49)],
            [(50, 15), (50, 34), (20, 34), (20, 79), (50, 79), (50, 114)],
            [(82, 15), (82, 34), (66, 34), (66, 49)],
            [(66, 64), (66, 94), (82, 94), (82, 79), (105, 79)],
        ],
    },
    {
        'id': 'split-gates', 'name': 'Split Gates', 'nameJa': '左右に分かれた門',
        'width': 3.80,
        'routes': [
            [(34, 15), (34, 34), (20, 34), (20, 79), (50, 79), (50, 114)],
            [(66, 15), (66, 49), (82, 49), (82, 94), (66, 94), (66, 79), (105, 79)],
            [(20, 64), (50, 64), (50, 49), (34, 49)],
            [(50, 79), (66, 79)],
            [(-3, 94), (34, 94), (34, 79)],
        ],
    },
    {
        'id': 'diagonal-ladder', 'name': 'Diagonal Ladder', 'nameJa': '斜めに連なる段差',
        'width': 3.25,
        'routes': [
            [(-3, 94), (20, 94), (20, 79), (34, 79), (34, 64), (50, 64), (50, 49), (66, 49), (66, 34), (82, 34), (82, 15)],
            [(20, 79), (20, 49), (-3, 49)],
            [(34, 64), (34, 34), (50, 34), (50, 15)],
            [(50, 49), (82, 49), (82, 79), (105, 79)],
            [(34, 79), (66, 79), (66, 94), (105, 94)],
        ],
    },
]


OLD_BOUNDS = (10.5, 27.0, W - 10.5, H - 27.0)
OPEN_BOUNDS = (2.5, 19.0, W - 2.5, 109.5)
SUPPORT_RADIUS = 4.3


def _expanded_window():
    """Use the full supported area, with four shoulders around the screws.

    Each rounded shoulder joins BOTH adjacent outer-frame edges.  It cannot
    become an isolated mounting island, and the lower plate retains a thin
    continuous 1.9 mm strip along its top and bottom edges.
    """
    shoulders = []
    for x, y in SCREWS:
        left, upper = x < W / 2, y < H / 2
        circle = Point(x, y).buffer(SUPPORT_RADIUS, quad_segs=12)
        if left and upper:
            north = box(0, KEEP_OUT, x + SUPPORT_RADIUS, y)
            side = box(0, y, x, y + SUPPORT_RADIUS)
        elif not left and upper:
            north = box(x - SUPPORT_RADIUS, KEEP_OUT, W, y)
            side = box(x, y, W, y + SUPPORT_RADIUS)
        elif left:
            north = box(0, y, x + SUPPORT_RADIUS, H - KEEP_OUT)
            side = box(0, y - SUPPORT_RADIUS, x, y)
        else:
            north = box(x - SUPPORT_RADIUS, y, W, H - KEEP_OUT)
            side = box(x, y - SUPPORT_RADIUS, W, y)
        shoulders.append(unary_union([circle, north, side]))
    return ensure_polygon(box(*OPEN_BOUNDS).difference(unary_union(shoulders)),
                          'Woven Maze expanded window')


def _expand_point(point):
    x, y = point
    x0, y0, x1, y1 = OLD_BOUNDS
    nx0, ny0, nx1, ny1 = OPEN_BOUNDS
    return (nx0 + (x - x0) * (nx1 - nx0) / (x1 - x0),
            ny0 + (y - y0) * (ny1 - ny0) / (y1 - y0))


def _tracks(index):
    # Keep Rev3's seven distinct graphs; enlarge their coordinate domain.
    return [[_expand_point(point) for point in route]
            for route in MAZES[index]['routes']]


def _turn_count(routes):
    """Count the specified right-angle bends, including closed-loop corners."""
    turns = 0
    for route in routes:
        points = route + [route[1]] if route[0] == route[-1] else route
        for a, b, c in zip(points, points[1:], points[2:]):
            u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            turns += int(abs(u[0] * v[1] - u[1] * v[0]) > 1e-8)
    return turns


def _margin_ornament(body):
    """An orthogonal meander band on each solid margin of the front PCB."""
    path = [(12.8, 9.6)]
    for cell in range(6):
        x = 12.8 + 12.6 * cell
        path.extend([(x + 3.0, 9.6), (x + 3.0, 17.8),
                     (x + 8.8, 17.8), (x + 8.8, 12.2),
                     (x + 12.6, 12.2), (x + 12.6, 9.6)])
    paths = [(path, 0.64), ([(12.8, 21.0), (88.4, 21.0)], 0.22)]
    for cell in range(7):
        x = 12.8 + 12.6 * cell
        paths.append(([(x, 19.7), (x, 21.0)], 0.22))
    artwork = []
    drawing_surface = body.buffer(-0.18, join_style=2)
    for points, width in paths:
        # Compress the ornament into the remaining solid margin.  The lower
        # edge now stops at y=17 mm, safely above the expanded opening at y=19.
        upper = [(x, 8.0 + (y - 9.6) * 9.0 / 11.4) for x, y in points]
        for line in (upper, [(x, H - y) for x, y in upper]):
            shape = LineString(line).buffer(width / 2, cap_style=2, join_style=2).intersection(drawing_surface)
            pieces = list(shape.geoms) if hasattr(shape, 'geoms') else [shape]
            for piece in pieces:
                if piece.geom_type == 'Polygon' and not piece.is_empty:
                    artwork.append(fill(list(piece.exterior.coords)[:-1]))
    return artwork


def build():
    colors = ['black', 'white', 'black', 'white', 'black',
              'white', 'black', 'white', 'black']
    layers = []
    window = _expanded_window()
    for index, color in enumerate(colors):
        if index == 8:
            layers.append(make_layer(
                index, color, plate(index), solid=True,
                note='黒の底板。通路の隙間に見える暗い最奥面。'))
            continue
        # Individually designed paths on a common lane rhythm keep broad
        # windows through the stack instead of filling every possible opening.
        width = MAZES[index]['width']
        strips = [ribbon(path, width, rounded=False)
                  for path in _tracks(index)]
        body = ensure_polygon(
            unary_union([frame(index, window)] + strips).intersection(plate(index)),
            f'Woven Maze L{index + 1}',
        )
        # Offset into the material (away from each aperture) so the full
        # pinstripe lies on PCB.  These remain flat surface graphics.
        pinstripes, ornament = [], []
        if index == 0:
            inset = body.buffer(-0.34, join_style=2)
            pieces = list(inset.geoms) if hasattr(inset, 'geoms') else [inset]
            pinstripes = [stroke(list(hole.coords)[:-1], 0.22, closed=True)
                          for piece in pieces for hole in piece.interiors]
            ornament = _margin_ornament(body)
        layers.append(make_layer(
            index, color, body, strokes=pinstripes, fills=ornament,
            note=f"{MAZES[index]['nameJa']}。幅{width:g} mmの直角の帯が、このPCBの面内で外周へつながります。",
        ))
    through = window.difference(unary_union([layer['body'] for layer in layers[:-1]]))
    through_fraction = through.area / window.area
    if through_fraction < 0.15:
        raise ValueError(f'Woven Maze: only {through_fraction:.1%} projected opening remains through the stack')
    maze_layers = [
        {'index': i, 'id': maze['id'], 'name': maze['name'], 'nameJa': maze['nameJa'],
         'widthMm': maze['width'], 'routeCount': len(maze['routes']),
         'turnCount': _turn_count(maze['routes']), 'apertures': len(layers[i]['body'].interiors)}
        for i, maze in enumerate(MAZES)
    ]
    # Regenerate the original Rev3 top shape from its preserved routes.  This
    # comparison uses true apertures, excluding mount/rail holes, and remains
    # reproducible without loading an external snapshot or previous build.
    old_window = art_window()
    old_strips = [ribbon(route, MAZES[0]['width'], rounded=False)
                  for route in MAZES[0]['routes']]
    old_body = unary_union([frame(0, old_window)] + old_strips).intersection(plate(0))
    old_apertures = unary_union([Polygon(hole) for hole in old_body.interiors])
    new_apertures = unary_union([Polygon(hole) for hole in layers[0]['body'].interiors])
    expansion = {
        'referenceRevision': 3,
        'oldBounds': [round(v, 4) for v in old_apertures.bounds],
        'newBounds': [round(v, 4) for v in new_apertures.bounds],
        'oldWindowBounds': list(OLD_BOUNDS),
        'newWindowBounds': list(OPEN_BOUNDS),
        'oldApertureAreaMm2': round(old_apertures.area, 2),
        'newApertureAreaMm2': round(new_apertures.area, 2),
        'areaRatio': round(new_apertures.area / old_apertures.area, 4),
        'increasePercent': round((new_apertures.area / old_apertures.area - 1) * 100, 2),
        'lowerRimMm': {'side': 2.5, 'top': 1.9, 'bottom': 1.9},
        'supportRadiusMm': SUPPORT_RADIUS,
        'routeScale': {'x': (OPEN_BOUNDS[2] - OPEN_BOUNDS[0]) / (OLD_BOUNDS[2] - OLD_BOUNDS[0]),
                       'y': (OPEN_BOUNDS[3] - OPEN_BOUNDS[1]) / (OLD_BOUNDS[3] - OLD_BOUNDS[1])},
    }
    return {
        'id': 'woven-maze', 'number': '18', 'name': 'Woven Maze',
        'subtitle': '黒と白の直角の帯を、異なる深さで重ねる',
        'description': '黒と白を交互に重ねる9枚構成。四隅の固定部を残して開口を外周近くまで広げ、手前の編み込みと七つの異なる迷路を大きく見せます。最奥は黒い底板で、すべての帯は各PCBの面内で外周へつながっています。',
        'notes': [
            '手前から黒→白を4回繰り返し、9枚目の黒い底板で閉じます。',
            '帯の幅は最上層が4.5 mm、下の迷路が3.25〜3.85 mm。金色の細い縁と上下余白の迷路模様は最上層だけの平面ENIG図柄です。',
            '2〜9枚目は金色の模様を持たない単色レジスト。白い層にも金色の縁は付けません。',
            '2〜8枚目は段状経路・二つの中庭・分岐する幹・内側への折り返し・交差水路・左右の門・斜めの梯子という別々の迷路。位置をずらした複製ではありません。',
            f'開口領域はx=2.5〜98.8、y=19〜109.5 mm。前のモデルよりトップの実際の穴の面積を約{expansion["increasePercent"]:.0f}%広げました。',
            f'迷路の経路を約1.2倍の範囲に展開。分解なしの正面投影でも開口領域の約{through_fraction * 100:.0f}%から底板まで見通せます。',
            '左右2.5 mm、下層の上下1.9 mmの連続した外周と、四隅の張り出した固定部を残しています。',
            '帯が曲がるのは各PCBの面内だけです。交差の上下関係は1.6 mmの板と3 mmの層間で生まれます。',
            'すべての帯が各層の外周につながり、1層が1枚のPCBとして成立します。',
        ],
        'mazeLayers': maze_layers,
        'apertureExpansion': expansion,
        'throughOpening': {'areaMm2': round(through.area, 2), 'fraction': round(through_fraction, 4)},
        'layers': layers,
    }
