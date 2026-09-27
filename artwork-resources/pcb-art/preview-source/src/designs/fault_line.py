"""A tall, fractured canyon with alternating eroded and shattered strata.

The opening is deliberately allowed to occupy almost the full lower-board
height.  Its sides reach toward opposing panel edges at different elevations.
Each stratum has independently varying left/right retreat, then is intersected
with the opening above.  This preserves nested voids without making the cliff
walls identical offset copies.  Every remaining board is one connected PCB.
"""
from functools import lru_cache
from math import cos, pi, sin
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from build_common import SCREWS, SLOTS, SLOT_DRILL, plate, make_layer, polyline_art, ensure_polygon


# Independent left and right cliff stations, in ascending y order.  The two
# large lateral breaks occur at different heights, rather than making a
# central square window or a symmetrical star of branches.
LEFT_WALL = [
    (48, 19.4), (41, 21), (39, 25), (29, 29), (32, 33), (17, 36),
    (21, 40), (4, 46), (13, 48), (29, 48.5), (32, 54), (29, 59),
    (38, 62), (32, 68), (23, 71), (29, 76), (14, 79), (27, 83),
    (22, 87), (30, 90), (26, 94), (31, 99), (43, 101), (38, 105),
    (42, 108.9),
]
RIGHT_WALL = [
    (73, 19.4), (77, 23), (85, 26), (75, 31), (80, 34), (73, 39),
    (79, 44), (69, 47), (77, 52), (81, 54), (73, 59), (65, 62),
    (77, 66), (75, 71), (88, 75), (97, 79), (81, 82), (79, 86),
    (67, 89), (76, 94), (71, 98), (63, 100), (69, 105), (67, 108.9),
]
WALL_STYLES = [
    'angular-collapse', 'rounded-erosion', 'angular-collapse', 'rounded-erosion',
    'angular-collapse', 'rounded-erosion', 'angular-collapse', 'rounded-erosion',
]
MINIMUM_STEP_MM = .55
ERODED_CORNER_RADIUS_MM = 3.2


def _wall_x(stations, y, curved):
    for (x0, y0), (x1, y1) in zip(stations, stations[1:]):
        if y <= y1:
            t = max(0., min(1., (y-y0)/(y1-y0)))
            if curved:
                t = (1-cos(pi*t))/2
            return x0 + (x1-x0)*t
    return stations[-1][0]


def _layer_candidate(index):
    if index == 0:
        return Polygon(LEFT_WALL + RIGHT_WALL[::-1])
    # A different retreat on each wall and at each height produces locally
    # broad ledges and narrow ledges.  Alternating interpolation and a 3.2 mm
    # morphological opening visibly mix rounded strata with angular ones.
    y0, y1 = 19.4 + index*.92, 108.9 - index*.79
    ys = {y0+(y1-y0)*j/420 for j in range(421)}
    ys.update(y for _, y in LEFT_WALL+RIGHT_WALL if y0 < y < y1)
    left, right = [], []
    curved = bool(index % 2)
    for y in sorted(ys):
        left_retreat = index*(2.33 + .36*sin(y*.105 + index*.82))
        right_retreat = index*(2.44 + .42*sin(y*.131 - index*.63))
        left.append((_wall_x(LEFT_WALL, y, curved) + left_retreat, y))
        right.append((_wall_x(RIGHT_WALL, y, curved) - right_retreat, y))
    candidate = Polygon(left + right[::-1]).buffer(0)
    if curved:
        candidate = candidate.buffer(-ERODED_CORNER_RADIUS_MM, quad_segs=12).buffer(
            ERODED_CORNER_RADIUS_MM, quad_segs=12)
    return candidate


@lru_cache(maxsize=8)
def fracture(index):
    cut = _layer_candidate(index)
    if index:
        cut = cut.intersection(fracture(index-1).buffer(-MINIMUM_STEP_MM, quad_segs=12))
    # Keep exact nesting; simplifying independently can put an inner corner
    # fractionally outside the previously serialized aperture.
    return cut


def _front_rift():
    return fracture(0)


def _mount_keepouts():
    clearances = [Point(x, y).buffer(4.1, quad_segs=16) for x, y in SCREWS]
    half = (SLOT_DRILL[0] - SLOT_DRILL[1]) / 2
    clearances += [LineString([(x-half, y), (x+half, y)]).buffer(2.45, quad_segs=16)
                   for x, y in SLOTS]
    return unary_union(clearances)


