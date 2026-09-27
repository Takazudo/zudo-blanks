#!/usr/bin/env python3
"""Independent handoff audit. This is NOT a KiCad parser, DRC or CAM check.

Parses native S-expressions without importing the exporter, compares native
Edge.Cuts segments/drills directly with canonical millimetre geometry, and
compares graphic polygon sets with the portable fabrication/vector records.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')

def parse(text):
    stack, root = [], None
    for match in TOKEN.finditer(text):
        token = match.group()
        if token == '(':
            item = []
            if stack: stack[-1].append(item)
            else:
                assert root is None, 'Multiple root forms'
                root = item
            stack.append(item)
        elif token == ')':
            assert stack, 'Unexpected closing parenthesis'
            stack.pop()
        else:
            assert stack, 'Atom outside a form'
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    assert root is not None and not stack, 'Unclosed S-expression'
    return root

def children(form, tag):
    return [x for x in form[1:] if isinstance(x, list) and x and x[0] == tag]

def child(form, tag):
    records = children(form, tag)
    assert len(records) == 1, f'Expected one {tag}, got {len(records)}'
    return records[0]

def xy(form, tag):
    return tuple(float(x) for x in child(form, tag)[1:3])

def segment(a, b):
    return tuple(sorted((tuple(a), tuple(b))))

def ring_segments(ring):
    pts = list(map(tuple, ring))
    if pts[-1] != pts[0]: pts.append(pts[0])
    return [segment(a, b) for a, b in zip(pts, pts[1:]) if a != b]

def polygon_records(records):
    return unary_union([Polygon(item['outer'], item['holes']) for item in records]) if records else Polygon()

def main():
    ap = argparse.ArgumentParser(description='Independent geometry and S-expression audit; not KiCad DRC or CAM.')
    ap.add_argument('--geometry', type=Path, default=ROOT/'preview-source'/'assets'/'geometry.json')
    ap.add_argument('--manifest', type=Path, default=ROOT/'pcb'/'manifest.json')
    ap.add_argument('--boards-root', type=Path, default=ROOT.parents[1],
                    help='Root used to resolve nativeBoard paths in the selected manifest.')
    ap.add_argument('--vectors-root', type=Path, default=ROOT/'generated'/'rev5-export',
                    help='Generated export root used to resolve vectorDirectory paths in the selected manifest.')
    ap.add_argument('--output', type=Path, default=ROOT/'generated'/'audit'/'native-independent-audit.json')
    args = ap.parse_args()
    geometry = json.loads(args.geometry.read_text())
    manifest = json.loads(args.manifest.read_text())
    assert geometry['revision'] == 5
    spec = geometry['spec']
    geometry_lookup = {}
    for family in geometry['designs']:
        for design in [family, *family.get('variants', [])]:
            variant = design.get('variantId')
            for layer in design['layers']:
                geometry_lookup[(design['id'], variant, layer['index'] + 1)] = (design, layer)

    expected = {}
    for record in manifest['boards']:
        ident = (record['designId'], record.get('variant'), record['layerNumber'])
        assert ident in geometry_lookup, f"Manifest board has no canonical geometry: {record['id']}"
        expected[record['nativeBoard']] = (*geometry_lookup[ident], record['category'], record)
    assert len(expected) == 52, f"Expected 52 manifest boards, found {len(expected)}"
    actual_paths = {key: args.boards_root / key for key in expected}
    missing = [str(path) for path in actual_paths.values() if not path.is_file()]
    assert not missing, 'Missing native boards: ' + ', '.join(missing)

    result = {'revision':5,'scope':'Independent S-expression and geometric consistency checks; KiCad application parser/DRC/CAM not run',
              'kiCadApplicationRun':False,'selectedBoards':0,'alternativeBoards':0,'selectedENIG':0,'selectedMaskOnly':0,
              'boards':[], 'svgFiles':0,'dxfFiles':0}
    uuids = set()
    for key in sorted(expected):
        path = actual_paths[key]
        design, layer, category, record = expected[key]
        board = parse(path.read_text())
        assert board[0] == 'kicad_pcb' and child(board,'version')[1] == '20240108'
        assert float(child(child(board,'general'),'thickness')[1]) == spec['thickness']
        native_lines = [form for form in children(board,'gr_line') if child(form,'layer')[1] == 'Edge.Cuts']
        actual_segments = Counter(segment(xy(line,'start'),xy(line,'end')) for line in native_lines)
        mount_centers = list(spec['screws']) + (list(spec['slots']) if layer['index'] == 0 else [])
        decorative = [ring for ring in layer['holes'] if not any(Polygon(ring).contains(Point(*p)) for p in mount_centers)]
        expected_segments = Counter(edge for ring in [layer['outer'],*decorative] for edge in ring_segments(ring))
        assert actual_segments == expected_segments, f'{key}: native Edge.Cuts differs from exact canonical geometry'
        assert not children(board,'gr_arc') and not children(board,'gr_circle'), f'{key}: unexpected alternate routed-outline primitives'
        expected_drills = [(float(x),float(y),3.2,3.2,'circle') for x,y in spec['screws']]
        if layer['index'] == 0:
            expected_drills += [(float(x),float(y),10.28,3.2,'oval') for x,y in spec['slots']]
        actual_drills = []
        physical_drills = []
        for fp in children(board,'footprint'):
            x,y = xy(fp,'at')
            for pad in children(fp,'pad'):
                assert pad[2] == 'np_thru_hole', f'{key}: hole unexpectedly plated'
                assert xy(pad,'at') == (0,0)
                size = xy(pad,'size')
                drill = child(pad,'drill')
                kind = 'oval' if drill[1] == 'oval' else 'circle'
                dims = tuple(map(float,drill[2:4])) if kind == 'oval' else (float(drill[1]),)*2
                assert size == dims, f'{key}: NPTH pad contains an unintended annulus'
                assert child(pad,'layers')[1:] == ['*.Cu','*.Mask']
                actual_drills.append((x,y,*dims,kind))
                physical_drills.append(Point(x,y).buffer(dims[0]/2,quad_segs=128) if kind == 'circle' else LineString([(x-(dims[0]-dims[1])/2,y),(x+(dims[0]-dims[1])/2,y)]).buffer(dims[1]/2,quad_segs=128))
        assert Counter(actual_drills) == Counter(expected_drills), f'{key}: native drill location/shape/diameter mismatch'
        material = Polygon(layer['outer'], decorative).difference(unary_union(physical_drills))
        native_art = {'F.Cu':[], 'F.Mask':[]}
        for graphic in children(board,'gr_poly'):
            side = child(graphic,'layer')[1]
            assert side in native_art, f'{key}: unexpected graphic layer {side}'
            assert child(graphic,'fill')[1] == 'solid'
            coords = [tuple(map(float,p[1:])) for p in child(graphic,'pts')[1:]]
            polygon = Polygon(coords)
            assert polygon.is_valid and polygon.area > 0, f'{key}: invalid native art polygon'
            native_art[side].append(polygon)
        copper, mask = (unary_union(native_art[side]) if native_art[side] else Polygon() for side in ['F.Cu','F.Mask'])
        if layer['finish'] == 'mask-only':
            assert copper.is_empty and mask.is_empty
        else:
            assert copper.area > 0 and mask.area > 0
        assert mask.difference(copper).area < 0.0001, f'{key}: mask opens onto copper-free substrate'
        for side, ink, limit in [('F.Cu',copper,0.30),('F.Mask',mask,0.35)]:
            if ink.is_empty:
                continue
            assert ink.difference(material).area < 0.0001, f'{key}: {side} leaves its PCB'
            assert ink.distance(material.boundary) >= limit-0.00002, f'{key}: {side} edge clearance mismatch'
        vector_dir = args.vectors_root / record['vectorDirectory']
        fabrication = json.loads((vector_dir/'fabrication.json').read_text())
        for side, ink, item_key in [('F.Cu',copper,'frontCopper'),('F.Mask',mask,'frontMaskOpenings')]:
            assert ink.symmetric_difference(polygon_records(fabrication[item_key])).area < 0.002, f'{key}: {side} native/vector positive areas differ'
        for svg in vector_dir.glob('*.svg'):
            xml = ET.parse(svg).getroot()
            assert xml.attrib['width'] == '101.3mm' and xml.attrib['height'] == '128.5mm'
            assert list(map(float,xml.attrib['viewBox'].split())) == [0,0,101.3,128.5]
            result['svgFiles'] += 1
        for dxf in vector_dir.glob('*.dxf'):
            lines = dxf.read_text().splitlines()
            groups = [(lines[i].strip(),lines[i+1].strip()) for i in range(0,len(lines),2)]
            index = groups.index(('9','$INSUNITS'))
            assert groups[index+1] == ('70','4'), f'{dxf.name}: DXF is not millimetres'
            result['dxfFiles'] += 1
        identifiers = re.findall(r'\(uuid "([^"]+)"\)',path.read_text())
        assert len(set(identifiers)) == len(identifiers) and not uuids.intersection(identifiers), f'{key}: duplicate UUID'
        uuids.update(identifiers)
        selected = category == 'selected'
        result['selectedBoards' if selected else 'alternativeBoards'] += 1
        if selected:
            result['selectedMaskOnly' if layer['finish'] == 'mask-only' else 'selectedENIG'] += 1
        result['boards'].append({'file':key,'outlineSegments':len(native_lines),'functionalDrills':len(actual_drills),
            'copperPolygons':len(native_art['F.Cu']),'maskPolygons':len(native_art['F.Mask']),
            'copperAreaMm2':round(copper.area,5),'exposedGoldAreaMm2':round(mask.area,5),
            'closedCanonicalContours':1+len(decorative),'passed':True})
    assert (result['selectedBoards'],result['alternativeBoards'],result['selectedENIG'],result['selectedMaskOnly']) == (43,9,11,32)
    assert result['svgFiles'] == 52*7 and result['dxfFiles'] == 52*4
    result['passed'] = True
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ['passed','selectedBoards','alternativeBoards','selectedENIG',
        'selectedMaskOnly','svgFiles','dxfFiles','kiCadApplicationRun']}))
    print(args.output)


if __name__ == '__main__':
    main()
