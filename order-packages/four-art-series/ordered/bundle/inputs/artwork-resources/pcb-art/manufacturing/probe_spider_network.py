#!/usr/bin/env python3
"""Bound a complete Spider material proposal; do not emit production artwork."""
import hashlib
import json
import math
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NEW_STROKES = [2, 3, 4, 5, 6, 9, 10, 15, 16, 17, 18, 25, 27, 31, 34, 36, 39]
# Negative/positive normal sides, in each approved central path's direction.
GUIDES = {2: [104, 109], 3: [105, 106], 4: [98, 104], 5: [103, 105],
          6: [95, 98], 7: [101, 98], 8: [101, 103], 9: [96, 95],
          10: [100, 101], 15: [103, 99], 16: [103, 102], 17: [108, 103],
          18: [107, 103], 25: [106, 103], 27: [105, 103], 31: [100, 103],
          34: [102, 103], 36: [107, 103], 39: [110, 103]}
SOURCE_SHA = '00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def normsha(geometry):
    return digest(shapely.normalize(geometry).wkb)


def coordsha(points):
    return digest(json.dumps(points, separators=(',', ':')).encode())


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    return [p for child in getattr(geometry, 'geoms', []) for p in polygons(child)]


def frame(a, b):
    length = math.dist(a, b)
    u = ((b[0]-a[0])/length, (b[1]-a[1])/length)
    return length, u, (-u[1], u[0])


def intervals(region, section, midpoint, normal):
    intersection = region.intersection(section)
    pieces = getattr(intersection, 'geoms', [intersection])
    result = []
    for piece in pieces:
        if piece.geom_type != 'LineString' or piece.length < 1e-7:
            continue
        values = [(x-midpoint[0])*normal[0]+(y-midpoint[1])*normal[1]
                  for x, y in piece.coords]
        result.append((min(values), max(values)))
    return sorted(result)


def survey(top, snapshot):
    """Index sustained runs, not acute tips, on every original radial segment."""
    body = shapely.from_wkb(bytes.fromhex(snapshot['bodyWkbHex']))
    gold = shapely.from_wkb(bytes.fromhex(snapshot['goldWkbHex']))
    ink_parts = sorted(polygons(body.difference(gold)), key=lambda p: -p.area)
    ink_tree = STRtree(ink_parts)
    guide_lines = [LineString(s['pts']) for s in snapshot['guideCenterlines']]
    guide_tree = STRtree(guide_lines)
    runs = []
    for index, stroke in enumerate(top['art']['strokes'][:95]):
        for segment, (a, b) in enumerate(zip(stroke['pts'], stroke['pts'][1:])):
            length, u, n = frame(a, b)
            if length < 1:
                continue
            count = max(2, math.ceil(length/.2))
            step = length/count
            samples = []
            for j in range(count):
                distance = (j+.5)*step
                m = (a[0]+u[0]*distance, a[1]+u[1]*distance)
                section = LineString([(m[0]-2*n[0], m[1]-2*n[1]),
                                      (m[0]+2*n[0], m[1]+2*n[1])])
                spans = intervals(gold, section, m, n)
                central = next((k for k, (lo, hi) in enumerate(spans) if lo < 0 < hi), None)
                row = {}
                if central is not None and spans[central][1]-spans[central][0] <= .31:
                    material = next(hi-lo for lo, hi in intervals(body, section, m, n) if lo < 0 < hi)
                    for side in (-1, 1):
                        other = central+side
                        if not 0 <= other < len(spans):
                            continue
                        lo, hi = ((spans[central][1], spans[other][0]) if side == 1
                                  else (spans[other][1], spans[central][0]))
                        if not 1e-6 < hi-lo < .25:
                            continue
                        center = (lo+hi)/2
                        hits = ink_tree.query(Point(m[0]+center*n[0], m[1]+center*n[1]), predicate='intersects')
                        if len(hits) != 1:
                            continue
                        outer = sum(spans[other])/2
                        guide = int(guide_tree.nearest(Point(m[0]+outer*n[0], m[1]+outer*n[1])))
                        row[side] = {'width': hi-lo, 'body': material,
                                     'guide': snapshot['guideCenterlines'][guide]['sourceStrokeIndex0'],
                                     'ink': int(hits[0])}
                samples.append(row)
            for threshold in (.13, .25):
                for side in (-1, 1):
                    start = None
                    last = None
                    for j in range(count+1):
                        value = samples[j].get(side) if j < count else None
                        key = (value['guide'], value['ink']) if value and value['width'] < threshold else None
                        if start is not None and key != last:
                            if (j-start)*step >= 1:
                                values = [samples[k][side] for k in range(start, j)]
                                runs.append({'sourceStrokeIndex0': index, 'sourceSegmentIndex0': segment,
                                             'side': side, 'thresholdMm': threshold,
                                             'guideStrokeIndex0': last[0],
                                             'inkComponentNormalizedWkbSha256': normsha(ink_parts[last[1]]),
                                             'distanceAlongSegmentMm': [start*step, j*step],
                                             'sampleSpacingMm': step, 'lengthMm': (j-start)*step,
                                             'widthRangeMm': [min(v['width'] for v in values), max(v['width'] for v in values)],
                                             'minimumSampledMaterialWidthMm': min(v['body'] for v in values)})
                            start = None
                        if key is not None and start is None:
                            start, last = j, key
    return {'method': 'normal sections <=0.20 mm apart; >=1 mm sustained run; central gold <=0.31 mm; not a full width certificate',
            'interiorRuns': [r for r in runs if r['sourceStrokeIndex0'] < 43],
            'rimTransitionFlags': [r for r in runs if r['sourceStrokeIndex0'] >= 43]}


