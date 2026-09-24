"""Asanoha-inspired pierced sheets with strictly planar ENIG facet artwork.

The repeated six-leaf cells are generated from the centre, vertices and
triangle-centre points of a regular hexagon.  Lower sheets retain a connected
hexagonal skeleton while selectively opening cells and shifting the pattern.
"""
from math import cos, sin, pi, sqrt, hypot, floor, ceil

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import triangulate, unary_union

from build_common import (
    W, H, SCREWS, SLOTS, SLOT_DRILL, plate, frame, ribbon, make_layer, fill,
    ensure_polygon,
)


def _polygon_fills(geometry, color=None):
    """Export filled polygons without ever filling a clipped-out inner ring."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        if geometry.interiors:
            return [entry for triangle in triangulate(geometry)
                    for entry in _polygon_fills(triangle.intersection(geometry), color)]
        return [fill(list(geometry.exterior.coords)[:-1], color)]
    if hasattr(geometry, 'geoms'):
        return [entry for part in geometry.geoms
                for entry in _polygon_fills(part, color)]
    return []


def _window():
    """The kumiko opening, including its four corners, is fully angular."""
    return box(10.5, 27.0, W - 10.5, H - 27.0)


def _segments(index, radius=28.0, origin=(22.0, 35.0), region=None):
    # Roughly nine large star centres are visible through the art window.
    phases = [(0, 0), (2.4, 1.3), (-2.2, -0.8),
              (0.6, -2.2), (-1.7, 2.3), (2.0, -1.8),
              (-0.8, 1.8), (1.7, 0.1)]
    dx, dy = phases[index]
    window = (region if region is not None else _window()).buffer(2.0, join_style=2)
    edges = {}

    def add(a, b, kind):
        a, b = tuple(a), tuple(b)
        if not LineString([a, b]).intersects(window):
            return
        key = tuple(sorted((tuple(round(c, 6) for c in a),
                            tuple(round(c, 6) for c in b))))
        edges.setdefault(key, (a, b, kind))

    minx, miny, maxx, maxy = window.bounds
    qmin = floor((minx - origin[0] - dx) / (1.5 * radius)) - 2
    qmax = ceil((maxx - origin[0] - dx) / (1.5 * radius)) + 2
    for q in range(qmin, qmax + 1):
        rmin = floor((miny - origin[1] - dy) / (sqrt(3) * radius) - q / 2) - 2
        rmax = ceil((maxy - origin[1] - dy) / (sqrt(3) * radius) - q / 2) + 2
        for r in range(rmin, rmax + 1):
            center = (origin[0] + 1.5 * radius * q + dx,
                      origin[1] + sqrt(3) * radius * (r + q / 2) + dy)
            vertices = [(center[0] + radius * cos(k * pi / 3),
                         center[1] + radius * sin(k * pi / 3))
                        for k in range(6)]
            cell = Polygon(vertices)
            if not cell.intersects(window):
                continue

            # Adjacent cells share these edges: a continuous support network.
            for k in range(6):
                add(vertices[k], vertices[(k + 1) % 6], 'boundary')

            # A deliberately open rhythm behind the fully developed front.
            # Entire star interiors can be absent without detaching the sheet.
            open_cell = index > 0 and ((2 * q + r + index) % 4 == 0)
            if index >= 4 and (q - r + index) % 5 == 0:
                open_cell = True
            if open_cell:
                continue

            for k in range(6):
                va, vb = vertices[k], vertices[(k + 1) % 6]
                # C, Va and Vb form an equilateral triangle.  Its centre
                # produces the short pointed leaves characteristic of asanoha.
                inner = ((center[0] + va[0] + vb[0]) / 3,
                         (center[1] + va[1] + vb[1]) / 3)
                add(center, va, 'spoke')
                # At depth, two of the six leaf details are opened on selected
                # cells, making the coloured layers legible in large windows.
                if index > 0 and (k + q + r + index) % 3 == 0:
                    continue
                add(center, inner, 'leaf')
                add(inner, va, 'leaf')
                add(inner, vb, 'leaf')
    return list(edges.values())


def _facets(segments, width, body, region=None):
    """A light-facing gold half and a black half, drawn on the same plane.

    Four-point tapers at the ends keep the facet graphics clear at multi-way
    joints.  Nothing in this function modifies the board outline or thickness.
    """
    fills = []
    clip = (region if region is not None else _window()).intersection(
        body.buffer(-0.10, join_style=2))
    for a, b, kind in segments:
        vx, vy = b[0] - a[0], b[1] - a[1]
        length = hypot(vx, vy)
        if length < width * 2:
            continue
        ux, uy = vx / length, vy / length
        nx, ny = -uy, ux
        if nx * (-0.65) + ny * (-0.76) < 0:
            nx, ny = -nx, -ny
        reach = width * 0.38
        inner_inset, outer_inset = width * 0.28, width * 0.66

        def position(origin, advance, across):
            return (origin[0] + ux * advance + nx * across,
                    origin[1] + uy * advance + ny * across)

        light = Polygon([
            position(a, inner_inset, 0.02),
            position(b, -inner_inset, 0.02),
            position(b, -outer_inset, reach),
            position(a, outer_inset, reach),
        ])
        dark = Polygon([
            position(a, inner_inset, -0.035),
            position(a, outer_inset, -reach),
            position(b, -outer_inset, -reach),
            position(b, -inner_inset, -0.035),
        ])
        fills.extend(_polygon_fills(light.intersection(clip)))
        fills.extend(_polygon_fills(dark.intersection(clip), '#15161a'))
    return fills


def _top_safe_surface(body):
    """The entire available face, except edge and mechanical hole clearances.

    The keepouts are polygonal so their intersections do not round decorative
    corners.  The screw keepout is an octagon with a 4.1 mm inradius; the rail
    slot rectangle extends 0.85 mm beyond the slot's complete bounding box.
    Neither function changes a drilled hole or the outline of the PCB.
    """
    screw_radius = 4.1
    octagon_radius = screw_radius / cos(pi / 8)
    keepouts = [Polygon([
        (x + octagon_radius * cos(pi / 8 + k * pi / 4),
         y + octagon_radius * sin(pi / 8 + k * pi / 4))
        for k in range(8)
    ]) for x, y in SCREWS]
    for x, y in SLOTS:
        half_length = SLOT_DRILL[0] / 2 + 0.85
        half_height = SLOT_DRILL[1] / 2 + 0.85
        keepouts.append(box(x - half_length, y - half_height,
                            x + half_length, y + half_height))
    return body.buffer(-0.10, join_style=2).intersection(
        box(0.30, 0.30, W - 0.30, H - 0.30)
    ).difference(unary_union(keepouts))


def _art_union(entries):
    return unary_union([Polygon(item['pts']) for item in entries])


def _top_surface_art(body, window=None):
    """One continuous, aligned asanoha field over every remaining top region.

    The 28 mm physical lattice continues graphically into the solid frame.
    A one-third-scale subdivision fills the same upper/lower/side material;
    both grids use exactly the same origin and angular directions.  There is
    no separate banner, label area or decorative inset frame left blank.
    """
    window = _window() if window is None else window
    safe = _top_safe_surface(body)
    outer_material = safe.difference(window)
    origin = (22.0, 35.0)
    fine_radius = 28.0 / 3
    fine_segments = _segments(0, radius=fine_radius, origin=origin,
                              region=plate(0))
    coarse_segments = _segments(0, radius=28.0, origin=origin,
                                region=plate(0))
    fine = _facets(fine_segments, 1.24, body, outer_material)
    coarse = _facets(coarse_segments, 1.72, body, safe)
    fine_gold = [item for item in fine if not item.get('color')]
    fine_dark = [item for item in fine if item.get('color')]
    coarse_gold = [item for item in coarse if not item.get('color')]
    coarse_dark = [item for item in coarse if item.get('color')]
    # The large lattice's dark facet can cut across fine engraving, while its
    # gold edge remains continuous.  Both halves are flat material artwork.
    artwork = fine_dark + fine_gold + coarse_dark + coarse_gold
    visible_gold = _art_union(fine_gold).difference(_art_union(coarse_dark)).union(
        _art_union(coarse_gold))
    minx, miny, maxx, maxy = window.bounds
    regions = {
        'upper': box(0, 0, W, miny),
        'lower': box(0, maxy, W, H),
        'left': box(0, miny, minx, maxy),
        'right': box(maxx, miny, W, maxy),
        'lattice': window,
    }
    coverage = {}
    for name, region in regions.items():
        area = safe.intersection(region).area
        gold_area = visible_gold.intersection(region).area
        coverage[name] = {
            'availableAreaMm2': round(area, 3),
            'goldAreaMm2': round(gold_area, 3),
            'goldFraction': round(gold_area / area, 4) if area else 0,
        }
    # This measures spaces BETWEEN the engraving lines, not percent gold fill.
    # Samples throughout all usable material catch an accidentally blank band.
    distances = [Point(x / 2, y / 2).distance(visible_gold)
                 for x in range(1, int(W * 2), 4)
                 for y in range(1, int(H * 2), 4)
                 if safe.contains(Point(x / 2, y / 2))]
    report = {
        'scope': 'entire remaining top face',
        'edgeClearanceMm': 0.30,
        'screwKeepoutInradiusMm': 4.1,
        'railSlotExtraClearanceMm': 0.85,
        'coarseHexRadiusMm': 28.0,
        'fineHexRadiusMm': round(fine_radius, 5),
        'availableAreaMm2': round(safe.area, 3),
        'visibleGoldAreaMm2': round(visible_gold.area, 3),
        'visibleGoldFraction': round(visible_gold.area / safe.area, 4),
        'artworkBounds': [round(value, 3) for value in visible_gold.bounds],
        'maxSampleDistanceToGoldMm': round(max(distances), 3),
        'coverageSamplePitchMm': 2.0,
        'goldOutsideSafeAreaMm2': round(visible_gold.difference(safe).area, 9),
        'regions': coverage,
    }
    if any(region['goldAreaMm2'] <= 0 for region in coverage.values()):
        raise ValueError('The continuous top asanoha field misses a face region')
    if visible_gold.difference(safe).area > 1e-7:
        raise ValueError('Top asanoha copper crosses a hole/edge keepout')
    return artwork, report


def build():
    colors = ['black', 'red', 'green'] * 3
    layers = []
    top_coverage = None
    for index, color in enumerate(colors):
        if index == 8:
            layers.append(make_layer(
                index, color, plate(index), solid=True,
                note='緑の底板。組子の穴の最奥を閉じる1枚のPCB。'))
            continue
        segments = _segments(index)
        width = 1.72 if index == 0 else 1.85
        strips = [ribbon([a, b], width, rounded=False)
                  for a, b, kind in segments]
        body = ensure_polygon(
            unary_union([frame(index, _window())] + strips).intersection(plate(index)),
            f'Kumiko Void L{index + 1}',
        )
        if index == 0:
            artwork, top_coverage = _top_surface_art(body)
        else:
            artwork = _facets(segments, width, body) if color == 'black' else []
        layers.append(make_layer(
            index, color, body, fills=artwork,
            note=('六角形の頂点・中心から作る麻の葉格子。金と黒の平面図柄で擬似的な面取りを表現。'
                  if color == 'black' else
                  'セルを選んで開き、格子位置をわずかにずらした連続する1枚のPCB。'),
        ))
    return {
        'id': 'kumiko-void', 'number': '17', 'name': 'Kumiko Void',
        'artStyle': 'angular',
        'subtitle': '麻の葉の格子と、平面の金で作る立体感',
        'description': '最上層の上下・左右・切り抜きの格子まで、残った面全体を連続した麻の葉模様で覆います。黒と金の平面図柄が組子の面取りを表現し、黒・赤・緑の9層が奥行きを作ります。',
        'notes': [
            '手前から黒→赤→緑→黒→赤→緑→黒→赤→緑。最後の緑は穴のない底板。',
            '約28 mmの半径を持つ六角セルを基本に、頂点・中心・三角形の中心を結んだ格子。',
            '金色の明るい側面と黒い暗い側面は同じ高さの印刷・表面処理。実際の段差や傾斜面はありません。',
            '金色の模様は黒の1・4・7枚目だけ。赤と緑の層は単色レジストです。',
            '最上層は上下・左右の外枠から切り抜きの格子まで連続して装飾。外枠の約9.3 mmの麻の葉と28 mmの格子は、原点と線の方向をそろえています。',
            '装飾を避けるのは外周0.3 mmと固定穴・レール取付穴の周囲だけ。文字やラベル用の空白帯は設けていません。',
            '下層は一部セルの内側を開きます。各層は外周と格子がつながった1枚のPCBです。',
        ],
        'topArtworkCoverage': top_coverage,
        'layers': layers,
    }


def _wide_window():
    """A larger cut envelope backed by the shorter lower PCB rectangle."""
    return box(2.5, 19.0, W - 2.5, H - 19.0)


def _wide_mount_supports():
    """Angular screw islands tied directly to the continuous side frame.

    The octagons contain the complete required radius-3.05 support circle.
    The short, flat horizontal ties avoid relying on the incidental position
    of an asanoha rib for a screw island's mechanical connection.
    """
    support_radius = 3.20 / cos(pi / 8)
    supports = []
    for x, y in SCREWS:
        supports.append(Polygon([
            (x + support_radius * cos(pi / 8 + k * pi / 4),
             y + support_radius * sin(pi / 8 + k * pi / 4))
            for k in range(8)
        ]))
        side = 0.0 if x < W / 2 else W
        supports.append(ribbon([(side, y), (x, y)], 2.5, rounded=False))
    return supports


def _aperture_measure(body):
    openings = unary_union([Polygon(ring) for ring in body.interiors])
    return {
        'bounds': [round(value, 4) for value in openings.bounds],
        'areaMm2': round(openings.area, 4),
        'count': len(body.interiors),
    }


def build_wide():
    """The wider-opening variant; build() remains the exact Rev3 standard.

    Pattern radius, phase and planar facet treatment match the original.
    Only this variant expands the cut envelope and its supporting lattice on
    the first eight sheets.  No source body or artwork is reused mutably.
    """
    standard = build()
    window = _wide_window()
    supports = _wide_mount_supports()
    colors = ['black', 'red', 'green'] * 3
    layers = []
    comparisons = []
    top_coverage = None
    for index, color in enumerate(colors):
        if index == 8:
            layers.append(make_layer(
                index, color, plate(index), solid=True,
                note='緑の底板。開口拡大版の最奥を閉じる1枚のPCB。'))
            continue
        segments = _segments(index, region=window)
        width = 1.72 if index == 0 else 1.85
        strips = [ribbon([a, b], width, rounded=False)
                  for a, b, kind in segments]
        body = ensure_polygon(
            unary_union([frame(index, window)] + strips + supports).intersection(plate(index)),
            f'Kumiko Void Wide L{index + 1}',
        )
        if index == 0:
            artwork, top_coverage = _top_surface_art(body, window)
        elif color == 'black':
            artwork = _facets(segments, width, body,
                              window.intersection(_top_safe_surface(body)))
        else:
            artwork = []
        layers.append(make_layer(
            index, color, body, fills=artwork,
            note=('開口を上下左右に広げた麻の葉格子。金と黒の同一平面の図柄で面取りを表現。'
                  if color == 'black' else
                  '開口を広げた連続する1枚のPCB。固定穴の支持部を外枠へ接続。'),
        ))
        old = _aperture_measure(standard['layers'][index]['body'])
        new = _aperture_measure(body)
        comparisons.append({
            'index': index,
            'oldBounds': old['bounds'], 'newBounds': new['bounds'],
            'oldAreaMm2': old['areaMm2'], 'newAreaMm2': new['areaMm2'],
            'areaRatio': round(new['areaMm2'] / old['areaMm2'], 6),
            'oldApertureCount': old['count'], 'newApertureCount': new['count'],
        })
    top = comparisons[0]
    if top['areaRatio'] < 1.25:
        raise ValueError('Wide Kumiko top aperture area must exceed standard by at least25%')
    expansion = {key: top[key] for key in (
        'oldBounds', 'newBounds', 'oldAreaMm2', 'newAreaMm2', 'areaRatio')}
    expansion.update({
        'areaIncreasePercent': round((top['areaRatio'] - 1) * 100, 2),
        'oldWindowBounds': list(_window().bounds),
        'newWindowBounds': list(window.bounds),
        'layers': comparisons,
    })
    return {
        **standard,
        'variantId': 'wide', 'variantLabel': '開口拡大',
        'subtitle': '開口を広げた麻の葉の格子',
        'description': f'標準版の麻の葉模様を保ち、最上層の切り抜き面積を約{expansion["areaIncreasePercent"]:.0f}%拡大。上下左右まで広がる格子の奥に、黒・赤・緑の層が見えます。残る面全体の金と黒の図柄も引き継ぎます。',
        'notes': [
            '標準版と同じ黒→赤→緑を3回繰り返す9枚構成。ENIGは1・4・7枚目だけです。',
            '開口の範囲はx=2.5〜98.8 mm、y=19.0〜109.5 mm。下層PCBの高さの内側に収めています。',
            '約28 mmの麻の葉格子と平らな金・黒の面取り表現を保持。残る外枠にも小さな麻の葉を連続させています。',
            '固定穴の周囲は八角形の支持部を残し、短い帯で左右の外枠へ接続しています。',
            '標準版はそのまま残り、開口拡大版を切り替えて比較できます。',
            '開口のある8枚はそれぞれ外周と格子がつながる1枚のPCBで、9枚目は緑の底板です。',
        ],
        'layers': layers,
        'topArtworkCoverage': top_coverage,
        'apertureExpansion': expansion,
    }
