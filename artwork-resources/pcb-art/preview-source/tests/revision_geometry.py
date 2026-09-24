#!/usr/bin/env python3
"""Independent revision-5 checks against actual polygons and flat ENIG borders."""
import json
import math
import os
import sys
from itertools import combinations
from pathlib import Path
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'assets' / 'geometry.json'
BASELINE = Path(os.environ.get('PCB_PREVIEW_BASELINE', ROOT / 'assets' / 'reference-revision3.json'))
PREVIOUS = ROOT / 'assets' / 'reference-revision4.json'
OUTPUT = ROOT / 'tests' / 'output' / 'revision-geometry-report.json'


def body(layer, baseline=False):
    # Revision 3 contained a few zero-area rings created by coordinate rounding.
    # They have no physical footprint; permit their removal only in the baseline.
    holes = [ring for ring in layer['holes'] if Polygon(ring).area > 0] if baseline else layer['holes']
    shape = Polygon(layer['outer'], holes)
    assert shape.is_valid and shape.geom_type == 'Polygon', f"Invalid/disconnected PCB L{layer['index'] + 1}"
    return shape


def apertures(layer, spec):
    centers = [Point(*xy) for xy in spec['screws'] + spec['slots']]
    holes = [Polygon(ring) for ring in layer['holes']]
    return unary_union([hole for hole in holes if not any(hole.covers(center) for center in centers)])


def gold_footprint(design):
    top = design['layers'][0]
    footprints = [Polygon(item['pts']) for item in top['art']['fills'] if not item.get('color')]
    angular = design.get('artStyle') == 'angular'
    for item in top['art']['strokes']:
        if item.get('color') or len(item['pts']) < 2:
            continue
        points = item['pts']
        if item.get('closed') and points[0] != points[-1]:
            points = points + [points[0]]
        footprints.append(LineString(points).buffer(item['w'] / 2,
            cap_style=2 if angular else 1, join_style=2 if angular else 1))
    assert footprints and all(poly.is_valid for poly in footprints), f"{design['id']}: invalid/missing ENIG footprint"
    return unary_union(footprints).intersection(body(top))


