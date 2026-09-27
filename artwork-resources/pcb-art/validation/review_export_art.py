#!/usr/bin/env python3
"""Read exported physical art; record manufacturing review coordinates.

Never mutates native PCB files, source art, or vector geometry.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from shapely.geometry import Polygon, Point, LineString
from shapely import STRtree
from shapely.ops import unary_union, nearest_points

HERE = Path(__file__).resolve().parent
HANDOFF = HERE.parent


def geometry(items):
    return [Polygon(x['outer'], x['holes']) for x in items]


def gap_pairs(polygons, threshold, feature):
    if not polygons:
        return []
    tree = STRtree(polygons)
    pairs = []
    for i, p in enumerate(polygons):
        for j in tree.query(p, predicate='dwithin', distance=threshold):
            j = int(j)
            if j <= i:
                continue
            distance = p.distance(polygons[j])
            if distance >= threshold - 1e-7:
                continue
            a,b = nearest_points(p, polygons[j])
            pairs.append({'feature':feature, 'polygonIndices0':[i,j], 'gapMm':round(distance,9),
                'closestPointsMm':[list(a.coords[0]),list(b.coords[0])],
                'screenThresholdMm':threshold})
    return sorted(pairs,key=lambda x:x['gapMm'])


def edge_clearance(art, d):
    if art.is_empty:
        return None
    outline = Polygon(d['edgeCuts']['outer'], d['edgeCuts']['cutouts'])
    candidates = [art.distance(outline.boundary)]
    for drill in d['drills']:
        x,y,w,h = (drill[k] for k in ['x','y','width','height'])
        if drill['shape']=='circle':
            candidates.append(art.distance(Point(x,y))-w/2)
        else:
            half=(w-h)/2
            candidates.append(art.distance(LineString([(x-half,y),(x+half,y)]))-h/2)
    return round(min(candidates),9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors-root', type=Path, default=HANDOFF/'generated'/'rev5-export'/'resources'/'vector')
    parser.add_argument('--output-dir', type=Path, default=HANDOFF/'generated'/'export-art-review',
                        help='New generated report directory; imported source evidence is left untouched.')
    args = parser.parse_args()
    vector_root = args.vectors_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        source_pattern = vector_root.relative_to(HANDOFF).as_posix() + '/**/fabrication.json'
    except ValueError:
        source_pattern = 'custom vector root/**/fabrication.json'
    sources = sorted(vector_root.rglob('fabrication.json'))
    assert len(sources) == 52, f'Expected 52 exported boards, found {len(sources)}'
    report = {'schemaVersion':1,'revision':5,'manufacturingResolutionRequired':True,
        'sourcePattern':source_pattern,
        'scope':'Independent exported F.Cu/F.Mask geometric screening; not KiCad DRC or CAM approval.',
        'criteria':{
            'copperGapScreenMm':.10,'blackMaskGapScreenMm':.13,
            'maskSmallComponentDiameterHeuristicMm':.13,
            'maskSmallComponentHeuristicIsFactoryMinimum':False,
            'edgeClearanceNumericToleranceMm':.001,
            'source':'https://jlcpcb.com/capabilities/pcb-capabilities',
            'note':'Copper 0.10 mm and black-mask bridge 0.13 mm are screening thresholds from the cited capability table. Tip-to-tip measurements flag local mask features; they do not guarantee whole-feature printability.'},
        'boards':[]}
    csv_rows=[]
    representative_rows=[]
    for path in sources:
        raw=path.read_bytes()
        d=json.loads(raw)
        cu=geometry(d['frontCopper'])
        mask=geometry(d['frontMaskOpenings'])
        copper=unary_union(cu)
        gold=unary_union(mask)
        cp=gap_pairs(cu,.10,'F.Cu island gap')
        mp=gap_pairs(mask,.13,'F.Mask black gap')
        tiny=[{'polygonIndex0':i,'areaMm2':round(p.area,9),'boundsMm':list(p.bounds)}
            for i,p in enumerate(mask) if p.buffer(-.065).is_empty]
        cclear=edge_clearance(copper,d)
        mclear=edge_clearance(gold,d)
        uncovered=gold.difference(copper).area
        try:
            source_label=path.relative_to(HANDOFF).as_posix()
        except ValueError:
            source_label=path.name
        rec={'boardId':d['id'],'designId':d['designId'],'variant':d['variant'],'category':d['category'],
            'layerNumber':d['layerNumber'],'finish':d['finish'],
            'source':source_label,'sourceSha256':hashlib.sha256(raw).hexdigest(),
            'copperPositiveComponents':len(cu),'maskOpeningPositiveComponents':len(mask),
            'copperMinEdgeAndTrueDrillClearanceMm':cclear,
            'maskMinEdgeAndTrueDrillClearanceMm':mclear,
            'maskUncoveredByCopperAreaMm2':round(uncovered,9),
            'clearanceAndContainmentPass':(cclear is None or cclear>=.299) and (mclear is None or mclear>=.349) and uncovered<.0001,
            'maskOnlyHasNoDecorativeCopperOrMaskOpenings':d['finish']!='mask-only' or (not cu and not mask and not d['backCopper'] and not d['backMaskArtOpenings']),
            'previewGoldAreaMm2':d['metrics']['previewGoldAreaMm2'],
            'exportedGoldAreaMm2':round(gold.area,6),
            'goldClippedFraction':d['metrics']['goldClippedFraction'],
            'copperGapsBelow010Mm':cp,'blackMaskGapsBelow013Mm':mp,
            'maskComponentsNo013MmCircleFitsHeuristic':tiny}
        board_rows=[]
        for item in cp+mp:
            a,b=item['closestPointsMm']
            row={'boardId':d['id'],'feature':item['feature'],'polygonA0':item['polygonIndices0'][0],
                'polygonB0':item['polygonIndices0'][1], 'gapMm':item['gapMm'],
                'pointAxMm':a[0],'pointAyMm':a[1],'pointBxMm':b[0],'pointByMm':b[1],
                'screenThresholdMm':item['screenThresholdMm']}
            csv_rows.append(row)
            board_rows.append(row)
        for feature in ['F.Cu island gap','F.Mask black gap']:
            candidates=[r for r in board_rows if r['feature']==feature]
            if candidates:
                representative_rows.append(min(candidates,key=lambda r:r['gapMm']))
        report['boards'].append(rec)
    report['summary']={'boardsReviewed':len(sources),
        'clearanceAndContainmentPassCount':sum(b['clearanceAndContainmentPass'] for b in report['boards']),
        'maskOnlyPolicyPassCount':sum(b['maskOnlyHasNoDecorativeCopperOrMaskOpenings'] for b in report['boards']),
        'boardsWithCopperGapCandidates':sum(bool(b['copperGapsBelow010Mm']) for b in report['boards']),
        'boardsWithBlackMaskGapCandidates':sum(bool(b['blackMaskGapsBelow013Mm']) for b in report['boards']),
        'copperGapPairCount':sum(len(b['copperGapsBelow010Mm']) for b in report['boards']),
        'blackMaskGapPairCount':sum(len(b['blackMaskGapsBelow013Mm']) for b in report['boards'])}
    report['repositoryRelativeOutputDirectory'] = (
        output_dir.relative_to(HANDOFF).as_posix() if output_dir.is_relative_to(HANDOFF) else 'custom output directory'
    )
    (output_dir/'export-art-review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    fields=['boardId','feature','polygonA0','polygonB0','gapMm','pointAxMm','pointAyMm','pointBxMm','pointByMm','screenThresholdMm']
    csv_path=output_dir/'artwork-gap-review.csv'
    with csv_path.open('w',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    with (output_dir/'artwork-minimum-gap-examples.csv').open('w',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=fields)
        writer.writeheader()
        writer.writerows(representative_rows)
    rows=[]
    for b in report['boards']:
        if b['finish']=='mask-only':
            continue
        cg=b['copperGapsBelow010Mm']
        mg=b['blackMaskGapsBelow013Mm']
        rows.append('| '+b['boardId']+' | '+str(len(cg))+' | '+(f'{cg[0]["gapMm"]:.6f}' if cg else 'N/A')+' | '+str(len(mg))+' | '+(f'{mg[0]["gapMm"]:.6f}' if mg else 'N/A')+' | '+f'{b["goldClippedFraction"]*100:.1f}%'+' |')
    md="""# Exported Copper and Mask Review