def _crust_art(body):
    # These planar gold strata follow the SAME canyon as the physical opening.
    # The copper field therefore grows out of the central geology, rather
    # than applying an unrelated tile or evenly distributed crack texture.
    safe = body.buffer(-.32, join_style=2).difference(_mount_keepouts())
    art = []
    for step, distance in enumerate([1.05, 2.25, 3.9, 5.25, 7.5, 10.25, 13.5,
                                     17.25, 21.75, 27.0, 33.0, 39.5]):
        width = .31 if step in (0, 4, 8) else .23
        contour = _front_rift().buffer(distance, quad_segs=10).boundary
        art.extend(polyline_art(contour.intersection(safe.buffer(-width/2)), width))
    # Blind-ended fault tears interrupt the contour rhythm at the surviving
    # rock shoulders.  All curves and corners are copper artwork on a flat PCB.
    tears = [
        [(15, 37), (10, 31), (15, 23), (11, 17), (14, 10)],
        [(29, 30), (23, 25), (26, 18), (20, 13), (22, 7)],
        [(40, 22), (34, 18), (36, 11), (30, 5)],
        [(77, 25), (84, 20), (80, 13), (86, 7)],
        [(78, 39), (89, 36), (91, 30)],
        [(28, 54), (19, 59), (14, 56), (8, 61), (2, 58)],
        [(73, 61), (84, 60), (87, 54), (94, 51), (100, 53)],
        [(23, 74), (13, 69), (8, 73), (2, 71)],
        [(26, 91), (18, 96), (20, 105), (14, 112), (18, 121)],
        [(42, 106), (31, 112), (35, 119), (27, 127)],
        [(69, 106), (78, 111), (73, 118), (81, 126)],
        [(74, 91), (88, 94), (91, 99)],
    ]
    for points in tears:
        art.extend(polyline_art(LineString(points).intersection(safe.buffer(-.125)), .25))
    return art


def _offset_comparison(previous, cut):
    """Difference from a uniform inward offset having the same aperture area.

    A nonzero ratio is independent evidence that the new stratum is not just
    the previous aperture moved inward by one constant distance.
    """
    lo, hi = 0., 12.
    for _ in range(20):
        mid = (lo+hi)/2
        if previous.buffer(-mid, quad_segs=8).area > cut.area:
            lo = mid
        else:
            hi = mid
    distance = (lo+hi)/2
    offset = previous.buffer(-distance, quad_segs=8)
    return {'equivalentOffsetMm': round(distance, 4),
            'differenceAreaMm2': round(offset.symmetric_difference(cut).area, 3),
            'differenceFraction': round(offset.symmetric_difference(cut).area/cut.area, 5)}


def build():
    layers, previous, areas, openings, comparisons = [], None, [], [], []
    for index in range(9):
        color = 'black' if index % 2 == 0 else 'red'
        if index == 8:
            layers.append(make_layer(index, color, plate(index), solid=True,
                                    note='露出銅箔のない黒い底板。崩落した峡谷の最奥を閉じる。'))
            continue
        cut = fracture(index)
        if previous is not None:
            if cut.difference(previous).area > 1e-7 or cut.area >= previous.area:
                raise ValueError(f'Fault Line L{index+1}: rifts must shrink within the previous layer')
            comparisons.append({'index': index, **_offset_comparison(previous, cut)})
        previous = cut
        areas.append(round(cut.area, 2))
        openings.append(len(cut.geoms) if hasattr(cut, 'geoms') else 1)
        body = ensure_polygon(plate(index).difference(cut), f'Fault Line L{index+1}')
        layers.append(make_layer(index, color, body,
                      strokes=_crust_art(body) if index == 0 else [],
                      note=('上下に大きく裂け、左右の異なる高さへ広がる峡谷。表面の金の地形線も崖から外側へ続く。'
                            if index == 0 else
                            '丸く侵食した赤い崖。場所ごとに異なる幅で後退し、角張った黒い層と交互に現れる。'
                            if index % 2 else
                            '角張った黒い崖。上の開口の内側で不規則に後退する単色PCB。')))
    front = _front_rift()
    x0, y0, x1, y1 = front.bounds
    return {
        'id': 'fault-line', 'number': '13', 'name': 'Fault Line',
        'subtitle': '角張る岩盤と侵食した崖が交互に崩れる、大きな赤黒の峡谷',
        'description': '中央に収まる地割れを、上下約90 mmに及ぶ幅広い非対称の峡谷へ拡張しました。左右の崖は層ごと・場所ごとに異なる幅で後退し、鋭い破断面と丸く侵食した壁が交互に重なります。',
        'artStyle': 'angular',
        'openingProgression': {
            'nested': True, 'method': 'independent-wall-retreat-with-nested-clipping',
            'minimumStepMm': MINIMUM_STEP_MM, 'areasMm2': areas,
            'apertureCounts': openings, 'frontBoundsMm': [x0, y0, x1, y1],
            'frontWidthMm': round(x1-x0, 2), 'frontHeightMm': round(y1-y0, 2),
            'wallStyles': WALL_STYLES,
            'roundedCornerRadiusMm': ERODED_CORNER_RADIUS_MM,
            'uniformOffsetComparisons': comparisons,
        },
        'crackNetwork': {
            'style': 'full-height-collapsed-canyon', 'mainRift': 1,
            'sideBays': 'asymmetric at different elevations',
            'reference': 'user-provided original Fault Line concept',
            'topArtwork': 'canyon-following strata and blind-ended fault tears',
        },
        'notes': [
            'トップの開口は幅93.0 ×高さ89.5 mm。左右の張り出しを別々の高さへ伸ばした非対称の峡谷です。',
            '黒い層は角張った崖、赤い層は丸く侵食した崖。左右・高さ・深さによって後退量も変わります。',
            '各段の穴は手前の穴の内側に収まり、奥ほど面積が減少します。最奥の細い通路は分断して閉じます。',
            'トップの金の地形線は、実際の崖の輪郭から外側へ続きます。',
            '全層で外周と上下の橋を残しています。岩盤は各層内でつながり、独立した破片はありません。',
            'ENIGはトップのみ。第2〜9層は黒・赤の単色で、最奥は黒い底板です。',
        ],
        'layers': layers,
    }