def guide_portions(top):
    """Freeze exact approved guide edges and finite nominal relocation endpoints."""
    result = []
    for central, guide_ids in GUIDES.items():
        points = top['art']['strokes'][central]['pts']
        for segment, (a, b) in enumerate(zip(points, points[1:])):
            length, u, n = frame(a, b)
            for side, guide in zip((-1, 1), guide_ids):
                hits = []
                guide_points = top['art']['strokes'][guide]['pts']
                for edge, (c, d) in enumerate(zip(guide_points, guide_points[1:])):
                    gl, gu, _ = frame(c, d)
                    if gl < 1 or abs(gu[0]*u[0]+gu[1]*u[1]) < .9999:
                        continue
                    offsets = [(v[0]-a[0])*n[0]+(v[1]-a[1])*n[1] for v in (c, d)]
                    ts = [(v[0]-a[0])*u[0]+(v[1]-a[1])*u[1] for v in (c, d)]
                    lo, hi = max(min(ts), 0), min(max(ts), length)
                    if hi-lo < 1 or max(abs(v) for v in offsets) > .8:
                        continue
                    original = [[c[k]+(d[k]-c[k])*(t-ts[0])/(ts[1]-ts[0]) for k in (0, 1)] for t in (lo, hi)]
                    proposed = [[a[k]+t*u[k]+side*.5165*n[k] for k in (0, 1)] for t in (lo, hi)]
                    reach = max(math.dist(v, w) for v, w in zip(original, proposed))
                    assert reach <= .5
                    hits.append({'centralStrokeIndex0': central, 'centralSegmentIndex0': segment,
                                 'guideStrokeIndex0': guide, 'originalGuideEdgeIndex0': edge,
                                 'originalGuideContourSha256': coordsha(guide_points),
                                 'originalEdgeMm': [c, d], 'originalPortionMm': original,
                                 'distanceAlongCentralSegmentMm': [lo, hi], 'side': side,
                                 'nominalCenterOffsetMm': side*.5165, 'nominalRelocatedPortionMm': proposed,
                                 'maximumNominalDisplacementMm': reach})
                assert len(hits) == 1, (central, segment, guide, hits)
                result.extend(hits)
    return result


