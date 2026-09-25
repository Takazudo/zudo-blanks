#!/usr/bin/env python3
"""Inspect an external native checkpoint; never mutate manufacturing candidates."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('process_export', ROOT/'tools/export_kicad.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)
SOURCE_SHA = '00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e'
POURS = {'01-spider-nest-L03-gold-enig-fill', '01-spider-nest-L05-gold-enig-fill',
         '01-spider-nest-L07-gold-enig-fill', '03-coral-vault-L04-gold-enig-fill'}
# Fixed, measured local cross sections, not nearest-core midpoints interpreted
# as physical neck locations. Kumiko locations use the critical-radius cores.
WITNESSES = [
    ('coral-vault','ink',.13,(94.81089471887478,121.35257751122303),(.5244363076564288,-.8514496809628221)),
    ('coral-vault','copper-gap',.10,(61.71058399892604,125.06478598198142),(-.07248978304173623,-.9973691550045861)),
    ('coral-vault','visible-gold',.25,(16.7323464197987,42.812091748774066),(.2693798750698178,-.9630339988325278)),
    ('fault-line','copper-gap',.10,(89.98314777673505,123.250001),(0.,1.)),
    ('kumiko-void','ink',.13,(2.3889627479120437,51.15635033664704),(0.,-1.)),
    ('kumiko-void','copper-gap',.10,(2.3654152612283053,51.78076846830183),(-.4999888348166309,-.8660318499100986)),
]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def normsha(g):
    return digest(shapely.normalize(g).wkb)


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def selected(family):
    return next(d for d in family['variants'] if d.get('variantId')=='wide') if family['id']=='kumiko-void' else family


def board_id(design,layer):
    variant=('-'+design['variantId']) if design.get('variantId') else ''
    return (f'{int(design["number"]):02d}-{design["id"]}{variant}-'
            f'L{layer["index"]+1:02d}-{layer["colorKey"]}-{layer["finish"]}')


def body_for(layer,spec):
    drills = export.drill_specs(layer,spec)
    return Polygon(layer['outer']).difference(unary_union(export.split_functional_holes(layer,drills))).difference(unary_union([export.drill_shape(d) for d in drills]))


def component_class(board,poly,body,source_layer):
    if board in POURS:
        assert source_layer['finish']=='enig-fill'
        # Physical apertures do not turn a broad pour into an etched hatch.
        assert not any(Polygon(r).difference(body).area < 1e-5 for r in poly.interiors)
        return 'general-solid-pour'
    if not poly.interiors and poly.convex_hull.difference(poly).area <= 1e-5:
        return 'general-isolated-convex-island'
    return 'retained-special-or-unresolved-network'


def copper_width_mm(record):
    return .10 if record['class'].startswith('general-') else .25


def copper_spacing_mm(a,b=None,*,same_connected_return=False):
    # A missing net label never exempts a physically connected return/slit.
    if same_connected_return or b is None:
        return .25
    return max(copper_width_mm(a),copper_width_mm(b))


def core_summary(region,width):
    extras = []
    affected = 0
    no_disk = []
    for poly in export.polygons(region):
        cores = sorted(export.polygons(poly.buffer(-width/2+1e-6,quad_segs=64)),key=lambda p:-p.area)
        if not cores:
            no_disk.append(poly)
        extras.extend(p.area for p in cores[1:])
        if sum(p.area>1e-5 for p in cores)>1:
            affected += 1
    return {'widthMm':width,'rawExtraCores':len(extras),'secondaryCoresAbove1e5Mm2':sum(a>1e-5 for a in extras),
            'maximumSecondaryCoreAreaMm2':max(extras,default=0),'affectedInputRegions':affected,
            'noDiskRegionCount':len(no_disk),'noDiskAreaMm2':sum(p.area for p in no_disk),
            'meaning':'diagnostic counts, not complete width proof or automatic numerical-fragment waiver'}


def measure(native_dir):
    source_raw = (ROOT/'preview-source/assets/geometry.json').read_bytes()
    assert digest(source_raw)==SOURCE_SHA
    source = json.loads(source_raw)
    names = ['manufacturing-geometry.json','mask-repair-candidate.json','copper-repair-candidate.json']
    raw = {name:(native_dir/name).read_bytes() for name in names}
    data,masks,coppers = [json.loads(raw[name]) for name in names]
    assert masks['sourceGeometrySha256']==digest(raw[names[0]])
    assert coppers['sourceGeometrySha256']==digest(raw[names[0]])
    assert coppers['maskCandidateSha256']==digest(raw[names[1]])
    mask_by = {b['boardId']:b for b in masks['boards']}
    copper_by = {b['boardId']:b for b in coppers['boards']}
    boards, witnesses, pictures = [],[],[]
    for family,original_family in zip(data['designs'],source['designs']):
        design,original = selected(family),selected(original_family)
        for layer,original_layer in zip(design['layers'],original['layers']):
            if layer['finish']=='mask-only':
                continue
            bid = board_id(design,layer)
            body = body_for(layer,data['spec'])
            gold = shapely.from_wkb(bytes.fromhex(mask_by[bid]['afterMaskWkbHex']))
            copper = shapely.from_wkb(bytes.fromhex(copper_by[bid]['afterCopperWkbHex']))
            parts = sorted(export.polygons(copper),key=lambda q:(q.bounds,q.area))
            records = []
            for index,part in enumerate(parts):
                kind = component_class(bid,part,body,original_layer)
                row = {'componentIndex0':index,'featureKey':f"{bid}:F.Cu:{normsha(part)}",'normalizedWkbSha256':normsha(part),
                       'boundsMm':part.bounds,'areaMm2':part.area,'interiorRingCount':len(part.interiors),
                       'convexHullDeficitMm2':part.convex_hull.difference(part).area,'class':kind,
                       'minimumPositiveCopperWidthMm':.10 if kind.startswith('general-') else .25}
                if kind=='general-isolated-convex-island':
                    row['geometryCertificateWkbHex'] = part.wkb_hex
                records.append(row)
            ink = body.difference(gold)
            negative_copper = body.difference(copper)
            boards.append({'boardId':bid,'approvedLayerSha256':digest(encoded(original_layer)),
                           'maskColorHex':layer['mask'],'finish':layer['finish'],
                           'bodyNormalizedWkbSha256':normsha(body),'goldNormalizedWkbSha256':normsha(gold),
                           'copperNormalizedWkbSha256':normsha(copper),'copperFeatures':records,
                           'minimumVisibleGoldWindowWidthMm':.25,
                           'retainedBlackProjectScreenMm':.25 if family['id']=='spider-nest' else .13,
                           'maskProcessCondition':'unchanged submitted mask and required retained ink; local target only, final CAM/process confirmation pending',
                           'diagnostics':{'positiveCopper010':core_summary(copper,.10),
                                          'negativeCopper010':core_summary(negative_copper,.10),
                                          'blackInk013':core_summary(ink,.13)}})
            pictures.append((bid,body,parts,records))
            if layer['index']!=0:
                continue
            for family_id,phase,threshold,center,normal in WITNESSES:
                if family['id']!=family_id:
                    continue
                region = {'ink':ink,'copper-gap':negative_copper,'visible-gold':gold}[phase]
                line = LineString([(center[0]-.5*normal[0],center[1]-.5*normal[1]),(center[0]+.5*normal[0],center[1]+.5*normal[1])])
                intersection = region.intersection(line)
                spans = [q for q in getattr(intersection,'geoms',[intersection]) if q.geom_type=='LineString' and q.distance(Point(center))<1e-5]
                assert len(spans)==1,(bid,phase)
                span = spans[0]
                assert span.length < threshold-1e-6,(bid,phase,span.length)
                crop = region.intersection(box(center[0]-.6,center[1]-.6,center[0]+.6,center[1]+.6))
                witnesses.append({'boardId':bid,'phase':phase,'thresholdMm':threshold,'measuredCrossSectionMm':span.length,
                                  'centerMm':center,'normal':normal,'lineMm':list(line.coords),'spanMm':list(span.coords),
                                  'cropWkbHex':crop.wkb_hex,'cropNormalizedWkbSha256':normsha(crop),
                                  'status':'remaining real local section below screen; not waived by reclassification'})
    report = {'id':'process-classes-2026-09-25','status':'bounded class permissions and diagnostic evidence; no production approval',
              'approvedSourceSha256':SOURCE_SHA,'candidateFileSha256':{name:digest(value) for name,value in raw.items()},
              'indexConvention':'components sorted by exact bounds then area; normalized geometry hash is authoritative identity',
              'classRule':'only named full-gold pours and individually certified convex islands are general; all other geometry retains 0.25',
              'sameConnectedReturnSpacingMm':.25,'unclassifiedCopperWidthAndSpacingMm':.25,
              'boards':boards,'remainingFailureWitnesses':witnesses,
              'probeScriptSha256':digest(Path(__file__).read_bytes()),'exporterSha256':digest((ROOT/'tools/export_kicad.py').read_bytes()),
              'shapelyVersion':shapely.__version__}
    return report,pictures


def render(pictures):
    from PIL import Image,ImageDraw,ImageFont
    image = Image.new('RGB',(1200,1720),'#eef1ee')
    draw = ImageDraw.Draw(image)
    path = '/System/Library/Fonts/Supplemental/Arial.ttf'
    font = ImageFont.truetype(path,15) if Path(path).exists() else ImageFont.load_default(size=15)
    draw.text((20,12),'Copper classification: green = general; amber = retained 0.25 / unresolved; gray = substrate',fill='#192c35',font=font)
    draw.text((20,37),'Actual candidate copper. No mask/gold width waiver; physical cutouts are white. Final manufacturing checks pending.',fill='#192c35',font=font)
    def paint(g,left,top,scale,color):
        def pts(ring):return [(left+x*scale,top+y*scale) for x,y in ring.coords]
        for q in export.polygons(g):
            draw.polygon(pts(q.exterior),fill=color)
            for ring in q.interiors:draw.polygon(pts(ring),fill='#eef1ee')
    for i,(bid,body,parts,records) in enumerate(pictures):
        left,top=20+(i%3)*400,100+(i//3)*400
        draw.text((left,top-25),bid.replace('-black-enig-art','').replace('-gold-enig-fill',''),fill='#192c35',font=font)
        paint(body,left,top,2.6,'#c6cecf')
        for q,r in zip(parts,records):
            paint(q,left,top,2.6,'#257c61' if r['class'].startswith('general-') else '#c19536')
    image.save(HERE/'process-class-comparison.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir',type=Path,required=True,help='external manufacturing directory, read only')
    parser.add_argument('--verify',action='store_true',help='compare with committed decision; write nothing')
    args=parser.parse_args()
    report,pictures=measure(args.native_dir)
    target=HERE/'process-class-decision.json'
    if args.verify:
        assert json.loads(json.dumps(report))==json.loads(target.read_text())
    else:
        target.write_text(json.dumps(report,indent=2)+'\n')
        render(pictures)
    print(json.dumps({'boards':len(report['boards']),'generalCopperFeatures':sum(r['class'].startswith('general-') for b in report['boards'] for r in b['copperFeatures']),
                      'remainingFailureWitnesses':len(report['remainingFailureWitnesses'])}))
