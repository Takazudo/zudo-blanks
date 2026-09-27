#!/usr/bin/env python3
"""Export the approved millimetre artwork as editable KiCad boards and vectors.

Requires Python 3.10+ and Shapely 2.1+. No KiCad or node runtime is required to
generate the files. A KiCad GUI/CLI load, DRC and CAM review remains a local gate.
The input is the preview's exact geometry.json, not a traced screenshot.

KiCad format references:
https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/
https://dev-docs.kicad.org/en/file-formats/sexpr-intro/
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

import shapely
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, Point, LineString, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, split
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.UUID('220f011b-f652-52a4-a5e5-7b919e2c18bc')
RULES = {'copperEdgeClearanceMm': 0.30, 'maskOpeningEdgeClearanceMm': 0.35,
         'copperUnderMaskMarginMm': 0.05, 'numericPrecisionMm': 0.000001,
         'curveBufferQuadrantSegments': 32,
         'status': 'Chosen conservative export policy; not fabricator approval.'}
SOURCES = [
    'https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/',
    'https://dev-docs.kicad.org/en/file-formats/sexpr-intro/',
    'https://jlcpcb.com/capabilities/pcb-capabilities',
]


def number(x):
    return f'{float(x):.6f}'.rstrip('0').rstrip('.') or '0'


def quote(s):
    return json.dumps(str(s), ensure_ascii=False)


def ident(key):
    return str(uuid.uuid5(NAMESPACE, key))


def polygons(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [p for part in getattr(g, 'geoms', []) for p in polygons(part)]


def clean(g):
    """Retain every positive-area polygon; do not silently erase fine art."""
    if not g.is_valid:
        g = shapely.make_valid(g)
    p = polygons(g)
    return unary_union(p) if p else Polygon()


def ordered(g):
    return sorted(polygons(g), key=lambda p: (tuple(round(v, 6) for v in p.bounds), round(p.area, 9)))


def ring_points(r):
    points = [(round(x, 6), round(y, 6)) for x, y in r.coords]
    result = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result


def serialized(g):
    return [{'outer': ring_points(p.exterior), 'holes': [ring_points(r) for r in p.interiors]}
            for p in ordered(g)]


def drill_specs(layer, spec):
    result = [{'id': f'STACK-{i+1}', 'x': x, 'y': y,
               'width': spec['screwDiameter'], 'height': spec['screwDiameter'],
               'shape': 'circle', 'plated': False}
              for i, (x, y) in enumerate(spec['screws'])]
    if layer['index'] == 0:
        result += [{'id': f'RAIL-{i+1}', 'x': x, 'y': y,
                    'width': spec['slotDrill'][0], 'height': spec['slotDrill'][1],
                    'shape': 'oval', 'plated': False}
                   for i, (x, y) in enumerate(spec['slots'])]
    return result


def drill_shape(d, segments=128):
    x, y, w, h = d['x'], d['y'], d['width'], d['height']
    if d['shape'] == 'circle':
        return Point(x, y).buffer(w / 2, quad_segs=segments)
    half_line = (w-h)/2
    return LineString([(x-half_line, y), (x+half_line, y)]).buffer(h/2, quad_segs=segments)


def split_functional_holes(layer, drills):
    decorative, found = [], set()
    for points in layer['holes']:
        p = Polygon(points)
        matches = [d for d in drills if p.covers(Point(d['x'], d['y']))]
        if len(matches) > 1:
            raise ValueError('A hole unexpectedly contains multiple mounting centers')
        if matches:
            d = matches[0]
            # The preview used 16 segments per quadrant. Accept only that exact
            # known functional-hole shape, never an arbitrary opening nearby.
            expected = drill_shape(d, segments=16)
            if p.symmetric_difference(expected).area > 0.005:
                raise ValueError(f'Functional drill shape mismatch: {d["id"]}')
            found.add(d['id'])
        else:
            decorative.append(p)
    if found != {d['id'] for d in drills}:
        raise ValueError(f'Missing functional holes: {found}')
    return decorative


def stroke_geometry(s, angular):
    pts = s['pts']
    if len(set(map(tuple, pts))) < 2:
        return Polygon()
    if s.get('closed') and pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    return LineString(pts).buffer((s.get('w') or 0.3) / 2,
        cap_style='flat' if angular else 'round',
        join_style='mitre' if angular else 'round', mitre_limit=10,
        quad_segs=RULES['curveBufferQuadrantSegments'])


def paint_gold(layer, design, body):
    """Exactly follow viewer.makeArtwork: fills first, then strokes.

    A truthy color is opaque solder mask (including black Kumiko facets).
    Consecutive same-paint items are unioned in a batch; paint order is retained.
    """
    if layer['finish'] == 'mask-only':
        return Polygon()
    gold = body if layer['finish'] == 'enig-fill' else Polygon()
    items = []
    for f in layer['art'].get('fills', []):
        items.append((not bool(f.get('color')), clean(Polygon(f['pts']))))
    for s in layer['art'].get('strokes', []):
        items.append((not bool(s.get('color')), stroke_geometry(s, design.get('artStyle') == 'angular')))
    groups = []
    for is_gold, geom in items:
        if geom.is_empty:
            continue
        if groups and groups[-1][0] == is_gold:
            groups[-1][1].append(geom)
        else:
            groups.append((is_gold, [geom]))
    for is_gold, pieces in groups:
        ink = unary_union(pieces)
        gold = gold.union(ink) if is_gold else gold.difference(ink)
    return clean(gold.intersection(body))


def without_holes(geom):
    """Split positive polygons at zero-width lines; no drill/cutout is filled.

    KiCad gr_poly stores one simple contour. Vertically partitioning only
    polygons that contain holes avoids a triangle mesh and preserves exact
    polygon areas. These are editable filled graphics, not refillable zones.
    """
    pending, result = ordered(geom), []
    iterations = 0
    while pending:
        p = pending.pop()
        if not p.interiors:
            result.append(p)
            continue
        iterations += 1
        if iterations > 20000:
            raise ValueError('Unexpectedly complex artwork partition')
        hole = max((Polygon(r) for r in p.interiors), key=lambda q: q.area)
        middle = hole.representative_point()
        minx, miny, maxx, maxy = p.bounds
        cutter = LineString([(middle.x, miny-1), (middle.x, maxy+1)])
        pieces = polygons(split(p, cutter))
        if len(pieces) < 2:
            cutter = LineString([(minx-1, middle.y), (maxx+1, middle.y)])
            pieces = polygons(split(p, cutter))
        if len(pieces) < 2:
            raise ValueError('Could not split polygon hole into editable contours')
        pending.extend(pieces)
    result.sort(key=lambda p: (tuple(round(v, 6) for v in p.bounds), round(p.area, 9)))
    actual = unary_union(result)
    error = actual.symmetric_difference(geom).area
    if error > 0.00001:
        raise ValueError(f'Artwork partition changed area by {error} mm²')
    return result


def native_parts(geom):
    pieces, collapsed, collapsed_area = [], 0, 0.0
    for p in without_holes(geom):
        pts=ring_points(p.exterior)
        if len(pts)<3 or Polygon(pts).area==0:
            collapsed+=1;collapsed_area+=p.area
            continue
        rp=Polygon(pts)
        if not rp.is_valid:
            # Any such error would require review, rather than guessing a
            # repaired graphic that no longer matches the positive source.
            raise ValueError('Artwork polygon became invalid at 1 nm precision')
        pieces.append(rp)
    if collapsed_area>0.000001:
        raise ValueError('Quantization would discard a meaningful artwork area')
    return pieces, {'count':collapsed, 'areaMm2':collapsed_area}


def native_polygon(points, layer, key, fill='solid', width=0):
    pts = ' '.join(f'(xy {number(x)} {number(y)})' for x, y in points)
    return (f'  (gr_poly (pts {pts}) (stroke (width {number(width)}) (type default)) '
            f'(fill {fill}) (layer {quote(layer)}) (uuid {quote(ident(key))}))\n')


def native_board(stem, layer, spec, edge_rings, drills, cu_parts, mask_parts):
    finish = 'ENIG' if layer['finish'] != 'mask-only' else 'No exposed copper; quote non-ENIG finish separately'
    color = 'Black' if layer['colorKey'] == 'gold' else layer['colorKey'].capitalize()
    out = [f'(kicad_pcb (version 20240108) (generator "takazudo-pcb-art-export")\n',
      f'  (general (thickness {number(spec["thickness"])}))\n',
      '  (paper "A4")\n',
      f'  (title_block (title {quote(stem)}) (rev "5") (company "Takazudo Modular")\n'
      '    (comment 1 "Editable handoff: run local KiCad DRC and inspect CAM before order"))\n',
      '  (layers\n    (0 "F.Cu" signal) (31 "B.Cu" signal)\n'
      '    (32 "B.Adhes" user "B.Adhesive") (33 "F.Adhes" user "F.Adhesive")\n'
      '    (34 "B.Paste" user) (35 "F.Paste" user)\n'
      '    (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen")\n'
      '    (38 "B.Mask" user) (39 "F.Mask" user)\n'
      '    (40 "Dwgs.User" user "User.Drawings") (41 "Cmts.User" user "User.Comments")\n'
      '    (44 "Edge.Cuts" user) (45 "Margin" user)\n'
      '    (46 "B.CrtYd" user "B.Courtyard") (47 "F.CrtYd" user "F.Courtyard")\n'
      '    (48 "B.Fab" user) (49 "F.Fab" user)\n  )\n',
      '  (setup (pad_to_mask_clearance 0) (solder_mask_min_width 0)\n'
      '    (aux_axis_origin 0 0) (grid_origin 0 0)\n'
      '    (stackup\n'
      f'      (layer "F.Mask" (type "Top Solder Mask") (color {quote(color)}))\n'
      '      (layer "F.Cu" (type "copper") (thickness 0.035))\n'
      '      (layer "dielectric 1" (type "core") (thickness 1.53) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))\n'
      '      (layer "B.Cu" (type "copper") (thickness 0.035))\n'
      f'      (layer "B.Mask" (type "Bottom Solder Mask") (color {quote(color)}))\n'
      f'      (copper_finish {quote(finish)}) (dielectric_constraints no)\n'
      '    )\n  )\n',
      '  (net 0 "")\n']
    for index, ring in enumerate(edge_rings):
        pts = ring_points(ring)
        # Line primitives form explicit closed routable loops. They are never
        # also represented as drill pads or hidden under filled board graphics.
        for j, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1])):
            out.append(f'  (gr_line (start {number(a[0])} {number(a[1])}) '
                       f'(end {number(b[0])} {number(b[1])}) '
                       '(stroke (width 0.05) (type default)) (layer "Edge.Cuts") '
                       f'(uuid {quote(ident(stem+f"/edge/{index}/{j}"))}))\n')
    for d in drills:
        shape = d['shape']
        drill = f'(drill {number(d["width"])})' if shape == 'circle' else f'(drill oval {number(d["width"])} {number(d["height"])})'
        key = stem + '/' + d['id']
        out.append(f'  (footprint "TakazudoArt:NPTH_{shape}" (layer "F.Cu") '
            f'(uuid {quote(ident(key))}) (at {number(d["x"])} {number(d["y"])})\n'
            f'    (descr {quote("Mechanical " + d["id"] + "; non-plated; copper halo is separate artwork")})\n'
            '    (attr board_only exclude_from_pos_files exclude_from_bom)\n'
            f'    (pad "" np_thru_hole {shape} (at 0 0) '
            f'(size {number(d["width"])} {number(d["height"])}) {drill} '
            f'(layers "*.Cu" "*.Mask") (solder_mask_margin 0) (uuid {quote(ident(key+"/pad"))}))\n  )\n')
    for label, pieces in [('F.Cu', cu_parts), ('F.Mask', mask_parts)]:
        for i, p in enumerate(pieces):
            pts = ring_points(p.exterior)
            if len(pts) < 3 or Polygon(pts).area == 0:
                raise ValueError('Positive geometry collapsed at 1 nm output precision')
            out.append(native_polygon(pts, label, f'{stem}/{label}/{i}'))
    out.append(')\n')
    return ''.join(out)


def svg_path(p):
    segments = []
    for r in [p.exterior] + list(p.interiors):
        pts = ring_points(r)
        if not pts:
            continue
        segments.append('M' + ' L'.join(f'{number(x)},{number(y)}' for x, y in pts) + ' Z')
    return ' '.join(segments)


def svg_document(spec, title, content):
    # A shared full-top coordinate frame keeps every layer and vector registered.
    w, h = spec['width'], spec['height']
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{number(w)}mm" '
        f'height="{number(h)}mm" viewBox="0 0 {number(w)} {number(h)}">\n'
        f'<title>{title}</title>\n'
        '<desc>1 SVG unit = 1 mm. Front view, x right, y down. Shared origin at top panel upper-left. '
        'Lower boards retain their y=17.1 mm offset. Do not fit or scale on import.</desc>\n'
        + content + '\n</svg>\n')


def svg_polys(geom, color):
    return '\n'.join(f'<path d="{svg_path(p)}" fill="{color}" fill-rule="evenodd"/>' for p in ordered(geom))


def svg_edges(rings):
    return '\n'.join(f'<path d="{svg_path(Polygon(r))}" fill="none" stroke="#000000" stroke-width="0.05"/>' for r in rings)


def dxf_document(rings, layer_name):
    """Millimetre DXF closed outlines. DXF Y-up = negative preview Y-down.

    Copper/mask DXFs are boundary interchange, not filled Gerbers. Use the
    native board or even-odd filled SVG to retain positive-region semantics.
    """
    data = ['0','SECTION','2','HEADER','9','$ACADVER','1','AC1015',
            '9','$INSUNITS','70','4','9','$MEASUREMENT','70','1','0','ENDSEC',
            '0','SECTION','2','TABLES','0','TABLE','2','LAYER','70','1',
            '0','LAYER','2',layer_name,'70','0','62','7','6','CONTINUOUS','0','ENDTAB','0','ENDSEC',
            '0','SECTION','2','ENTITIES']
    for r in rings:
        pts = ring_points(r)
        data += ['0','LWPOLYLINE','100','AcDbEntity','8',layer_name,'100','AcDbPolyline',
                 '90',str(len(pts)),'70','1']
        for x, y in pts:
            data += ['10',number(x),'20',number(-y)]
    data += ['0','ENDSEC','0','EOF']
    return '\n'.join(data)+'\n'


def all_rings(geom):
    return [r for p in ordered(geom) for r in [p.exterior] + list(p.interiors)]


def check_sexpr(text):
    """Independent syntax sanity check, explicitly NOT the KiCad parser."""
    depth, string, escaped = 0, False, False
    for c in text:
        if string:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                string = False
        elif c == '"':
            string = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth < 0:
                raise ValueError('S-expression closes before it opens')
    if depth or string:
        raise ValueError('Unbalanced S-expression')


def export_layer(design, layer, category, spec, source_hash, out):
    variant = design.get('variantId')
    slug = f'{int(design["number"]):02d}-{design["id"]}' + (f'-{variant}' if variant else '')
    stem = f'{slug}-L{layer["index"]+1:02d}-{layer["colorKey"]}-{layer["finish"]}'
    board_dir = out/'pcb'/category/slug
    vector_dir = out/'resources'/'vector'/category/slug/stem
    board_dir.mkdir(parents=True, exist_ok=True)
    vector_dir.mkdir(parents=True, exist_ok=True)
    drills = drill_specs(layer, spec)
    decorative = split_functional_holes(layer, drills)
    outline = Polygon(layer['outer'])
    edge_body = Polygon(outline.exterior, [p.exterior.coords for p in decorative])
    if not edge_body.is_valid or edge_body.geom_type != 'Polygon':
        raise ValueError(f'{stem}: invalid connected Edge.Cuts: {explain_validity(edge_body)}')
    drill_union = unary_union([drill_shape(d) for d in drills])
    body = clean(edge_body.difference(drill_union))
    if body.geom_type != 'Polygon':
        raise ValueError(f'{stem}: drills split board into loose islands')
    visible_gold = paint_gold(layer, design, body)
    # Exact drilled circles are represented by true NPTH pads in KiCad. Buffer
    # clearance calculations use 512-sided circular approximations; error is
    # <0.000031 mm on a Ø3.2 mm hole, far below the chosen 0.30 mm margin.
    mask_safe = body.buffer(-RULES['maskOpeningEdgeClearanceMm'], join_style='mitre', mitre_limit=10)
    cu_safe = body.buffer(-RULES['copperEdgeClearanceMm'], join_style='mitre', mitre_limit=10)
    mask = clean(visible_gold.intersection(mask_safe))
    copper = clean(mask.union(mask.buffer(RULES['copperUnderMaskMarginMm'], join_style='mitre',
                    mitre_limit=10, quad_segs=RULES['curveBufferQuadrantSegments'])).intersection(cu_safe)) if not mask.is_empty else Polygon()
    if layer['finish'] == 'mask-only' and (not copper.is_empty or not mask.is_empty):
        raise ValueError('Mask-only layer unexpectedly received artwork')
    if mask.difference(copper.buffer(0.000001)).area > 0.000001:
        raise ValueError('Mask opening extends beyond copper support')
    # KiCad's internal grid is 1 nm. Collapse only sub-grid artifacts created
    # by Boolean artwork operations, never approved decorative Edge.Cuts.
    cu_before=copper;mask_before=mask
    copper=shapely.set_precision(copper, RULES['numericPrecisionMm'])
    mask=shapely.set_precision(mask, RULES['numericPrecisionMm'])
    quantization={'copperAreaDeltaMm2':copper.area-cu_before.area,
                  'maskAreaDeltaMm2':mask.area-mask_before.area,
                  'copperSymmetricDifferenceMm2':copper.symmetric_difference(cu_before).area,
                  'maskSymmetricDifferenceMm2':mask.symmetric_difference(mask_before).area}
    cu_parts,cu_subgrid = native_parts(copper)
    mask_parts,mask_subgrid = native_parts(mask)
    # Validate serialized polygons, including coordinate rounding, rather than
    # relying on only the unrounded in-memory source geometry.
    cu_export = unary_union([Polygon(ring_points(p.exterior)) for p in cu_parts])
    mask_export = unary_union([Polygon(ring_points(p.exterior)) for p in mask_parts])
    for tag, original, exported in [('F.Cu', copper, cu_export), ('F.Mask', mask, mask_export)]:
        if not exported.is_valid or original.symmetric_difference(exported).area > 0.02:
            raise ValueError(f'{stem}: serialized {tag} differs from computed artwork')
    edge_rings = [outline.exterior] + [p.exterior for p in decorative]
    native = native_board(stem, layer, spec, edge_rings, drills, cu_parts, mask_parts)
    check_sexpr(native)
    board_path = board_dir/(stem+'.kicad_pcb')
    board_path.write_text(native)
    (vector_dir/'Edge_Cuts.svg').write_text(svg_document(spec, stem+' Edge.Cuts', svg_edges(edge_rings)))
    (vector_dir/'Edge_Cuts.dxf').write_text(dxf_document(edge_rings, 'Edge_Cuts'))
    for name, geom in [('F_Cu', copper), ('F_Mask', mask)]:
        (vector_dir/(name+'.svg')).write_text(svg_document(spec, stem+' '+name, svg_polys(geom, '#000000')))
        (vector_dir/(name+'.dxf')).write_text(dxf_document(all_rings(geom), name))
    (vector_dir/'Drill.svg').write_text(svg_document(spec, stem+' NPTH drill reference', svg_edges(all_rings(drill_union))))
    (vector_dir/'Drill.dxf').write_text(dxf_document(all_rings(drill_union), 'NPTH_Drill_Reference'))
    (vector_dir/'front.svg').write_text(svg_document(spec, stem+' front finish reference',
                         svg_polys(body, layer['mask'])+'\n'+svg_polys(mask, '#caa653')))
    (vector_dir/'preview_gold.svg').write_text(svg_document(spec, stem+' approved gold BEFORE clearance adaptation', svg_polys(visible_gold, '#000000')))
    (vector_dir/'preview_front.svg').write_text(svg_document(spec, stem+' approved finish BEFORE clearance adaptation',
                         svg_polys(body, layer['mask'])+'\n'+svg_polys(visible_gold, '#caa653')))
    for svg in vector_dir.glob('*.svg'):
        ET.parse(svg)
    metrics = {
        'boardAreaMm2': round(body.area, 6),
        'decorativeApertureCount': len(decorative),
        'decorativeApertureAreaMm2': round(sum(p.area for p in decorative), 6),
        'npthRoundCount': sum(d['shape']=='circle' for d in drills),
        'npthSlotCount': sum(d['shape']=='oval' for d in drills),
        'previewGoldAreaMm2': round(visible_gold.area, 6),
        'exportedMaskOpeningAreaMm2': round(mask.area, 6),
        'exportedCopperAreaMm2': round(copper.area, 6),
        'goldClippedForEdgeClearanceMm2': round(visible_gold.difference(mask).area, 6),
        'goldClippedFraction': round(visible_gold.difference(mask).area/visible_gold.area, 7) if visible_gold.area else 0,
        'copperPositiveComponents': len(polygons(copper)),
        'maskOpeningPositiveComponents': len(polygons(mask)),
        'nativeCopperPolygons': len(cu_parts), 'nativeMaskPolygons': len(mask_parts),
        'copperToBoardEdgeMinimumMm': round(copper.distance(body.boundary), 6) if not copper.is_empty else None,
        'maskOpeningToBoardEdgeMinimumMm': round(mask.distance(body.boundary), 6) if not mask.is_empty else None,
        'serializedCopperSymmetricDifferenceMm2': round(copper.symmetric_difference(cu_export).area, 8),
        'serializedMaskSymmetricDifferenceMm2': round(mask.symmetric_difference(mask_export).area, 8),
        'artworkNanometreQuantization':quantization,
        'subgridArtworkPartitionFragments':{'copper':cu_subgrid,'mask':mask_subgrid},
    }
    data = {'id': stem, 'designId': design['id'], 'variant': variant,
        'category': category, 'layerNumber': layer['index']+1,
        'maskColor': 'black' if layer['colorKey']=='gold' else layer['colorKey'],
        'previewColorKey': layer['colorKey'], 'finish': layer['finish'],
        'thicknessMm': spec['thickness'], 'boardBoundsMm': list(body.bounds),
        'sourceGeometrySha256': source_hash, 'rules': RULES,
        'edgeCuts': {'outer': ring_points(outline.exterior),
                     'cutouts': [ring_points(p.exterior) for p in decorative]},
        'drills': drills, 'frontCopper': serialized(copper),
        'frontMaskOpenings': serialized(mask), 'backCopper': [], 'backMaskArtOpenings': [],
        'metrics': metrics,
        'nativeBoard': str(board_path.relative_to(out)),
        'semantics': {'frontMaskOpenings': 'Positive regions REMOVE solder mask; they do not paint solder mask.',
            'drills': 'NPTH native pads; do not import Drill.svg/DXF into Edge.Cuts.',
            'DXF': 'Closed boundaries only; mm; x-right/y-up (y=-previewY). SVG/native retains filled area semantics.',
            'copper': 'Positive editable graphics without electrical nets; hidden 0.05 mm under-mask support where clearance permits.',
            'back': 'No back copper/art; no solder paste and no silkscreen.',
            'stackup': 'Two copper-layer FR4 process assumed, 1.6 mm total; bare mask-only order option requires fab quotation.'},
    }
    (vector_dir/'fabrication.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    (vector_dir/'drills.json').write_text(json.dumps({'units':'mm', 'origin':'top panel upper-left',
                                            'drills':drills}, indent=2))
    record = {k:data[k] for k in ['id','designId','variant','category','layerNumber','maskColor',
                     'previewColorKey','finish','thicknessMm','boardBoundsMm','nativeBoard','metrics']}
    record['vectorDirectory'] = str(vector_dir.relative_to(out))
    record['nativeBoardSha256'] = hashlib.sha256(native.encode()).hexdigest()
    print(f'{stem}: {len(decorative)} routed cutouts, {len(drills)} NPTH, '
          f'Cu {copper.area:.2f} mm², gold trim {metrics["goldClippedFraction"]:.1%}', flush=True)
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=ROOT/'preview-source'/'assets'/'geometry.json')
    ap.add_argument('--output', type=Path, default=ROOT/'generated'/'rev5-export')
    ap.add_argument('--force', action='store_true', help='Explicitly allow overwriting files changed since the previous generated manifest')
    ap.add_argument('--allow-previous-revision', action='store_true', help='For development only; final deliverable requires revision 5')
    args = ap.parse_args()
    raw = args.input.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    if data.get('revision', 0) < 5 and not args.allow_previous_revision:
        raise ValueError('Final export requires Rev5 gold-border geometry; use --allow-previous-revision only for development')
    # Refuse to silently overwrite locally edited boards or vectors. Validate
    # the complete planned output set before generating the first board.
    planned = [args.output/'pcb'/'README.md', args.output/'pcb'/'manifest.csv']
    for original in data['designs']:
        variants = [(d, 'selected' if d.get('variantId')=='wide' else 'alternatives')
                    for d in original.get('variants', []) + [original]] if original['id']=='kumiko-void' else [(original,'selected')]
        for design, category in variants:
            slug = f'{int(design["number"]):02d}-{design["id"]}' + (f'-{design["variantId"]}' if design.get('variantId') else '')
            for layer in design['layers']:
                stem = f'{slug}-L{layer["index"]+1:02d}-{layer["colorKey"]}-{layer["finish"]}'
                planned.append(args.output/'pcb'/category/slug/(stem+'.kicad_pcb'))
                vdir=args.output/'resources'/'vector'/category/slug/stem
                planned.extend(vdir/name for name in ['Edge_Cuts.svg','Edge_Cuts.dxf','F_Cu.svg','F_Cu.dxf',
                    'F_Mask.svg','F_Mask.dxf','Drill.svg','Drill.dxf','front.svg','preview_gold.svg','preview_front.svg','fabrication.json','drills.json'])
    old_manifest=args.output/'pcb'/'manifest.json'
    old_hashes=json.loads(old_manifest.read_text()).get('generatedFiles',{}) if old_manifest.exists() else {}
    conflicts=[]
    for path in planned:
        if path.exists():
            relative=str(path.relative_to(args.output))
            if hashlib.sha256(path.read_bytes()).hexdigest()!=old_hashes.get(relative):
                conflicts.append(relative)
    if conflicts and not args.force:
        raise SystemExit('Refusing to overwrite locally edited/untracked generated files. Keep local edits in a separate working copy, use a new --output directory, or explicitly use --force.\n'+'\n'.join(conflicts[:20]))
    records = []
    for original in data['designs']:
        if original['id'] == 'kumiko-void':
            wide = next(d for d in original['variants'] if d.get('variantId')=='wide')
            variants = [(wide, 'selected'), (original, 'alternatives')]
        else:
            variants = [(original, 'selected')]
        for design, category in variants:
            for layer in design['layers']:
                records.append(export_layer(design, layer, category, data['spec'], source_hash, args.output))
    selected = [r for r in records if r['category']=='selected']
    assert len(records)==52 and len(selected)==43
    assert sum(r['finish']!='mask-only' for r in selected)==11
    report = {'schemaVersion':1, 'revision':5, 'sourceRevision':data['revision'],
        'sourceGeometrySha256':source_hash, 'exporter':'tools/export_kicad.py',
        'shapelyVersion':shapely.__version__, 'geosVersion':shapely.geos_version_string,
        'nativeFormat':'KiCad 8 .kicad_pcb / file version 20240108',
        'nativeKiCadParserValidated':False, 'nativeKiCadDrcRun':False,
        'validationStatus':'Geometric, XML and S-expression syntax checks passed. KiCad parser/DRC/CAM must run locally.',
        'notManufacturingRelease':True, 'defaultKumikoVariant':'wide',
        'manufacturingResolutionRequired':True,
        'manufacturingReviewReport':'validation/fabrication-review.json',
        'kumikoRoutingIssues':'resources/manufacturing-review/kumiko-routing-issues.csv',
        'selectedBoardCount':43,'alternativeBoardCount':9,
        'selectedEnigCount':11,'selectedMaskOnlyCount':32,
        'rules':RULES, 'spec':data['spec'], 'sources':SOURCES, 'boards':records,
        'remainingChecks':['Load every board in local KiCad 8+; inspect board outline and 3D view.',
            'Resolve documented sub-1 mm Kumiko decorative holes and narrow material ligament before release.',
            'Resolve documented sub-capability copper island gaps and narrow mask webs; edge clearance alone is not fabrication approval.',
            'Confirm routing cutter diameter and treatment of acute internal corners with manufacturer.',
            'Run native KiCad DRC and inspect plotted Gerber plus separate NPTH drill/slot files.',
            'Confirm mask registration and fine copper/mask features against chosen color/finish capability.',
            'Confirm each selected board mask color and ENIG grouping in quote; alternative Kumiko replaces its whole 9-board stack.']}
    columns = ['id','category','designId','variant','layerNumber','maskColor','finish','thicknessMm','nativeBoard','vectorDirectory']
    with (args.output/'pcb'/'manifest.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f, fieldnames=columns, extrasaction='ignore');writer.writeheader();writer.writerows(records)
    (args.output/'pcb'/'README.md').write_text('''# Editable KiCad handoff — revision 5

`selected/` contains 43 boards: one complete set of five designs with **Kumiko wide**.
`alternatives/17-kumiko-void-standard/` contains nine replacement boards for a standard Kumiko stack.
Do not order both Kumiko stacks unless you want two variants.

Each `.kicad_pcb` is a standalone native PCB, intended for KiCad 8 or later. No custom library install is required: mechanical NPTH footprints are embedded. This is a **handoff**, not a manufacturing release. Geometry/XML/S-expression checks ran here; native KiCad loading, DRC and CAM checks have **not** run here.

Known manufacturing decisions are recorded in `../validation/fabrication-review.json` and `../resources/manufacturing-review/`: Kumiko has positive-area decorative holes too small for the assumed Ø1 mm routing cutter, and some designs have copper island gaps / mask webs below the screened fabrication thresholds. These were retained, not silently redesigned. Configure a local KiCad project's fabrication rules, resolve these features, and review the final CAM before ordering.

## Layer semantics

- `Edge.Cuts`: exact outer shape and decorative cutout loops from the approved geometry. Angular Spider/Kumiko shapes remain angular.
- Four Ø3.2 mm mounting holes are native **NPTH pads** on each board. The top board also has four native 10.28 × 3.2 mm oval NPTH slots. These holes do not also appear on `Edge.Cuts`.
- `F.Cu`: editable positive filled graphic polygons, including 0.05 mm extra hidden copper under the visible gold design. These are not net-connected zones. No refill operation is required.
- `F.Mask`: positive mask **openings**, exposing the gold artwork. Black Kumiko facets were resolved as mask-covered regions in the same paint order as the 3D preview.
- No `B.Cu` art, no silkscreen, no solder paste. Mask-only boards contain zero decorative copper or mask-opening graphics. NPTH pad size equals drill, so it creates no copper annulus.
- Mask colors and finish intent are in board stackup metadata and `manifest.csv`. Select the same colors/finish on the order form. Stackup specifies the common two-copper-layer FR4 process; it does not claim copper-free laminate.

## Explicit fabrication adaptation

Visible gold is clipped to at least **0.35 mm from routed/drilled edges**. Copper extends 0.05 mm under the mask and stays at least **0.30 mm from those edges**. This selected policy is not factory approval. `manifest.json` and each vector folder's `fabrication.json` record the exact gold area clipped from the preview. Full-gold sheets therefore have a narrow masked strip around their cut edges and holes.

The masks and copper are split into simple positive polygons only where a region contains a hole. This makes native KiCad artwork editable while avoiding accidental fill over a decorative aperture. Exact component geometry is also provided as `fabrication.json` and filled SVG.

## Vector interchange

`../resources/vector/<selected|alternatives>/<design>/<board>/` contains:

- `Edge_Cuts.svg` / `.dxf`: routed outer and decorative contours, excluding functional drills.
- `F_Cu.svg`, `F_Mask.svg`: filled positive regions at true millimetre scale.
- `F_Cu.dxf`, `F_Mask.dxf`: closed boundary interchange; these DXFs do not encode filled copper. Prefer the native board or SVG for positive area semantics.
- `Drill.svg` / `.dxf` and `drills.json`: registration reference only. Do not import these as extra `Edge.Cuts`; native NPTH pads already define them.
- `front.svg`: color/gold inspection image at true millimetre scale.
- `preview_gold.svg`, `preview_front.svg`: approved visible artwork **before** the export clearance adaptation; compare with `F_Mask.svg` and `front.svg`. These are design references, not extra manufacturing layers.
- `fabrication.json`: exact exported positive polygons, holes, drill centers, rules and metrics.

All SVGs use `width="101.3mm" height="128.5mm" viewBox="0 0 101.3 128.5"`. All layers share the top panel's upper-left origin. Lower boards retain their `y=17.1` offset and have actual bounds **101.3 × 94.3 mm**. Do not fit to page or rescale. DXF uses millimetres and normal CAD Y-up, so its Y values are `-previewY`; the origin remains the same.

## Regenerate

```sh
python -m venv .venv
.venv/bin/pip install shapely==2.1.2
.venv/bin/python tools/export_kicad.py --input preview-source/assets/geometry.json --output regenerated
```

Changing geometry or export rules regenerates these files. The exporter checks previous generated file hashes and refuses to replace changed/untracked native boards or vectors. Keep local KiCad manual edits in a separate working copy, choose a new `--output` folder, or explicitly use `--force` after preserving your edits. It never silently overwrites edits. Port intended changes into the generator before regenerating.

## Local native KiCad validation and CAM review

`tools/local_kicad_check.py` is prepared for KiCad 8+ and detects the macOS application CLI path. It does not edit source boards. Its native commands were **not executed in this session**.

```sh
python tools/local_kicad_check.py --output local-review-01 --plan
python tools/local_kicad_check.py --output local-review-01 --export-cam
```

Default is the selected 43-board set. Use `--category alternatives` for the nine standard Kumiko boards, or `--category all` for both. Use `--boards-root /path/to/your/working-copy` for a mirrored local `pcb/` tree after edits. The output directory must be new/empty. DRC violations remain in reports, return exit code 5, and are not suppressed. `--export-cam` also generates Gerbers and separated non-plated Excellon holes/route slots for **review**, including boards with DRC violations, so the results are never automatically treated as a manufacturing release.

Official references: [KiCad board format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/), [KiCad common/graphics/pad format](https://dev-docs.kicad.org/en/file-formats/sexpr-intro/), [JLCPCB capability table](https://jlcpcb.com/capabilities/pcb-capabilities), [KiCad 8 CLI](https://docs.kicad.org/8.0/en/cli/cli.html).
''')
    report['generatedFiles']={str(path.relative_to(args.output)):hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in planned}
    (args.output/'pcb'/'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'Wrote {len(records)} native boards: 43 selected / 9 alternatives; 11 selected ENIG.',flush=True)


if __name__ == '__main__':
    main()