def measure(include_survey=True):
    source_raw = (ROOT/'preview-source/assets/geometry.json').read_bytes()
    assert digest(source_raw) == SOURCE_SHA
    source = json.loads(source_raw)
    top = next(d for d in source['designs'] if d['id'] == 'spider-nest')['layers'][0]
    prior_raw = (HERE/'spider-channel-erratum.json').read_bytes()
    prior = json.loads(prior_raw)
    before = shapely.from_wkb(bytes.fromhex(prior['candidateBodyWkbHex']))
    snapshot_raw = (HERE/'spider-network-input.json').read_bytes()
    snapshot = json.loads(snapshot_raw)
    assert snapshot['approvedSourceSha256'] == SOURCE_SHA
    paths = [{'sourceStrokeIndices0': [i], 'pointsMm': top['art']['strokes'][i]['pts']}
             for i in NEW_STROKES]
    # One continuous mitered path preserves the earlier 7/8 ribbon exactly.
    paths.append({'sourceStrokeIndices0': [7, 8], 'pointsMm': top['art']['strokes'][7]['pts']+top['art']['strokes'][8]['pts'][1:]})
    for path in paths:
        path['coordinatesSha256'] = coordsha(path['pointsMm'])
    ribbons = unary_union([LineString(p['pointsMm']).buffer(1, cap_style='flat', join_style='mitre') for p in paths])
    initial = before.union(ribbons)
    initial_delta = initial.difference(before)
    screws = [Point(x, y).buffer(1.6, quad_segs=128) for x, y in source['spec']['screws']]
    slots = [LineString([(x-3.54, y), (x+3.54, y)]).buffer(1.6, quad_segs=128) for x, y in source['spec']['slots']]
    functional = unary_union(screws+slots)
    centers = [Point(x, y) for x, y in source['spec']['screws']+source['spec']['slots']]
    original_holes = [(i, Polygon(h)) for i, h in enumerate(top['holes']) if not any(Polygon(h).covers(c) for c in centers)]
    affected = [i for i, q in original_holes if q.intersection(initial_delta).area > 1e-5]
    apertures = [Polygon(r) for r in initial.interiors if not any(Polygon(r).covers(c) for c in centers)]
    cleanup = []
    tool_rows = []
    for aperture in apertures:
        index, original = max(original_holes, key=lambda pair: aperture.intersection(pair[1]).area)
        tool_centers = aperture.buffer(-.5, quad_segs=64)
        assert len(polygons(tool_centers)) == 1 and not tool_centers.is_empty
        swept = tool_centers.buffer(.5, quad_segs=64).intersection(aperture)
        delta = aperture.difference(swept) if index in affected else Polygon()
        final_aperture = aperture.difference(delta)
        final_centers = final_aperture.buffer(-.5, quad_segs=64)
        assert len(polygons(final_centers)) == 1 and not final_centers.is_empty
        plunge = final_centers.representative_point()
        cleanup.append(delta)
        tool_rows.append({'originalGeometryHoleIndex0': index,
                          'originalContourSha256': coordsha(top['holes'][index]),
                          'initialApertureNormalizedWkbSha256': normsha(aperture),
                          'toolCenterComponents': len(polygons(tool_centers)),
                          'finalToolCenterComponents': len(polygons(final_centers)),
                          'plungeCenterMm': list(plunge.coords)[0],
                          'plungeDiskOutsideApertureAreaMm2': plunge.buffer(.5, quad_segs=64).difference(final_aperture).area,
                          'cleanupAreaMm2': delta.area, 'cleanupNormalizedWkbSha256': normsha(delta),
                          'finalApertureNormalizedWkbSha256': normsha(final_aperture)})
    cleanup_delta = unary_union(cleanup)
    final = initial.union(cleanup_delta)
    final_decor = [Polygon(r) for r in final.interiors if not any(Polygon(r).covers(c) for c in centers)]
    original_area = sum(q.area for _, q in original_holes)
    loss = 1-sum(q.area for q in final_decor)/original_area
    # Additions preserve already-proven ligaments and the lower floor; directly
    # check the remaining invariants rather than relying on that inference.
    checks = {
        'validOnePieceAfterDrilling': final.is_valid and final.geom_type == 'Polygon',
        'outerBoundsUnchanged': final.bounds == before.bounds,
        'noMaterialRemoval': before.difference(final).area < 1e-5,
        'functionalDrillsUnchanged': final.difference(before).intersection(functional).area < 1e-5,
        'holeCountUnchanged': len(final.interiors) == len(before.interiors),
        'nineteenDecorativeApertures': len(final_decor) == 19,
        'supportDisksBeforeDrilling': all(final.union(functional).buffer(1e-6).covers(Point(x, y).buffer(3.05, quad_segs=128)) for x, y in source['spec']['screws']),
        'continuousUpperLowerBridges': final.covers(box(0, 0, 101.3, 1)) and final.covers(box(0, 127.5, 101.3, 128.5)),
        'topAperturesBacked': all(q.difference(box(0, 17.1, 101.3, 111.4)).area < 1e-5 for q in final_decor),
        'apertureLossWithinTwoPercent': loss <= .02,
        'allAperturesHaveConnectedCutterCenters': all(r['toolCenterComponents'] == r['finalToolCenterComponents'] == 1 for r in tool_rows),
        'allPlungeDisksContained': all(r['plungeDiskOutsideApertureAreaMm2'] < 1e-5 for r in tool_rows),
    }
    assert all(checks.values()), checks
    sections = []
    for index in sorted(GUIDES):
        pts = top['art']['strokes'][index]['pts']
        for segment, (a, b) in enumerate(zip(pts, pts[1:])):
            length, u, n = frame(a, b)
            for fraction in (.1, .25, .5, .75, .9):
                m = (a[0]+fraction*length*u[0], a[1]+fraction*length*u[1])
                line = LineString([(m[0]-2*n[0], m[1]-2*n[1]), (m[0]+2*n[0], m[1]+2*n[1])])
                before_width = next(hi-lo for lo, hi in intervals(before, line, m, n) if lo < 0 < hi)
                after_width = next(hi-lo for lo, hi in intervals(final, line, m, n) if lo < 0 < hi)
                assert after_width >= 1.999
                sections.append({'sourceStrokeIndex0': index, 'sourceSegmentIndex0': segment,
                                 'fraction': fraction, 'pointMm': m, 'normal': n,
                                 'beforeMaterialWidthMm': before_width, 'afterMaterialWidthMm': after_width,
                                 'nominalGoldWidthsMm': [.251, .28, .251], 'nominalInkWidthsMm': [.251, .251],
                                 'nominalOuterClearanceMm': .358})
    old_rib = LineString(paths[-1]['pointsMm']).buffer(1, cap_style='flat', join_style='mitre')
    diagnostic_body = shapely.from_wkb(bytes.fromhex(snapshot['bodyWkbHex']))
    portions = guide_portions(top)
    safe = final.buffer(-.35, quad_segs=64)
    for portion in portions:
        nominal_gold = LineString(portion['nominalRelocatedPortionMm']).buffer(.1255, quad_segs=64)
        portion['nominalGoldOutsideMaskSafeAreaMm2'] = nominal_gold.difference(safe).area
        assert portion['nominalGoldOutsideMaskSafeAreaMm2'] < 1e-5
    patches = [shapely.from_wkb(bytes.fromhex(p['wkbHex']))
               for p in prior['implementationExample']['patches']]
    report = {
        'id': 'spider-l01-complete-network-2026-09-25',
        'status': 'bounded material feasibility and nominal guide proposal; final transition, artwork, finite toolpath and native/CAM gates pending',
        'approvedSourceSha256': SOURCE_SHA, 'baseEvidence': 'spider-channel-erratum.json',
        'baseEvidenceSha256': digest(prior_raw), 'baseBodyNormalizedWkbSha256': normsha(before),
        'surveyInput': 'spider-network-input.json', 'surveyInputSha256': digest(snapshot_raw),
        'newCentralStrokeIndices0': NEW_STROKES, 'retainedEarlierCentralStrokeIndices0': [7, 8],
        'paths': paths, 'ribbonWidthMm': 2.0, 'capStyle': 'flat', 'joinStyle': 'mitre',
        'affectedOriginalGeometryHoleIndices0': affected,
        'initialAdditionAreaMm2': initial_delta.area, 'initialAdditionNormalizedWkbSha256': normsha(initial_delta),
        'earlierRibAdditionAreaMm2IncludedOnce': old_rib.difference(before).area,
        'extraRibbonAreaVersusCapturedSurveyBodyMm2': ribbons.difference(diagnostic_body).area,
        'routingCleanupAreaMm2': cleanup_delta.area, 'routingCleanupNormalizedWkbSha256': normsha(cleanup_delta),
        'combinedAdditionAreaMm2': final.difference(before).area,
        'finalBodyNormalizedWkbSha256': normsha(final),
        'originalDecorativeAreaMm2': original_area, 'cumulativeApertureLossFraction': loss,
        'mechanicalChecks': checks, 'toolAccess': sorted(tool_rows, key=lambda r: r['originalGeometryHoleIndex0']),
        'guidePortions': portions, 'crossSections': sections,
        'priorChannelPatchesRetainedUnchanged': [normsha(p) for p in patches],
        'priorPatchOverlapWithNetworkEnvelopeAreaMm2': unary_union(patches).intersection(ribbons.buffer(.5)).area,
        'probeScriptSha256': digest(Path(__file__).read_bytes()),
        'shapelyVersion': shapely.__version__, 'geosVersion': shapely.geos_version_string,
    }
    if include_survey:
        report['survey'] = survey(top, snapshot)
    return report, before, initial, final


