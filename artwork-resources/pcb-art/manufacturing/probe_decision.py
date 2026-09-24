#!/usr/bin/env python3
"""Reproduce scoped decision comparisons; never emit production geometry or CAM."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('export_reference', ROOT / 'tools/export_kicad.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(data):
    for family in data['designs']:
        yield family['variants'][0] if family['id'] == 'kumiko-void' else family


def font(size):
    for name in ['/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def draw_geom(draw, geom, bounds, viewport, fill):
    x0, y0, x1, y1 = bounds
    vx, vy, vw, vh = viewport
    scale = min(vw / (x1-x0), vh / (y1-y0))
    def points(ring):
        return [(vx+(x-x0)*scale, vy+(y-y0)*scale) for x, y in ring.coords]
    for p in export.polygons(geom.intersection(box(*bounds))):
        draw.polygon(points(p.exterior), fill=fill)
        for ring in p.interiors:
            draw.polygon(points(ring), fill='#edf0ed')


def comparison_image(examples, path):
    image = Image.new('RGB', (1200, 240 + 350*len(examples)), '#edf0ed')
    draw = ImageDraw.Draw(image)
    draw.text((28, 20), 'Fabrication decision: targeted geometry probes', font=font(27), fill='#152025')
    draw.text((28, 63), 'Left: approved Rev5. Right: local process adaptation. Gold is flat artwork.', font=font(19), fill='#152025')
    draw.text((28, 94), 'Decision evidence only. Final geometry, width checks, native DRC and CAM belong to #15 / #16.', font=font(17), fill='#704527')
    for n, example in enumerate(examples):
        title, before, after, old_gold, new_gold, bounds, caption = example
        y = 150 + n*350
        draw.text((28, y), title, font=font(20), fill='#152025')
        for x, body, gold in [(35, before, old_gold), (635, after, new_gold)]:
            viewport=(x, y+35, 530, 260)
            draw_geom(draw, body, bounds, viewport, '#202429')
            # Rendering a polygon's holes as background is correct for the body;
            # gold holes must show the underlying black material.
            cut = gold.intersection(box(*bounds))
            x0,y0,x1,y1=bounds; s=min(530/(x1-x0),260/(y1-y0))
            for p in export.polygons(cut):
                pts=lambda r:[(x+(xx-x0)*s,y+35+(yy-y0)*s) for xx,yy in r.coords]
                draw.polygon(pts(p.exterior),fill='#d7ad51')
                for ring in p.interiors:
                    draw.polygon(pts(ring),fill='#202429')
            # Gold polygons may enclose board cutouts: restore true voids last.
            draw_geom(draw, box(*bounds).difference(body), bounds, viewport, '#edf0ed')
        draw.text((28,y+306),caption,font=font(16),fill='#31414a')
    image.save(path)


def run():
    policy = json.loads((HERE/'policy.json').read_text())
    for file, digest in policy['sourceHashes'].items():
        assert sha(ROOT/file) == digest, f'Immutable source changed: {file}'
    data = json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
    report = {'decisionId':policy['decisionId'], 'sourceHashes':policy['sourceHashes'],
              'policySha256':sha(HERE/'policy.json'),'probeScriptSha256':sha(Path(__file__)),
              'shapelyVersion':shapely.__version__, 'geosVersion':shapely.geos_version_string,
              'scope':'Decision probes only, not final manufacturing geometry, minimum-width proof or CAM.',
              'boards':[], 'comparisons':[], 'knownClosures':[], 'passed':False}
    examples=[]
    border_examples=[]
    for design in selected(data):
        previous_apertures=None
        for layer in design['layers']:
            key=f'{design["id"]}-L{layer["index"]+1:02d}'
            drills=export.drill_specs(layer,data['spec'])
            before=Polygon(layer['outer'],layer['holes'])
            cutouts=export.split_functional_holes(layer,drills)
            new_holes=[]; changes=[]
            for index, ring in enumerate(layer['holes']):
                original=Polygon(ring)
                if any(original.covers(Point(d['x'],d['y'])) for d in drills):
                    continue
                actions=[a for a in policy['selectedApertureActions']
                         if design['id']=='kumiko-void' and a['layerNumber']==layer['index']+1 and a['geometryHoleIndex0']==index]
                center=original.buffer(-.5,quad_segs=64)
                if actions:
                    assert center.is_empty, actions[0]['issueId']
                    report['knownClosures'].append(actions[0]['issueId'])
                    after_hole=Polygon()
                else:
                    assert not center.is_empty, f'Unindexed closure: {key} hole {index}'
                    after_hole=center.buffer(.5,quad_segs=64).intersection(original)
                    new_holes.append(after_hole)
                delta=original.symmetric_difference(after_hole)
                if delta.area>1e-5:
                    changes.append({'geometryHoleIndex0':index,'boundsMm':[round(v,4) for v in original.bounds],
                                    'deltaAreaMm2':round(delta.area,6),'closed':bool(actions),
                                    'centerComponents':len(export.polygons(center))})
            apertures=unary_union(new_holes)
            substrate=Polygon(layer['outer']).difference(apertures)
            # Use true circles for the support assertion, not serialized drill polygons.
            assert all(substrate.buffer(.0001).covers(Point(x,y).buffer(3.05,quad_segs=128)) for x,y in data['spec']['screws']), key
            functional=unary_union([export.drill_shape(d) for d in drills])
            after=substrate.difference(functional)
            assert after.is_valid and after.geom_type=='Polygon',key
            assert len(export.polygons(after.buffer(-.5)))==1,key
            assert all(substrate.covers(box(0,yy,101.3,yy+1)) for yy in ([0,127.5] if layer['index']==0 else [17.1,110.4])),key
            if layer['index']==0:
                assert apertures.difference(box(0,17.1,101.3,111.4)).area<1e-5,key
            if layer['solid']:
                assert apertures.is_empty,key
            if previous_apertures is not None and design['id'] in ('coral-vault','fault-line'):
                assert apertures.difference(previous_apertures.buffer(.001)).area<1e-5,key
            previous_apertures=apertures
            total_original=unary_union(cutouts)
            loss=total_original.area-apertures.area
            fraction=loss/total_original.area if total_original.area else 0
            assert fraction <= (.035 if key=='kumiko-void-L01' else .02),key
            boundary_parts=[Polygon(r) for r in after.interiors]
            minimum=min([p.distance(after.exterior) for p in boundary_parts]+[a.distance(b) for a,b in itertools.combinations(boundary_parts,2)])
            assert minimum>=.999,key
            record={'board':key,'layerNumber':layer['index']+1,'decorativeAreaBeforeMm2':round(total_original.area,6),
                    'decorativeAreaAfterMm2':round(apertures.area,6),'removedApertureAreaFraction':round(fraction,8),
                    'minimumDistinctBoundaryMaterialMm':round(minimum,6),
                    'supportDisksBridgesFloorBackingConnectivity':True,'changes':changes}
            report['boards'].append(record)
            if layer['index']==0:
                old_gold=export.paint_gold(layer,design,before)
                manufacturing_layer=copy.deepcopy(layer)
                if design['id']=='coral-vault':
                    for stroke in manufacturing_layer['art']['strokes']:
                        if stroke.get('purpose')=='top-gold-border' and stroke.get('feature')=='stack-hole' and stroke['featureIndex'] in (1,2,3):
                            cx,cy=data['spec']['screws'][stroke['featureIndex']]
                            stroke['pts']=[[cx+(x-cx)*2.55/2.70,cy+(y-cy)*2.55/2.70] for x,y in stroke['pts']]
                new_gold=export.paint_gold(manufacturing_layer,design,before).intersection(after.buffer(-.35,quad_segs=64))
                # Compare all complete tops, including the unchanged nine border paths.
                examples.append((design['name']+' / complete top and nine gold borders',before,after,old_gold,new_gold,(0,0,101.3,128.5),
                    f'{key}: routing loss {fraction:.3%}; gold shown with 0.35 mm edge/drill clearance.'))
                border_examples.append((design['name']+' / upper frame, rail rims and stack rims',before,after,old_gold,new_gold,(0,0,101.3,30),
                    'Nine closed rims retain a 0.25 mm core. Coral stack rims 1/2/3 move inward 0.15 mm.'))
                rims=[export.stroke_geometry(s,design.get('artStyle')=='angular') for s in manufacturing_layer['art']['strokes'] if s.get('purpose')=='top-gold-border']
                border_loss=[r.difference(new_gold).area for r in rims]
                rim_strokes=[s for s in manufacturing_layer['art']['strokes'] if s.get('purpose')=='top-gold-border']
                for stroke,rim in zip(rim_strokes,rims):
                    core=export.stroke_geometry(dict(stroke,w=.25),design.get('artStyle')=='angular')
                    assert core.difference(new_gold).area<.00001,(key,stroke['feature'],core.difference(new_gold).area)
                    clipped=rim.intersection(after.buffer(-.35,quad_segs=64))
                    assert clipped.geom_type=='Polygon' and len(clipped.interiors)==1,(key,stroke['feature'])
                report['comparisons'].append({'board':key,'kind':'complete top, corner adaptation and edge-cleared gold',
                    'maximumOriginalBorderClippedAreaMm2':round(max(border_loss),9),
                    'nineClosedBorderCores025MmPreserved':True,
                    'goldBeforeMm2':round(old_gold.area,6),'goldAfterEdgeClearanceMm2':round(new_gold.area,6),
                    'topBorderSourceCount':sum(s.get('purpose')=='top-gold-border' for s in layer['art']['strokes'])})
                if design['id']=='kumiko-void':
                    examples.append(('Kumiko wide / H11 closure and THIN-68-101',before,after,old_gold,new_gold,(90,23,97,29),
                        'Close H11 (0.065381 mm2). Preserve the adjacent planar gold/black facet.'))
                    # A concrete local mask-web widening, without merging black shadow into gold.
                    audit=json.loads((ROOT/'validation/export-art-review.json').read_text())
                    item=next(b for b in audit['boards'] if b['designId']=='kumiko-void' and b['variant']=='wide' and b['layerNumber']==1)
                    gap=min(item['blackMaskGapsBelow013Mm'],key=lambda g:g['gapMm']) if 'blackMaskGapsBelow013Mm' in item else None
                    if gap:
                        a,b=gap['closestPointsMm']; mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2)
                        # Local retreat only: preserve every preexisting black point.
                        revised=new_gold.difference(LineString([a,b]).buffer(.125,quad_segs=64))
                        bounds=(mid.x-1.3,mid.y-1.3,mid.x+1.3,mid.y+1.3)
                        examples.append(('Kumiko wide / indexed black facet mask-web probe',before,after,new_gold,revised,bounds,
                            'Local opening retreat; black facet retained. Full 0.25 mm width/spacing pass remains #15.'))
                        report['comparisons'].append({'board':key,'kind':'mask-web local retreat probe','sourceExportSha256':item['sourceSha256'],
                            'polygonIndices0':gap['polygonIndices0'],'closestPointsMm':gap['closestPointsMm'],'beforeGapMm':gap['gapMm'],
                            'probeOnly':True})
    assert len(report['knownClosures'])==56
    assert len(report['boards'])==43
    report['passed']=True
    (HERE/'decision-probe.json').write_text(json.dumps(report,indent=2)+'\n')
    comparison_image(examples,HERE/'decision-comparisons.png')
    comparison_image(border_examples,HERE/'top-border-comparisons.png')
    print(json.dumps({'passed':True,'boards':43,'indexedClosures':56,'comparisons':len(examples),
                      'largestApertureLossFraction':max(b['removedApertureAreaFraction'] for b in report['boards'])}))


if __name__=='__main__':
    run()
