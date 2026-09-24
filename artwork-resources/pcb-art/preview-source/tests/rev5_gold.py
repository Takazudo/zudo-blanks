#!/usr/bin/env python3
"""Audit Revision 5 decorative borders against the immutable Revision 4 boards.

This checks the exported coordinates used by the viewer/exporters. It is not
factory DRC, and makes no claim that a decorative hole collar is a plated hole.
"""
import hashlib
import json
import sys
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'assets' / 'geometry.json'
BASELINE = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'assets' / 'reference-revision4.json'
OUTPUT = ROOT / 'tests' / 'output' / 'rev5-gold-report.json'


def flatten(data):
    result = {}
    for family in data['designs']:
        for design in [family, *family.get('variants', [])]:
            key = design['id'] + (':' + design['variantId'] if design.get('variantId') else '')
            result[key] = design
    return result


def copper(stroke, angular):
    points = stroke['pts']
    assert stroke.get('closed') is True, 'An outline must be a closed path'
    if points[0] != points[-1]:
        points = points + [points[0]]
    return LineString(points).buffer(stroke['w'] / 2,
        cap_style=2 if angular else 1, join_style=2 if angular else 1)


def physical_signature(designs):
    records = {key: [{'outer': layer['outer'], 'holes': layer['holes']}
                     for layer in design['layers']] for key, design in designs.items()}
    return hashlib.sha256(json.dumps(records, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def main():
    data, previous = json.loads(SOURCE.read_text()), json.loads(BASELINE.read_text())
    assert data['revision'] == 5 and previous['revision'] == 4
    current, baseline = flatten(data), flatten(previous)
    assert current.keys() == baseline.keys() and len(current) == 6
    assert data['spec'] == previous['spec'], 'Physical dimensions/hardware specification changed'
    before_hash, after_hash = physical_signature(baseline), physical_signature(current)
    assert before_hash == after_hash, 'Rev5 changed an actual outline or drill coordinate'
    results = {}
    board_count = 0
    for key, design in current.items():
        old = baseline[key]
        assert len(design['layers']) == len(old['layers'])
        assert design['finishSummary'] == old['finishSummary']
        for layer, original in zip(design['layers'], old['layers']):
            for field in ('index', 'colorKey', 'mask', 'surface', 'solid', 'finish', 'finishLabel'):
                assert layer[field] == original[field], f'{key}: {field} changed'
            if layer['index'] > 0:
                assert layer['art'] == original['art'], f'{key}: lower-layer artwork changed'
                assert not layer.get('goldBorders'), f'{key}: top borders were added to a lower PCB'
            board_count += 1
        top, old_top = design['layers'][0], old['layers'][0]
        assert top['art']['fills'] == old_top['art']['fills'], f'{key}: filled top motif changed'
        old_strokes = old_top['art']['strokes']
        if design['id'] in ('fault-line', 'woven-maze'):
            # Revision 4 appended nine untagged legacy rims after the motif.
            old_strokes = old_strokes[:-9]
        assert top['art']['strokes'][:-9] == old_strokes, f'{key}: preexisting top motif changed'
        rims = [s for s in top['art']['strokes'] if s.get('purpose') == 'top-gold-border']
        assert len(rims) == 9 and top['art']['strokes'][-9:] == rims
        assert not any(s.get('color') for s in rims), f'{key}: a rim is not gold'
        expected_features = ['perimeter'] + ['stack-hole'] * 4 + ['rail-slot'] * 4
        assert [s.get('feature') for s in rims] == expected_features
        angular = design.get('artStyle') == 'angular'
        shape = Polygon(top['outer'], top['holes'])
        assert shape.is_valid and shape.geom_type == 'Polygon'
        footprints = [copper(s, angular) for s in rims]
        outside = [p.difference(shape).area for p in footprints]
        assert max(outside) < 1e-7, f'{key}: border copper falls outside the actual board'
        # The full-width frame itself must remain unbroken after clipping.
        for outline, footprint in zip(rims, footprints):
            assert footprint.intersection(shape).equals(footprint), f'{key}: border needs clipping'
        frame = footprints[0]
        rail_rims = footprints[5:]
        assert all(p.intersects(frame) for p in rail_rims), f'{key}: accidental frame-to-slot mask sliver'
        for index, (x, y) in enumerate(data['spec']['screws']):
            ring = footprints[index + 1]
            assert ring.distance(Point(x, y)) > 1.6, f'{key}: copper enters a screw drill'
            island = Point(x, y).buffer(3.05)
            assert ring.difference(island).area < 1e-7, f'{key}: collar exceeds guaranteed mounting island'
        frame_clearance = frame.distance(box(0, 0, data['spec']['width'], data['spec']['height']).boundary)
        assert frame_clearance > .389, f'{key}: copper too close to outside board edge'
        metadata = design['topGoldBorders']
        assert metadata == top['goldBorders']
        assert metadata['closedStrokeCount'] == 9 and metadata['allCopperInsideBoard']
        assert metadata['flatArtwork'] and not metadata['platedHolesRequired'] and not metadata['edgePlatingRequired']
        if design['id'] in ('spider-nest', 'kumiko-void'):
            assert metadata['stackHoles']['outline'] == 'octagonal'
            assert all(len(s['pts']) == 8 for s in rims[1:5])
            assert metadata['railSlots']['outline'] == 'rectangular'
        results[key] = {
            'boardCount': len(design['layers']), 'physicalGeometryUnchanged': True,
            'lowerArtworkUnchanged': True, 'preexistingTopMotifUnchanged': True,
            'paletteAndFinishUnchanged': True, 'rimStrokesDrawnLast': True,
            'taggedClosedBorderCount': 9, 'outsideCopperAreaMm2': max(outside),
            'minimumCopperToBoardBoundaryMm': round(min(p.distance(shape.boundary) for p in footprints), 4),
            'parameters': metadata,
        }
    assert board_count == 52
    output = {
        'revision': 5, 'source': str(SOURCE), 'baseline': str(BASELINE),
        'physicalGeometryHash': {'algorithm': 'sha256', 'revision4': before_hash, 'revision5': after_hash},
        'boardRecords': board_count, 'effectiveTopVariants': len(results),
        'totalClosedRimStrokes': sum(v['taggedClosedBorderCount'] for v in results.values()),
        'designs': results, 'passed': True,
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'boardRecords': board_count,
        'topVariants': len(results), 'physicalGeometryUnchanged': True,
        'report': str(OUTPUT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