def main():
    data, baseline = json.loads(SOURCE.read_text()), json.loads(BASELINE.read_text())
    previous = json.loads(PREVIOUS.read_text())
    assert data['revision'] == 5, 'Build revision 5 before running focused QA'
    assert baseline['revision'] == 3
    assert previous['revision'] == 4
    families = {d['id']: d for d in data['designs']}
    old = {d['id']: d for d in baseline['designs']}
    assert len(families) == 5 and set(families) == set(old), 'Variants must not increase the five-family navigation'
    active = {key: next((v for v in d.get('variants', []) if v['variantId'] == d.get('defaultVariant')), d) for key, d in families.items()}
    spec, width, height = data['spec'], data['spec']['width'], data['spec']['height']
    window = box(10.5, 27.0, width - 10.5, height - 27.0)
    zones = {
        'top': box(0, 0, width, 27.0), 'bottom': box(0, height - 27.0, width, height),
        'left': box(0, 27.0, 10.5, height - 27.0),
        'right': box(width - 10.5, 27.0, width, height - 27.0), 'center': window,
    }
    result = {'revision': 5, 'source': str(SOURCE), 'baseline': str(BASELINE), 'previousRevision': str(PREVIOUS), 'patternCoverage': {}, 'growth': {}, 'wovenPaths': {}, 'progression': {}, 'structuralChecks': {}, 'goldBorders': {}}

    def variants(records):
        return {(design['id'], design.get('variantId')): design for family in records for design in [family, *family.get('variants', [])]}

    previous_designs, current_designs = variants(previous['designs']), variants(data['designs'])
    assert current_designs.keys() == previous_designs.keys()
    assert spec == previous['spec'], 'Revision 5 must not alter physical dimensions or drilling'
    for identity, design in current_designs.items():
        old_design = previous_designs[identity]
        key = ':'.join(str(value) for value in identity if value is not None)
        for before, after in zip(old_design['layers'], design['layers']):
            assert before['outer'] == after['outer'] and before['holes'] == after['holes'], f'{key}: revision-4 physical outline/drills changed'
            if after['index']:
                assert before['art'] == after['art'], f'{key}/L{after["index"] + 1}: lower artwork changed'
                assert 'goldBorders' not in after
        top, meta = design['layers'][0], design['topGoldBorders']
        assert meta == top['goldBorders']
        assert meta['topOnly'] and meta['flatArtwork'] and meta['drillsUnchanged']
        assert not meta['platedHolesRequired'] and not meta['edgePlatingRequired']
        borders = [item for item in top['art']['strokes'] if item.get('purpose') == 'top-gold-border']
        assert len(borders) == meta['closedStrokeCount'] == 9
        assert [item['feature'] for item in borders].count('perimeter') == 1
        assert [item['feature'] for item in borders].count('stack-hole') == 4
        assert [item['feature'] for item in borders].count('rail-slot') == 4
        shape, angular = body(top), design.get('artStyle') == 'angular'
        details = []
        for item in borders:
            assert item['closed'] and not item.get('color')
            points = item['pts'] + ([item['pts'][0]] if item['pts'][0] != item['pts'][-1] else [])
            footprint = LineString(points).buffer(item['w'] / 2, cap_style=2 if angular else 1, join_style=2 if angular else 1)
            assert footprint.difference(shape).area < 0.001, f'{key}: {item["feature"]} copper leaves PCB material'
            assert footprint.distance(shape.boundary) > 0.08, f'{key}: inadequate border clearance'
            if item['feature'] == 'stack-hole':
                center = Point(*spec['screws'][item['featureIndex']])
                assert Polygon(points).contains(center), f'{key}: border does not surround its screw hole'
                if design['id'] in ['spider-nest', 'kumiko-void']:
                    assert len(set(map(tuple, points))) == 8, f'{key}: angular ring must have straight octagonal facets'
            if item['feature'] == 'rail-slot':
                assert Polygon(points).contains(Point(*spec['slots'][item['featureIndex']])), f'{key}: border does not surround its rail slot'
                if design['id'] in ['spider-nest', 'kumiko-void']:
                    assert len(set(map(tuple, points))) == 4, f'{key}: angular rail-slot frame must be rectangular'
            details.append({'feature': item['feature'], 'index': item.get('featureIndex'), 'copperAreaMm2': round(footprint.area, 4), 'minimumBoardBoundaryClearanceMm': round(footprint.distance(shape.boundary), 4)})
        result['goldBorders'][key] = {'closedFeatures': 9, 'actualCopperInsideBoard': True, 'topOnly': True, 'features': details}
    result['revision4Preservation'] = {'boardRecords': sum(len(d['layers']) for d in current_designs.values()), 'allOutlinesAndDrillsExactlyUnchanged': True, 'allLowerArtworkExactlyUnchanged': True}

    for key, design in active.items():
        before, after = apertures(old[key]['layers'][0], baseline['spec']), apertures(design['layers'][0], spec)
        ratio = after.area / before.area
        assert ratio > 1.05, f'{key}: top opening must be materially larger than revision 3'
        assert after.bounds[1] > spec['keepout'] and after.bounds[3] < height - spec['keepout'], f'{key}: front opening extends into the lower-PCB rail keepout'
        result['growth'][key] = {'beforeAreaMm2': round(before.area, 4), 'afterAreaMm2': round(after.area, 4), 'ratio': round(ratio, 6), 'beforeBounds': list(before.bounds), 'afterBounds': list(after.bounds), 'variantId': design.get('variantId')}

    for family in families.values():
        for design in [family, *family.get('variants', [])]:
            key = design['id'] + (':' + design['variantId'] if design.get('variantId') else '')
            for layer in design['layers']:
                shape = body(layer)
                eroded = shape.buffer(-0.5)
                pieces = list(eroded.geoms) if hasattr(eroded, 'geoms') else [eroded]
                assert not eroded.is_empty and len([p for p in pieces if p.area > 0.02]) == 1, f'{key}/L{layer["index"] + 1}: narrow connection fails 0.5 mm inward check'
                for x, y in spec['screws']:
                    support = Point(x, y).buffer(3.05).difference(Point(x, y).buffer(1.6001))
                    assert support.difference(shape).area < 0.005, f'{key}/L{layer["index"] + 1}: incomplete screw support'
            result['structuralChecks'][key] = {'connectedLayers': len(design['layers']), 'supports': True, 'inwardOffsetMm': 0.5}

    standard = families['kumiko-void']
    assert standard['variantId'] == 'standard' and standard['defaultVariant'] == 'wide'
    wide = next(v for v in standard['variants'] if v['variantId'] == 'wide')
    for i, (previous, current) in enumerate(zip(old['kumiko-void']['layers'], standard['layers'])):
        assert body(previous, baseline=True).equals(body(current)), f'Kumiko standard L{i + 1} geometry changed'
        if i:
            assert previous['art'] == current['art'], f'Kumiko standard lower L{i + 1} artwork changed'
    assert apertures(wide['layers'][0], spec).area > apertures(standard['layers'][0], spec).area
    result['kumikoVariants'] = {'standardGeometryUnchanged': True, 'standardLowerArtworkUnchanged': True, 'topBorderAddedToBoth': True, 'default': 'wide', 'standardOpeningMm2': round(apertures(standard['layers'][0], spec).area, 4), 'wideOpeningMm2': round(apertures(wide['layers'][0], spec).area, 4)}

    for key in ['spider-nest', 'coral-vault', 'kumiko-void']:
        design = active[key]
        shape, gold = body(design['layers'][0]), gold_footprint(design)
        result['patternCoverage'][key] = {}
        for label, zone in zones.items():
            solid, ink = shape.intersection(zone), gold.intersection(zone)
            assert solid.area > 0 and ink.area > 0, f'{key}/{label}: missing pattern on the remaining face'
            result['patternCoverage'][key][label] = {'solidMm2': round(solid.area, 4), 'goldMm2': round(ink.area, 4)}

    shapes = [body(layer).intersection(window) for layer in active['woven-maze']['layers'][1:8]]
    differences = []
    for i, j in combinations(range(7), 2):
        assert not shapes[i].equals(shapes[j]), f'Woven L{i + 2} and L{j + 2} repeat the same central geometry'
        differences.append({'layers': [i + 2, j + 2], 'differentAreaMm2': round(shapes[i].symmetric_difference(shapes[j]).area, 4)})
    result['wovenPaths'] = {'layers': list(range(2, 9)), 'pairwiseDistinct': True, 'comparisons': differences}

    for key in ['coral-vault', 'fault-line']:
        holes = [apertures(layer, spec) for layer in active[key]['layers'][:-1]]
        assert all(not hole.is_empty for hole in holes)
        for index, (front, deeper) in enumerate(zip(holes, holes[1:])):
            tolerance = (front.length + deeper.length) * 0.0001 * math.sqrt(2)
            assert deeper.area < front.area, f'{key}: openings do not shrink at L{index + 2}'
            assert deeper.difference(front).area <= tolerance, f'{key}: deeper opening protrudes beyond L{index + 1}'
        result['progression'][key] = {'nested': True, 'areasMm2': [round(h.area, 4) for h in holes], 'componentCounts': [len(h.geoms) if hasattr(h, 'geoms') else 1 for h in holes], 'shapeCompactness': [round(4 * math.pi * h.area / h.length ** 2, 4) for h in holes]}

    result['configurationTotals'] = {'families': len(active), 'boards': sum(len(d['layers']) for d in active.values()), 'enigBoards': sum(d['finishSummary']['enigCount'] for d in active.values())}
    assert result['configurationTotals'] == {'families': 5, 'boards': 43, 'enigBoards': 11}
    result['passed'] = True
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'growthRatios': {k: v['ratio'] for k, v in result['growth'].items()}, 'report': str(OUTPUT)}))


if __name__ == '__main__':
    main()
