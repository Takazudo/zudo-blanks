"""Coral Vault: large flowing chambers and changing nested coral openings.

Six large warped cells and a few small pores replace the earlier small grid.
Uneven erosion and two curved septa change each deeper cross-section while
keeping its opening union inside the previous one.  Every PCB is connected.
"""

from math import atan2, ceil, cos, hypot, sin, pi

from shapely import affinity
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union, polylabel

from build_common import (
    H, W, SCREWS, SLOTS, SLOT_DRILL,
    ensure_polygon, make_layer, plate, polyline_art,
)


# Unequal corallites, deliberately placed away from a regular row/column grid.
# Weights are square millimetres.  A continuous warp bends their shared walls.
SEEDS = [
    (37.0, 30.5, 76.0),
    (84.0, 36.0, -5.0),
    (15.8, 62.0, 10.0),
    (62.0, 66.0, 156.0),
    (31.0, 99.0, 38.0),
    (87.0, 99.5, -5.0),
]

FIELD_BOUNDS = (1.4, 17.9, W-1.4, H-17.9)
OPEN_BOUNDS = (2.5, 19.0, W-2.5, H-19.0)
REV3_FRONT_AREA = 4195.819431205

PALETTE = ['black', 'green', 'purple', 'gold', 'red', 'yellow', 'red', 'blue']


def _clip_halfplane(vertices, nx, ny, bound):
    """Clip a convex polygon against nx*x + ny*y <= bound."""
    clipped = []
    if not vertices:
        return clipped
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        da = nx * a[0] + ny * a[1] - bound
        db = nx * b[0] + ny * b[1] - bound
        a_inside, b_inside = da <= 1e-9, db <= 1e-9
        if a_inside:
            clipped.append(a)
        if a_inside != b_inside:
            fraction = da / (da - db)
            clipped.append((a[0] + fraction * (b[0] - a[0]),
                            a[1] + fraction * (b[1] - a[1])))
    return clipped


def _parts(geometry, minimum_area=0.0):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry] if geometry.area >= minimum_area else []
    return [p for part in getattr(geometry, 'geoms', [])
            for p in _parts(part, minimum_area)]


def _warp(x, y):
    """A gentle non-affine deformation, fixed at all four outside edges."""
    x0, y0, x1, y1 = FIELD_BOUNDS
    u, v = (x-x0)/(x1-x0), (y-y0)/(y1-y0)
    envelope = sin(pi*u)*sin(pi*v)
    return (x + envelope*(12.5*sin(2*pi*v+0.6) + 2.2*sin(2*pi*u)),
            y + envelope*(10.5*cos(2*pi*u-0.4) + 1.5*sin(2*pi*v)))


def _flowing_window():
    """Uneven outer lips keep the six large cells from reading as rectangles."""
    x0, y0, x1, y1 = OPEN_BOUNDS
    points = []
    for n in range(97):
        t = n/96
        points.append((x0+(x1-x0)*t, y0+2.4*(0.5+0.5*sin(3*pi*t+0.4))))
    for n in range(97):
        t = n/96
        points.append((x1-1.8*(0.5+0.5*sin(3*pi*t+1.6)), y0+(y1-y0)*t))
    for n in range(97):
        t = 1-n/96
        points.append((x0+(x1-x0)*t, y1-2.4*(0.5+0.5*cos(2.6*pi*t+1.1))))
    for n in range(97):
        t = 1-n/96
        points.append((x0+1.7*(0.5+0.5*sin(3*pi*t+0.1)), y0+(y1-y0)*t))
    return Polygon(points).buffer(0)


def _mount_material():
    """Full support disks joined firmly to the nearest outside frame."""
    pieces = []
    for x, y in SCREWS:
        edge = 0.0 if x < W/2 else W
        pieces.append(Point(x, y).buffer(3.15, quad_segs=24))
        pieces.append(LineString([(edge, y), (x, y)]).buffer(1.85, quad_segs=16))
    return unary_union(pieces)