This report screens 52 fabrication.json records under the selected vector root. It independently measures exported F.Cu and F.Mask polygons. It is not a KiCad parser, DRC, CAM review, or supplier approval.

## Screened checks

- For all 52 boards, exposed gold is contained by copper and meets the selected edge and hole clearances within a 0.001 mm numeric tolerance. Round-hole clearance uses center distance minus radius; slot clearance uses distance from the centerline minus half-width.
- Mask-only boards have no decorative front or back copper and no gold-opening mask art.
- Gold clipping reports a visible-area change from the selected edge clearances. It is not a quote or price-reduction estimate.

## Narrow gaps for local review

The source screen flags separate copper polygons closer than 0.10 mm and separate mask openings closer than 0.13 mm, using the cited [JLCPCB capability table](https://jlcpcb.com/capabilities/pcb-capabilities). A mask gap is the narrow black solder-mask bridge between exposed-gold regions. A pair count is not a distinct defect count; review its coordinates and actual local shape.

| Board ID | Copper pairs | Minimum copper gap, mm | Black-mask pairs | Minimum mask gap, mm | Gold area clipped |
| --- | ---: | ---: | ---: | ---: | ---: |
""" + '\n'.join(rows) + """

## Review options

Possible edits include joining hidden copper under mask, widening a black facet, or joining neighboring gold. Compare the resulting art before adopting a change. The Kumiko black facets contribute to visual depth and should not be erased in bulk.

The companion CSV files and JSON are written beside this report. artwork-minimum-gap-examples.csv contains representative minima; artwork-gap-review.csv lists the measured pairs. The polygon indexes refer to frontCopper or frontMaskOpenings in each board's fabrication.json. The JSON records true-drill and board-edge clearances, containment, and small-mask-component heuristics. A 0.13 mm heuristic is not a claim about a supplier's minimum gold opening.

## Regenerate into a new local directory

    python3 artwork-resources/pcb-art/validation/review_export_art.py --vectors-root artwork-resources/pcb-art/generated/rev5-export/resources/vector

Shapely 2.1 or later is required. Reports and CSVs are written under artwork-resources/pcb-art/generated/export-art-review by default. The tool does not edit boards or vector geometry.
"""
    (output_dir/'export-art-review.md').write_text(md)
    print(json.dumps(report['summary'],indent=2))


if __name__ == '__main__':
    main()