def render(report, before, initial, final):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1400, 1600), '#eef1ee')
    draw = ImageDraw.Draw(image)
    def font(size):
        for name in ['/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
            if Path(name).exists():
                return ImageFont.truetype(name, size)
        return ImageFont.load_default(size=size)
    def paint(geometry, bounds, left, top, width, height, color):
        x0, y0, x1, y1 = bounds
        scale = min(width/(x1-x0), height/(y1-y0))
        def points(ring):
            return [(left+(x-x0)*scale, top+(y-y0)*scale) for x, y in ring.coords]
        for poly in polygons(geometry.intersection(box(*bounds))):
            draw.polygon(points(poly.exterior), fill=color)
            for ring in poly.interiors:
                draw.polygon(points(ring), fill='#eef1ee')
    draw.text((25, 20), 'Spider L01: complete network material decision', font=font(28), fill='#14212a')
    draw.text((25, 66), 'Left: captured pre-rib material. Right: exact 2.0 mm ribbons and indexed cutter cleanup.', font=font(19), fill='#14212a')
    draw.text((25, 100), 'Blue: added ribbon material. Orange: cutter cleanup. Artwork and transitions are not approved here.', font=font(18), fill='#704527')
    for x, body in [(60, before), (760, final)]:
        paint(body, (0, 0, 101.3, 128.5), x, 150, 530, 670, '#293b47')
    paint(initial.difference(before), (0, 0, 101.3, 128.5), 760, 150, 530, 670, '#128dc2')
    paint(final.difference(initial), (0, 0, 101.3, 128.5), 760, 150, 530, 670, '#d16a22')
    for y, bounds, title in [(875, (58, 27, 92, 53), 'Upper radial network: strokes 6/7/8 and junctions'),
                              (1220, (26, 57, 45, 84), 'Central network: strokes 18/36/39, including the smallest channels')]:
        draw.text((25, y), title, font=font(21), fill='#14212a')
        for x, body in [(30, before), (730, final)]:
            paint(body, bounds, x, y+40, 620, 260, '#293b47')
        paint(initial.difference(before), bounds, 730, y+40, 620, 260, '#128dc2')
        paint(final.difference(initial), bounds, 730, y+40, 620, 260, '#d16a22')
    draw.text((25, 1560), f"Cumulative aperture loss {100*report['cumulativeApertureLossFraction']:.4f}%; 19 apertures retained. Final artwork/CAM pending.", font=font(18), fill='#14212a')
    image.save(HERE/'spider-network-comparison.png')


if __name__ == '__main__':
    report, before, initial, final = measure()
    (HERE/'spider-network-decision.json').write_text(json.dumps(report, indent=2)+'\n')
    render(report, before, initial, final)
    print(json.dumps({key: report[key] for key in ['initialAdditionAreaMm2', 'routingCleanupAreaMm2', 'combinedAdditionAreaMm2', 'cumulativeApertureLossFraction']}))