def _front_chambers():
    x0, y0, x1, y1 = FIELD_BOUNDS
    supports = _mount_material()
    flowing_window = _flowing_window()
    chambers = []
    for i, (x, y, weight) in enumerate(SEEDS):
        vertices = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for j, (other_x, other_y, other_weight) in enumerate(SEEDS):
            if j == i:
                continue
            bound = ((other_x ** 2 + other_y ** 2 - other_weight)
                     - (x ** 2 + y ** 2 - weight)) / 2.0
            vertices = _clip_halfplane(
                vertices, other_x - x, other_y - y, bound,
            )
        dense = []
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            count = max(2, ceil(hypot(b[0]-a[0], b[1]-a[1])/0.80))
            for n in range(count):
                t = n/count
                dense.append(_warp(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
        cell = ensure_polygon(Polygon(dense).buffer(0), 'warped coral cell')
        opening = cell.buffer(-1.10, quad_segs=10)
        pole = polylabel(opening, tolerance=0.10)
        rounding = min(11.0+1.3*(i % 3), pole.distance(opening.boundary)*0.78)
        opening = opening.buffer(-rounding, quad_segs=12).buffer(rounding, quad_segs=12)
        opening = opening.intersection(flowing_window).difference(supports)
        opening = unary_union(_parts(opening, 12.0))
        chambers.append(opening)

    # Secondary corallites inhabit only the broad natural wall junctions.
    # Their clearance is measured from the main cavities, so a pore cannot
    # sever a thin rib or weaken a mechanical support.
    main = unary_union(chambers)
    free = box(*OPEN_BOUNDS).difference(main.buffer(1.85)).difference(supports.buffer(0.8))
    candidates = []
    for region in _parts(free, 12.0):
        pole = polylabel(region, tolerance=0.08)
        radius = pole.distance(region.boundary)
        if radius >= 1.30:
            candidates.append((radius, pole.x, pole.y))
    for i, (radius, x, y) in enumerate(sorted(candidates, reverse=True)[:4]):
        pore = affinity.scale(Point(x, y).buffer(radius*0.88, quad_segs=20),
                              xfact=1.0, yfact=0.77, origin=(x, y))
        pore = affinity.rotate(pore, 23+i*41, origin=(x, y))
        if pore.area >= 8.0:
            chambers.append(pore)
    return chambers


def _boundary_hit(polygon, center, angle):
    """Find a ray's exit from a convex, rounded corallite aperture."""
    direction = (cos(angle), sin(angle))
    ray = LineString([
        center,
        (center[0] + 140.0 * direction[0], center[1] + 140.0 * direction[1]),
    ])
    result = ray.intersection(polygon.boundary)
    if result.geom_type == 'Point':
        point = result
    else:
        points = [g for g in getattr(result, 'geoms', []) if g.geom_type == 'Point']
        if not points:
            return None
        point = max(points, key=lambda p: p.distance(Point(center)))
    return (point.x, point.y), direction


def _curved_septum(component, stage):
    x0, y0, x1, y1 = component.bounds
    width, height = x1-x0, y1-y0
    if stage == 2:
        controls = [(x0-4, y0+height*0.38), (x0+width*0.30, y0+height*0.09),
                    (x0+width*0.66, y0+height*0.89), (x1+4, y0+height*0.62)]
    else:
        controls = [(x0+width*0.28, y0-4), (x0+width*0.05, y0+height*0.34),
                    (x0+width*0.90, y0+height*0.61), (x0+width*0.65, y1+4)]
    points = []
    for n in range(65):
        t = n/64
        weights = [(1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3]
        points.append(tuple(sum(p[k]*w for p, w in zip(controls, weights)) for k in (0, 1)))
    return LineString(points).buffer(0.98, quad_segs=12)


def _shrink_chamber(previous, chamber_index, layer_index):
    """Uneven, direction-dependent inward growth with guaranteed nesting.

    Discs overlap the existing wall, so added PCB material is attached to
    that wall.  Their changing radii produce new lobes and off-centre waists,
    instead of repeating a translated uniformly-offset copy of the opening.
    """
    if previous.is_empty:
        return previous
    next_parts = []
    for component in _parts(previous, 8.0):
        center = component.centroid
        if not component.contains(center):
            center = component.representative_point()
        small_scale = 0.55 + 0.45*min(1.0, component.area/300.0)
        perimeter = component.exterior.length
        samples = max(32, ceil(perimeter/0.55))
        discs = []
        for n in range(samples):
            p = component.exterior.interpolate(perimeter*n/samples)
            angle = atan2(p.y-center.y, p.x-center.x)
            phase = chamber_index*0.83 + layer_index*0.46
            radius = (0.35 + layer_index*0.07
                      + 0.68*(0.5+0.5*sin(2*angle+phase))
                      + 0.95*max(0.0, cos(angle-chamber_index*0.91-layer_index*0.29))**4
                      + 0.25*(0.5+0.5*sin(3*angle-phase*0.71))) * small_scale
            discs.append(p.buffer(radius, quad_segs=7))
        inward = component.buffer(-0.24*small_scale).difference(unary_union(discs))
        # Open morphological rounding stays inside the preceding aperture.
        inward = inward.buffer(-0.24, quad_segs=8).buffer(0.24, quad_segs=8)
        inward = inward.simplify(0.035, preserve_topology=True)
        inward = inward.intersection(component.buffer(-0.16*small_scale))
        if ((layer_index == 2 and chamber_index == 3)
                or (layer_index == 4 and chamber_index == 0)):
            inward = inward.difference(_curved_septum(component, layer_index))
            inward = inward.buffer(-0.24, quad_segs=8).buffer(0.24, quad_segs=8)
        next_parts.extend(_parts(inward, 8.0))
    return unary_union(next_parts)


def _surface_ornament(body):
    """One continuous Favites field over every remaining top-board surface.

    The 8–12 mm cups are generated beyond all four panel edges, then cropped
    only to real PCB material and hardware clearances.  The same field flows
    across upper/lower margins, side frames and the narrow inter-cup walls.
    No label strip, ornamental border or separate band is reserved.
    """
    seeds = []
    for row in range(-2, 17):
        for column in range(-2, 13):
            x = column*10.25 + (row % 2)*4.85 + 1.20*sin(column*1.73 + row*0.81)
            y = row*9.20 + 1.10*cos(column*0.93 + row*1.61)
            weight = 3.2*sin(column*2.01 - row*1.37)
            seeds.append((x, y, weight))

    # Copper is brought close to routed edges while staying on the board.
    # A larger keepout is reserved only around the functional mounting holes.
    screw_keepout = unary_union([Point(p).buffer(4.10, quad_segs=20) for p in SCREWS])
    half_straight = (SLOT_DRILL[0] - SLOT_DRILL[1])/2
    slot_keepout = unary_union([
        LineString([(x-half_straight, y), (x+half_straight, y)]).buffer(
            SLOT_DRILL[1]/2 + 0.85, quad_segs=20,
        )
        for x, y in SLOTS
    ])
    safe = body.buffer(-0.22).difference(screw_keepout.union(slot_keepout))
    clip_for_width = {width: safe.buffer(-width/2-0.02)
                      for width in (0.34, 0.20, 0.22, 0.28)}
    artwork = []

    def draw(geometry, width):
        clipped = geometry.intersection(clip_for_width[width])
        for mark in polyline_art(clipped, width=width):
            if LineString(mark['pts']).length >= 0.16:
                artwork.append(mark)

    for i, (x, y, weight) in enumerate(seeds):
        if x < -8 or x > W+8 or y < -8 or y > H+8:
            continue
        vertices = [(-24.0, -24.0), (W+24.0, -24.0),
                    (W+24.0, H+24.0), (-24.0, H+24.0)]
        for j, (other_x, other_y, other_weight) in enumerate(seeds):
            if i == j:
                continue
            # Only nearby seeds can bound this small staggered-grid cell.
            if (other_x-x)**2 + (other_y-y)**2 > 28.0**2:
                continue
            bound = ((other_x**2 + other_y**2 - other_weight)
                     - (x**2 + y**2 - weight))/2.0
            vertices = _clip_halfplane(vertices, other_x-x, other_y-y, bound)
        for _ in range(2):
            smoothed = []
            for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                smoothed.extend([
                    (a[0]*0.83+b[0]*0.17, a[1]*0.83+b[1]*0.17),
                    (a[0]*0.17+b[0]*0.83, a[1]*0.17+b[1]*0.83),
                ])
            vertices = smoothed
        cup = Polygon(vertices).buffer(-0.35, quad_segs=6)
        cup = cup.buffer(-0.55, quad_segs=6).buffer(0.55, quad_segs=6)
        if cup.is_empty or not cup.intersects(safe):
            continue
        cup = ensure_polygon(cup, 'coral surface motif')
        center = (cup.centroid.x, cup.centroid.y)
        draw(cup.exterior, 0.34)
        inner = affinity.scale(cup, xfact=0.59, yfact=0.54, origin=center)
        draw(inner.exterior, 0.20)
        mouth = affinity.scale(Point(center).buffer(0.38, quad_segs=8),
                               xfact=1.16, yfact=0.84, origin=center)
        draw(mouth.exterior, 0.22)
        spoke_count = 12 + 2*(i % 2)
        for n in range(spoke_count):
            angle = n*2*pi/spoke_count + 0.15*sin(i*0.71) + 0.08*sin(n*1.73+i)
            hit = _boundary_hit(cup, center, angle)
            if hit is None:
                continue
            (bx, by), _ = hit
            remaining = 0.42 if n % 2 == 0 else 0.63
            end = (center[0]+(bx-center[0])*remaining,
                   center[1]+(by-center[1])*remaining)
            draw(LineString([(bx, by), end]), 0.28 if n % 2 == 0 else 0.20)
    return artwork


def build():
    chambers = _front_chambers()
    front_count = len(_parts(unary_union(chambers)))
    layers = []
    opening_areas = []
    opening_counts = []
    opening_bounds = []
    nesting = []
    minimum_insets = []
    previous_union = None
    for index, color in enumerate(PALETTE):
        if index == len(PALETTE) - 1:
            opening = Polygon()
        else:
            if index:
                chambers = [_shrink_chamber(previous, i, index)
                            for i, previous in enumerate(chambers)]
            opening = unary_union(chambers)
        opening_areas.append(round(opening.area, 3))
        opening_counts.append(len(_parts(opening)))
        opening_bounds.append(None if opening.is_empty else [round(v, 3) for v in opening.bounds])
        if previous_union is not None:
            nesting.append(opening.is_empty or previous_union.covers(opening))
            minimum_insets.append(None if opening.is_empty else
                                  round(opening.distance(previous_union.boundary), 3))
        body = ensure_polygon(
            plate(index).difference(opening), f'Coral Vault layer {index + 1}',
        )
        artwork = _surface_ornament(body) if index == 0 else []

        layers.append(make_layer(
            index, color, body, strokes=artwork, solid=index == len(PALETTE)-1,
            note=('大きく流れる空洞と小さな副孔。残る板面全体に平面のENIGサンゴ模様を配置します。'
                  if index == 0 else
                  '青い単色マスクの一体の底板。すべての空洞を閉じます。'
                  if index == 7 else
                  '非対称に狭まった空洞を囲む、全面ENIGの金色層。'
                  if index == 3 else
                  '単色マスクの層。内側へ成長する不均一な壁と曲がった隔壁で、奥の空洞の輪郭を変えます。'),
        ))
        previous_union = opening

    return {
        'id': 'coral-vault',
        'number': '03',
        'name': 'CORAL VAULT',
        'subtitle': '大きなサンゴの空洞が、奥でゆがみ、分かれる',
        'description': ('不規則なサンゴのカップと隔壁を、大きく流れる6つの主空洞と小さな副孔へ抽象化。'
                        '下の層ほど穴を非対称に狭め、途中で曲がった隔壁を加えて、奥の輪郭を変化させます。'),
        'notes': [
            '上から黒・緑・紫・全面ENIG金・赤・黄・赤・青の8枚。青は一体の底板です。',
            f'前面は6つの大きな空洞と副孔を合わせた{front_count}個の開口。下層の外形内で、左右・上下へ大きく広げました。',
            '各層は外周と共有壁でつながる1枚のPCB。固定穴には半径3.15 mmの支持部と外枠への接続を残しています。',
            '奥の開口は必ず手前の開口の内側に収まり、不均一な壁の成長と途中の曲がった隔壁で形が変わります。',
            'ENIGは前面と第4層だけに使用し、他の6枚には露出銅箔アートを設けません。',
            '前面の上下・左右・開口の間を含む全板面に、約8〜12 mmのサンゴ模様を連続して配置します。',
            '模様を避けるのは固定穴周囲の機能上必要な範囲だけ。ラベル帯や幅広の無地の縁は設けません。',
            '曲がった隔壁は基板の形状、板面全体を覆う細い放射状の模様は平面のENIG表現です。',
            '自然の形を抽象化した設計で、色は指定の配色を使っています。',
        ],
        'openingProgression': {
            'method': 'warped-main-chambers / asymmetric-inward-growth / curved-septa',
            'areasMm2': opening_areas,
            'counts': opening_counts,
            'boundsMm': opening_bounds,
            'nestedByStep': nesting,
            'nested': all(nesting),
            'minimumInsetByStepMm': minimum_insets,
            'frontAreaRatioToRev3': round(opening_areas[0]/REV3_FRONT_AREA, 4),
        },
        'sources': [
            {
                'label': 'Corals of the World — Favites pentagona',
                'url': 'https://www.coralsoftheworld.org/species_factsheets/species_factsheet_summary/favites-pentagona/',
            },
            {
                'label': 'Smithsonian Ocean — Corals and Coral Reefs',
                'url': 'https://ocean.si.edu/ocean-life/invertebrates/corals-and-coral-reefs',
            },
        ],
        'layers': layers,
    }
