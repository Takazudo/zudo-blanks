#!/usr/bin/env python3
"""Index inherited pairwise art findings against the corrected geometry candidate.

This is a diagnostic inventory. A covered midpoint is not a printable-width
proof, and an open midpoint is not automatically a finished-union violation.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('export_reference',ROOT/'tools/export_kicad.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    data = json.loads((HERE/'manufacturing-geometry.json').read_text())
    review = json.loads((ROOT/'validation/export-art-review.json').read_text())
    records = []
    summary = {}
    for family in data['designs']:
        design = (next(d for d in family['variants'] if d.get('variantId')=='wide')
                  if family['id']=='kumiko-void' else family)
        for layer in design['layers']:
            finding = next(b for b in review['boards'] if b['designId']==design['id']
                           and b['layerNumber']==layer['index']+1
                           and b.get('variant')==design.get('variantId'))
            if layer['finish']=='mask-only':
                assert not finding['copperGapsBelow010Mm'] and not finding['blackMaskGapsBelow013Mm']
                continue
            drills=export.drill_specs(layer,data['spec'])
            cutouts=export.split_functional_holes(layer,drills)
            body=Polygon(layer['outer']).difference(unary_union(cutouts)).difference(
                unary_union([export.drill_shape(d) for d in drills]))
            gold=export.paint_gold(layer,design,body)
            mask=gold.intersection(body.buffer(-.35,quad_segs=64))
            copper=mask.buffer(.05,quad_segs=64).intersection(body.buffer(-.30,quad_segs=64))
            for key,feature,union in [('copperGapsBelow010Mm','F.Cu island gap',copper),
                                      ('blackMaskGapsBelow013Mm','F.Mask black gap',mask)]:
                for issue in finding[key]:
                    a,b=issue['closestPointsMm']
                    mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2)
                    records.append({
                        'key':f'art:{finding["sourceSha256"]}:{finding["boardId"]}:{feature}:{issue["polygonIndices0"][0]}:{issue["polygonIndices0"][1]}',
                        'boardId':finding['boardId'],
                        'sourceExportSha256':finding['sourceSha256'],
                        'feature':feature,
                        'polygonIndices0':issue['polygonIndices0'],
                        'originalClosestPointsMm':issue['closestPointsMm'],
                        'originalGapMm':issue['gapMm'],
                        'candidateMidpointCoveredByUnion':union.covers(mid),
                        'disposition':'unresolved; finished union width/gap proof required',
                    })
            summary[finding['boardId']] = {
                'originalCopperPairFindings':len(finding['copperGapsBelow010Mm']),
                'originalMaskPairFindings':len(finding['blackMaskGapsBelow013Mm']),
                'candidateGoldAreaMm2':round(mask.area,6),
                'candidateCopperAreaMm2':round(copper.area,6),
            }
    report={
        'status':'diagnostic only; all original selected art findings remain unresolved',
        'geometrySha256':sha(HERE/'manufacturing-geometry.json'),
        'sourceReviewSha256':sha(ROOT/'validation/export-art-review.json'),
        'summary':summary,
        'findings':records,
    }
    (HERE/'art-candidate-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'selectedOriginalArtFindings':len(records),
                      'coveredMidpoints':sum(r['candidateMidpointCoveredByUnion'] for r in records)}))


if __name__=='__main__':
    run()
