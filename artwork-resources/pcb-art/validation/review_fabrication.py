#!/usr/bin/env python3
"""Quantify handoff geometry; never edit a source outline or emit release Gerbers.

Run with the source project's Shapely/Pillow/numpy environment. Geometry units mm.
The router-opening model is a diagnostic, not a prediction of a factory toolpath.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, nearest_points

HERE = Path(__file__).resolve().parent
HANDOFF = HERE.parent
DEFAULT_SOURCE = HANDOFF / 'preview-source/assets/geometry.json'
TOOL_DIAMETER = 1.0
MIC_TOLERANCE = .0001


def polys(g):
    if g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g]
    return [p for child in getattr(g, 'geoms', []) for p in polys(child)]


def convex_mic_upper(p):
    """LP optimum for convex hull by enumerating 3 active half planes.

    A circle inside p is inside its convex hull, so this is an upper bound for p.
    Coordinates are translated to their centroid to reduce numeric cancellation.
    """
    hull = orient(p.convex_hull, sign=1)
    origin = np.array([hull.centroid.x, hull.centroid.y])
    vertices = np.array(hull.exterior.coords[:-1]) - origin
    constraints, limits = [], []
    for a, b in zip(vertices, np.roll(vertices, -1, axis=0)):
        edge = b - a
        n = np.array([edge[1], -edge[0]]) / np.linalg.norm(edge)
        constraints.append([n[0], n[1], 1.0])
        limits.append(np.dot(n, a))
    A, B = np.array(constraints), np.array(limits)
    best = None
    for ix in itertools.combinations(range(len(A)), 3):
        try:
            candidate = np.linalg.solve(A[list(ix)], B[list(ix)])
        except np.linalg.LinAlgError:
            continue
        if candidate[2] >= -1e-10 and np.all(A @ candidate <= B + 1e-9):
            if best is None or candidate[2] > best[2]:
                best = candidate
    if best is None:
        raise ValueError('No bounded convex MIC solution')
    return float(best[2] * 2), (best[:2] + origin).tolist()


def measure_small_hole(p):
    mic = shapely.maximum_inscribed_circle(p, tolerance=MIC_TOLERANCE)
    center = Point(mic.coords[0])
    lower = 2 * center.distance(p.boundary)
    upper, hull_center = convex_mic_upper(p)
    # An LP center valid for the original polygon often gives an exact solution.
    hc = Point(hull_center)
    if p.covers(hc) and 2 * hc.distance(p.boundary) > lower:
        center, lower = hc, 2 * hc.distance(p.boundary)
    return {
        'micDiameterLowerBoundMm': round(lower, 8),
        'micDiameterUpperBoundMm': round(upper, 8),
        'micNumericalSearchToleranceMm': MIC_TOLERANCE,
        'micCenterMm': [round(center.x, 8), round(center.y, 8)],
        'upperBoundMethod': 'convex-hull maximum-inscribed-circle linear program',
        'noOneMmCircularRouterFits': upper < TOOL_DIAMETER - 1e-7,
    }


def roundn(v, n=6):
    return round(float(v), n)


def nominal_gold_strokes(d):
    result = []
    for l in d['layers']:
        positive = [s for s in l['art']['strokes'] if not s.get('color')]
        if positive:
            result.append({'layer': l['index'] + 1,
                'minNominalStrokeWidthMm': min(s['w'] for s in positive),
                'strokesBelow025Mm': sum(s['w'] < .25 for s in positive),
                'strokeCount': len(positive)})
    return result


def polygon_path(p):
    def ring_path(r):
        pts = list(r.coords)
        return 'M ' + ' L '.join(f'{x:.4f},{y:.4f}' for x, y in pts) + ' Z'
    return ' '.join([ring_path(p.exterior), *[ring_path(r) for r in p.interiors]])


def font(size, bold=False):
    path = '/usr/share/fonts/truetype/dejavu/DejaVuSans' + ('-Bold' if bold else '') + '.ttf'
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def annotated_layer(d, layer, issues, destination):
    key = d.get('variantId', 'standard')
    slug = f'kumiko-{key}-L{layer["index"] + 1:02d}'
    body = Polygon(layer['outer'], layer['holes'])
    # Always show the 101.3 x 128.5 reference frame so lower sheets remain aligned.
    sx = 5.0
    margin, top = 28, 86
    width, height = math.ceil(101.3 * sx + 2 * margin), math.ceil(128.5 * sx + top + 54)
    im = Image.new('RGB', (width, height), '#f4f4f1')
    draw = ImageDraw.Draw(im)
    draw.text((20, 14), f'KUMIKO {key.upper()} / L{layer["index"]+1:02d}', font=font(20, True), fill='#17212e')
    draw.text((20, 43), f'{len(issues)} apertures cannot contain a 1.0 mm cutter', font=font(12), fill='#ac2437')
    draw.text((20, 62), 'Red marks locate issues. IDs refer to the CSV / JSON.', font=font(11), fill='#52606b')
    def pts(r):
        return [(margin + x * sx, top + y * sx) for x, y in r]
    draw.rectangle((margin, top, margin + 101.3*sx, top + 128.5*sx), outline='#cad1d5', width=1)
    draw.polygon(pts(body.exterior.coords), fill='#334658')
    for r in body.interiors:
        draw.polygon(pts(r.coords), fill='#f4f4f1')
    svg_marks = []
    for j, issue in enumerate(issues):
        poly = Polygon(issue['verticesMm'])
        x, y = issue['micCenterMm']
        px, py = margin+x*sx, top+y*sx
        draw.polygon(pts(poly.exterior.coords), fill='#e23a52')
        draw.ellipse((px-10, py-10, px+10, py+10), outline='#e23a52', width=2)
        # Alternating vertical offsets keep neighboring edge apertures legible.
        tx = min(width-36, max(4, px+13 if x < 85 else px-32))
        ty = py - (22 if j % 2 == 0 else -7)
        text_id = issue['localId']
        draw.line((px, py, tx+8, ty+6), fill='#e23a52', width=1)
        draw.rectangle((tx-2, ty-1, tx+27, ty+14), fill='#fff4f3')
        draw.text((tx, ty), text_id, font=font(11, True), fill='#bb1735')
        stx, sty = (tx-margin)/sx, (ty-top)/sx
        svg_marks.append(f'<path d="{polygon_path(poly)}" fill="#e23a52"/><circle cx="{x}" cy="{y}" r="2" fill="none" stroke="#e23a52" stroke-width=".4"/><line x1="{x}" y1="{y}" x2="{stx+1.6}" y2="{sty+1.2}" stroke="#e23a52" stroke-width=".2"/><rect x="{stx-.4}" y="{sty-.2}" width="5.8" height="3" fill="#fff4f3"/><text x="{stx}" y="{sty+2.1}" font-size="2.2" font-weight="bold" fill="#bb1735">{text_id}</text>')
    draw.text((20, height-35), 'Source cutouts preserved; annotated analysis only.', font=font(11), fill='#52606b')
    im.save(destination / f'{slug}.png')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="113.3mm" height="155mm" viewBox="-6 -18 113.3 155">
<rect x="-6" y="-18" width="113.3" height="155" fill="#f4f4f1"/>
<text x="-2" y="-11" font-family="sans-serif" font-size="4" font-weight="bold">Kumiko {escape(key)} / L{layer['index']+1:02d}</text>
<text x="-2" y="-6" font-family="sans-serif" font-size="2.6" fill="#ac2437">{len(issues)} apertures: no 1.0 mm cutter fits inside</text>
<rect width="101.3" height="128.5" fill="none" stroke="#cad1d5" stroke-width=".2"/>
<path d="{polygon_path(body)}" fill="#334658" fill-rule="evenodd"/>
<g font-family="sans-serif">{''.join(svg_marks)}</g>
<text x="-2" y="134" font-family="sans-serif" font-size="2.4">Original outlines retained. See issue IDs in CSV / JSON.</text>
</svg>'''
    (destination / f'{slug}.svg').write_text(svg)
    return im, slug


def annotated_thin_ligament(body, issue, destination):
    """An enlarged actual-geometry example explaining the erosion-test limit."""
    width, height = 1120, 600
    im = Image.new('RGB', (width, height), '#f4f4f1')
    draw = ImageDraw.Draw(im)
    draw.text((24, 16), 'KUMIKO WIDE / L01 — LOCAL MATERIAL DETAIL', font=font(25, True), fill='#17212e')
    draw.text((24, 54), 'A connected eroded core does not prove that every local feature is 1.0 mm wide.', font=font(17), fill='#52606b')
    x0, y0, x1, y1 = 89.8, 22.0, 98.8, 30.2
    scale = 49
    def render(g, ox):
        def pts(r):
            return [(ox+(x-x0)*scale, 141+(y-y0)*scale) for x,y in r]
        viewport = Polygon([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        for p in polys(g.intersection(viewport)):
            draw.polygon(pts(p.exterior.coords), fill='#334658')
            for r in p.interiors:
                draw.polygon(pts(r.coords), fill='#f4f4f1')
        draw.rectangle((ox,141,ox+(x1-x0)*scale,141+(y1-y0)*scale), outline='#cad1d5')
        return pts
    left_pts = render(body, 38)
    render(body.buffer(-.5), 619)
    draw.text((38, 105), 'Original nominal outline', font=font(19, True), fill='#17212e')
    draw.text((619, 105), '0.5 mm inward offset', font=font(19, True), fill='#17212e')
    ends = left_pts(issue['closestPointsMm'])
    a,b=ends
    draw.line([a,b], fill='#e23a52', width=4)
    cx,cy=(a[0]+b[0])/2,(a[1]+b[1])/2
    draw.ellipse((cx-19,cy-19,cx+19,cy+19), outline='#e23a52', width=3)
    draw.line((cx+20,cy,467,cy-48), fill='#e23a52', width=2)
    draw.text((245,cy-75), f'{issue["widthMm"]:.6f} mm', font=font(19,True), fill='#bb1735')
    draw.text((38,560), 'Tiny aperture / ligament remains in the source; manufacturing resolution is required.', font=font(16), fill='#52606b')
    im.save(destination/'kumiko-wide-L01-thin-ligament.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output-dir', type=Path, default=HANDOFF/'generated'/'fabrication-review',
                        help='New generated report directory; imported source evidence is left untouched.')
    args = parser.parse_args()
    source = args.source.resolve()
    raw = source.read_bytes()
    data = json.loads(raw)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spec = data['spec']
    screws = [Point(*xy) for xy in spec['screws']]
    centers = screws + [Point(*xy) for xy in spec['slots']]
    resource_dir = output_dir / 'resources/manufacturing-review'
    resource_dir.mkdir(parents=True, exist_ok=True)
    result = {
        'schemaVersion': 1, 'revision': data['revision'],
        'source': 'preview-source/assets/geometry.json', 'sourceSha256': hashlib.sha256(raw).hexdigest(),
        'units': 'mm', 'manufacturingResolutionRequired': True,
        'referenceRouterDiameterMm': TOOL_DIAMETER,
        'sourceGeometryChanged': False,
        'methods': {
            'wholeApertureTooSmall': 'Negative buffer radius0.5 finds candidates; each is confirmed with a convex-hull MIC upper bound below1.0mm. MIC lower bound is twice distance from an interior point to aperture boundary. All calculations use nominal serialized polygons and floating-point arithmetic.',
            'routerUnreachableArea': 'Area(A) - Area(A intersect buffer(buffer(A,-0.5),+0.5)); 32 circular segments per quadrant. Shows inaccessible sharp tips and narrow zones under a1.0mm circular-router model, not approved factory CAM or a suggested replacement outline.',
            'routingDensityProxy': 'Sum decorative inner-contour perimeter plus rail-slot perimeter divided by original rectangular board area; mm^-1 multiplied by1000 to m/m². Does not include plunge/lead-in/repeated passes; is not the actual cutter-center toolpath or a quote.',
            'geometryConnectivity': 'A single Polygon after all drilling and one significant connected component after0.5mm inward offset. Erosion may remove thin dangling detail; this does not prove minimum width everywhere or mechanical load capacity.',
        },
        'sources': [
            {'title': 'JLCPCB rigid PCB capabilities', 'url': 'https://jlcpcb.com/capabilities/pcb-capabilities', 'checked': '2026-09-24', 'fields': ['Min. Non-Plated Slots1.0mm', 'Rectangular Holes / Slots without rounded corners not supported', 'Routed Cu clearance≥0.2mm', 'NPTH-to-Track0.2mm', '1oz min track/space0.10/0.10mm', 'Black/white mask bridge0.13mm', '1.6mm thickness±10%']},
            {'title': 'JLCPCB extra charges', 'url': 'https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra', 'checked': '2026-09-24', 'sections': ['3 Routing Fee', '5 ENIG Area over30%', '1 Different Designs in One Gerber File']},
            {'title': 'JLCPCB NPTH design guide', 'url': 'https://jlcpcb.com/blog/npth-design-guide', 'checked': '2026-09-24'},
            {'title': 'JLCPCB solder mask guide', 'url': 'https://jlcpcb.com/blog/basic-design-of-solder-mask', 'checked': '2026-09-24'},
            {'title': 'Shapely maximum_inscribed_circle', 'url': 'https://shapely.readthedocs.io/en/stable/reference/shapely.maximum_inscribed_circle.html', 'checked': '2026-09-24'},
        ],
        'designs': [], 'apertureIssues': [], 'thinMaterialIssues': [],
    }
    contact_images = {}
    for family in data['designs']:
        for d in [family, *family.get('variants', [])]:
            key = d['id'] + ('-' + d['variantId'] if d.get('variantId') else '')
            record = {'id': d['id'], 'variantId': d.get('variantId'), 'key': key,
                'layers': [], 'goldNominalStrokes': nominal_gold_strokes(d)}
            for layer in d['layers']:
                body = Polygon(layer['outer'], layer['holes'])
                holes = [Polygon(h) for h in layer['holes']]
                decorative = [(i, p) for i, p in enumerate(holes) if not any(p.covers(c) for c in centers)]
                copper_strokes = [s for s in layer['art']['strokes'] if not s.get('color')]
                width = spec['width']; height = spec['height'] if layer['index'] == 0 else spec['height'] - 2 * spec['keepout']
                perimeter = sum(p.length for _, p in decorative)
                slots = [p for p in holes if any(p.covers(c) for c in centers[4:])]
                perimeter += sum(p.length for p in slots)
                eroded = body.buffer(-.5)
                min_outer_gap = min((p.distance(body.exterior) for p in holes), default=None)
                interhole = [(a.distance(b), i, j) for (i, a), (j, b) in itertools.combinations(enumerate(holes), 2)]
                smallest_gap = min(interhole) if interhole else None
                for distance, ai, bi in interhole:
                    if distance >= 1.0:
                        continue
                    a,b = nearest_points(holes[ai],holes[bi])
                    issue = {'issueId':f'{key}-L{layer["index"]+1:02d}-THIN-{ai}-{bi}',
                        'designId':d['id'], 'variantId':d.get('variantId'), 'layer':layer['index']+1,
                        'geometryHoleIndices0':[ai,bi], 'widthMm':roundn(distance,9),
                        'closestPointsMm':[list(a.coords[0]),list(b.coords[0])],
                        'requiredAction':'Review the local ligament together with the adjacent tiny aperture before manufacturing; the connectivity erosion test does not preserve every thin detail.'}
                    result['thinMaterialIssues'].append(issue)
                    annotated_thin_ligament(body,issue,resource_dir)
                per_layer = {
                    'layer': layer['index'] + 1, 'colorKey': layer['colorKey'], 'finish': layer['finish'],
                    'connected': body.is_valid and body.geom_type == 'Polygon',
                    'erosion05Connected': len([p for p in polys(eroded) if p.area > .02]) == 1,
                    'decorativeApertureCount': len(decorative),
                    'decorativeApertureAreaMm2': roundn(sum(p.area for _, p in decorative)),
                    'routingContourLengthProxyMm': roundn(perimeter),
                    'routingContourDensityProxyMPerM2': roundn(perimeter / (width*height) * 1000),
                    'minHoleToOuterMaterialMm': roundn(min_outer_gap) if min_outer_gap is not None else None,
                    'minInterholeMaterialMm': roundn(smallest_gap[0]) if smallest_gap else None,
                    'minInterholeGeometryIndices0': list(smallest_gap[1:]) if smallest_gap else None,
                    'minSpacerFootprintMarginToDecorativeCutoutMm': roundn(min((c.distance(p)-3.0 for c in screws for _, p in decorative), default=float('nan'))) if decorative else None,
                    'noOneMmRouterHoleCount': 0, 'noOneMmRouterIssueIds': [],
                    'routerUnreachableAreaMm2': 0,
                    'aperturesWithSplitToolCenterRegions': [],
                }
                issues = []
                for hole_index, p in decorative:
                    core = p.buffer(-.5, quad_segs=32)
                    opening = core.buffer(.5, quad_segs=32).intersection(p) if not core.is_empty else Polygon()
                    per_layer['routerUnreachableAreaMm2'] += max(0, p.area - opening.area)
                    if len([q for q in polys(core) if q.area > .000001]) > 1:
                        per_layer['aperturesWithSplitToolCenterRegions'].append(hole_index)
                    if not core.is_empty:
                        continue
                    measure = measure_small_hole(p)
                    local_id = f'H{len(issues)+1:02d}'
                    item = {'issueId': f'{key}-L{layer["index"]+1:02d}-{local_id}',
                        'localId': local_id, 'designId': d['id'], 'variantId': d.get('variantId'),
                        'layer': layer['index'] + 1, 'geometryHoleIndex0': hole_index,
                        'areaMm2': roundn(p.area, 8), 'boundsMm': [roundn(v, 8) for v in p.bounds],
                        'verticesMm': list(map(list, p.exterior.coords[:-1])), **measure,
                        'requiredAction': 'Resolve locally against selected fabrication route; preserve source until a documented manufacturing variant is reviewed.',
                    }
                    if not item['noOneMmCircularRouterFits']:
                        raise ValueError('Small-hole candidate could not be confirmed by upper bound')
                    issues.append(item)
                per_layer['noOneMmRouterHoleCount'] = len(issues)
                per_layer['noOneMmRouterIssueIds'] = [i['issueId'] for i in issues]
                per_layer['routerUnreachableAreaMm2'] = roundn(per_layer['routerUnreachableAreaMm2'])
                area = per_layer['decorativeApertureAreaMm2']
                per_layer['routerUnreachableFraction'] = roundn(per_layer['routerUnreachableAreaMm2']/area) if area else 0
                record['layers'].append(per_layer)
                result['apertureIssues'].extend(issues)
                if issues:
                    im, slug = annotated_layer(d, layer, issues, resource_dir)
                    contact_images.setdefault(d.get('variantId', 'standard'), []).append((im, slug))
                    per_layer['annotation'] = str(resource_dir / f'{slug}.svg')
            record['wholeAperturesTooSmallForOneMmRouter'] = sum(l['noOneMmRouterHoleCount'] for l in record['layers'])
            record['totalRouterUnreachableAreaMm2'] = roundn(sum(l['routerUnreachableAreaMm2'] for l in record['layers']))
            record['minMaterialBetweenDistinctHolesMm'] = min(l['minInterholeMaterialMm'] for l in record['layers'] if l['minInterholeMaterialMm'] is not None)
            record['nominalStackMm'] = d['stackDepth']
            n = len(d['layers'])
            record['stackThicknessToleranceOnlyMm'] = [roundn(n*1.44+(n-1)*3), roundn(n*1.76+(n-1)*3)]
            record['spacerCountForOneStack'] = 4*(n-1)
            result['designs'].append(record)
    for variant, images in contact_images.items():
        cols = 4
        tw, th = 400, 558
        rows = math.ceil(len(images)/cols)
        canvas = Image.new('RGB', (cols*tw + 40, rows*th + 95), '#e8ecee')
        draw = ImageDraw.Draw(canvas)
        draw.text((22, 17), f'KUMIKO {variant.upper()} — ROUTING REVIEW', font=font(26, True), fill='#192936')
        draw.text((22, 52), 'All marked apertures have an inscribed-circle upper bound below 1.0 mm. Source geometry retained.', font=font(15), fill='#415461')
        for i, (im, slug) in enumerate(images):
            resized = im.copy()
            resized.thumbnail((tw-12, th-10))
            canvas.paste(resized, (20+(i%cols)*tw, 86+(i//cols)*th))
        canvas.save(resource_dir/f'kumiko-{variant}-routing-review.png')
    output = output_dir / 'fabrication-review.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    with (resource_dir/'kumiko-routing-issues.csv').open('w', newline='') as fp:
        fields = ['issueId','variantId','layer','geometryHoleIndex0','areaMm2','micDiameterLowerBoundMm','micDiameterUpperBoundMm','centerXmm','centerYmm','minXmm','minYmm','maxXmm','maxYmm']
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for x in result['apertureIssues']:
            row = {key:x[key] for key in fields if key in x}
            row.update(centerXmm=x['micCenterMm'][0], centerYmm=x['micCenterMm'][1], **dict(zip(['minXmm','minYmm','maxXmm','maxYmm'],x['boundsMm'])))
            writer.writerow(row)
    print(json.dumps({'revision': data['revision'], 'records':sum(len(d['layers']) for d in result['designs']), 'issueCount':len(result['apertureIssues']),
        'designs':[{k:d[k] for k in ['key','wholeAperturesTooSmallForOneMmRouter','totalRouterUnreachableAreaMm2','minMaterialBetweenDistinctHolesMm']} for d in result['designs']],
        'output':str(output)}, indent=2))


if __name__ == '__main__':
    main()
