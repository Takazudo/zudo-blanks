#!/usr/bin/env python3
"""Measure only the bounded Spider rib proposal; never emit native production boards."""
import hashlib
import json
import math
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CENTERLINE=[[73.5804,43.9604],[66.0864,48.5094],[56.1526,54.5394]]


def polygons(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for child in getattr(g,'geoms',[]) for p in polygons(child)]


def normsha(g):
    return hashlib.sha256(shapely.normalize(g).wkb).hexdigest()


def measure():
    raw=(HERE/'spider-channel-erratum.json').read_bytes()
    prior=json.loads(raw)
    body=shapely.from_wkb(bytes.fromhex(prior['candidateBodyWkbHex']))
    gold=shapely.from_wkb(bytes.fromhex(prior['preMergeMaskWkbHex']))
    source_raw=(ROOT/'preview-source/assets/geometry.json').read_bytes()
    assert hashlib.sha256(source_raw).hexdigest()==prior['approvedSourceSha256']
    source=json.loads(source_raw)
    top=next(d for d in source['designs'] if d['id']=='spider-nest')['layers'][0]
    assert top['art']['strokes'][7]['pts']==CENTERLINE[:2]
    assert top['art']['strokes'][8]['pts']==CENTERLINE[1:]
    ribbon=LineString(CENTERLINE).buffer(1.0,cap_style='flat',join_style='mitre')
    addition=ribbon.difference(body)
    after=body.union(ribbon)
    assert after.is_valid and after.geom_type=='Polygon'
    assert after.bounds==body.bounds
    assert body.difference(after).area<.00001
    assert len(after.interiors)==len(body.interiors)
    functional=[]
    for x,y in source['spec']['screws']:
        functional.append(Point(x,y).buffer(1.6,quad_segs=128))
    for x,y in source['spec']['slots']:
        functional.append(LineString([(x-3.54,y),(x+3.54,y)]).buffer(1.6,quad_segs=128))
    assert addition.intersection(unary_union(functional)).area<.00001
    before_drills=after.union(unary_union(functional))
    assert all(before_drills.buffer(.000001).covers(Point(x,y).buffer(3.05,quad_segs=128)) for x,y in source['spec']['screws'])
    assert after.covers(box(0,0,101.3,1)) and after.covers(box(0,127.5,101.3,128.5))
    centers=[Point(x,y) for x,y in source['spec']['screws']+source['spec']['slots']]
    source_decor=[(i,Polygon(h)) for i,h in enumerate(top['holes']) if not any(Polygon(h).covers(c) for c in centers)]
    affected=[{'originalGeometryHoleIndex0':i,'originalContourSha256':hashlib.sha256(json.dumps(top['holes'][i],separators=(',',':')).encode()).hexdigest(),'addedMaterialInsideOriginalApertureMm2':addition.intersection(p).area} for i,p in source_decor if addition.intersection(p).area>.00001]
    after_decor=[Polygon(r) for r in after.interiors if not any(Polygon(r).covers(c) for c in centers)]
    assert all(p.difference(box(0,17.1,101.3,111.4)).area<.00001 for p in after_decor)
    original_area=sum(p.area for _,p in source_decor)
    aperture_loss=1-sum(p.area for p in after_decor)/original_area
    assert aperture_loss<=.02
    # Diagnostic sweep coverage only. A plunge/path and production contour proof
    # must still be supplied by issue 15/16 after rebuilding affected apertures.
    sweeps=[]
    for i,p in enumerate(after_decor):
        tool_centers=p.buffer(-.5,quad_segs=64)
        envelope=tool_centers.buffer(.5,quad_segs=64).intersection(p)
        original_index=max(source_decor,key=lambda item:p.intersection(item[1]).area)[0]
        sweeps.append({'candidateDecorativeIndex0':i,'originalGeometryHoleIndex0':original_index,'toolCenterComponents':len(polygons(tool_centers)),'unreachedAreaMm2':p.difference(envelope).area})
    sections=[]
    for index,(a,b) in enumerate(zip(CENTERLINE,CENTERLINE[1:]),7):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);nx,ny=-dy/length,dx/length
        x,y=(a[0]+b[0])/2,(a[1]+b[1])/2
        line=LineString([(x-2*nx,y-2*ny),(x+2*nx,y+2*ny)])
        before_width=body.intersection(line).length
        sections.append({'sourceStrokeIndex0':index,'midpointMm':[x,y],'unitNormal':[nx,ny],
            'beforeMaterialWidthMm':before_width,'beforeAvailableArtworkWidthMm':before_width-.7,
            'beforeGoldWidthsMm':[p.length for p in getattr(gold.intersection(line),'geoms',[gold.intersection(line)])],
            'afterMaterialWidthMm':after.intersection(line).length,
            'requiredArtworkWidthMm':.251+.28+.251+2*.25,
            'requiredArtworkWidthAt013WebMm':.251+.28+.251+2*.13})
    return {'id':'spider-l01-rib-width-2026-09-25','status':'bounded material and cross-section probe only; full routing/artwork/native/CAM gates pending',
        'approvedSourceSha256':prior['approvedSourceSha256'],'baseEvidence':'spider-channel-erratum.json','baseEvidenceSha256':hashlib.sha256(raw).hexdigest(),
        'baseCandidateSha256':prior['evidenceCandidateSha256'],'baseBodyNormalizedWkbSha256':normsha(body),
        'sourceStrokeIndices0':[7,8],'guideStrokeIndices0':[98,101,103],'centerlineMm':CENTERLINE,'ribbonWidthMm':2.0,'capStyle':'flat','joinStyle':'mitre',
        'initialAdditionWkbHex':addition.wkb_hex,'initialAdditionNormalizedWkbSha256':normsha(addition),
        'measuredInitialAdditionAreaMm2':addition.area,'afterBodyNormalizedWkbSha256':normsha(after),
        'affectedOriginalApertures':affected,'sections':sections,'proposedGuideCenterOffsetsMm':[-.5165,.5165],
        'proposedGuideWidthMm':.251,'centralStrokeWidthMm':.28,'nominalBlackChannelWidthMm':.251,'nominalOuterMaskClearanceMm':.358,
        'originalDecorativeAreaMm2':original_area,'incrementalApertureLossFraction':addition.area/original_area,'cumulativeApertureLossFraction':aperture_loss,
        'localChecks':{'connectedAfterDrilling':True,'outerBoundsUnchanged':True,'holeCountUnchanged':True,'supportDisksBeforeDrilling':True,'fullUpperLowerBridges':True,'topAperturesBacked':True,'functionalDrillsUnchanged':True},
        'affectedApertureRoutingCleanupAreaMm2':sum(s['unreachedAreaMm2'] for s in sweeps if s['originalGeometryHoleIndex0'] in [a['originalGeometryHoleIndex0'] for a in affected]),
        'diagnosticToolSweeps':sweeps,'probeScriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'shapelyVersion':shapely.__version__,'geosVersion':shapely.geos_version_string}


def render(report):
    from PIL import Image,ImageDraw,ImageFont
    prior=json.loads((HERE/'spider-channel-erratum.json').read_text())
    body=shapely.from_wkb(bytes.fromhex(prior['candidateBodyWkbHex']))
    added=shapely.from_wkb(bytes.fromhex(report['initialAdditionWkbHex']))
    after=body.union(added)
    im=Image.new('RGB',(1200,1420),'#eef1ee');draw=ImageDraw.Draw(im)
    def font(n):
        for name in ['/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
            if Path(name).exists():return ImageFont.truetype(name,n)
        return ImageFont.load_default(size=n)
    def paint(geom,bounds,x,y,w,h,color):
        x0,y0,x1,y1=bounds;scale=min(w/(x1-x0),h/(y1-y0))
        def points(r):return [(x+(xx-x0)*scale,y+(yy-y0)*scale) for xx,yy in r.coords]
        for p in polygons(geom.intersection(box(*bounds))):
            draw.polygon(points(p.exterior),fill=color)
            for r in p.interiors:draw.polygon(points(r),fill='#eef1ee')
    draw.text((24,18),'Spider L01: bounded rib-width decision',font=font(28),fill='#14212a')
    draw.text((24,61),'Left: current material. Right: 2.0 mm rib; blue marks the 6.074302 mm2 addition.',font=font(18),fill='#14212a')
    draw.text((24,93),'Material proposal only. Guide relocation, routing, complete width and CAM checks remain pending.',font=font(17),fill='#704527')
    for x,g in [(55,body),(655,after)]:paint(g,(0,0,101.3,128.5),x,150,490,520,'#293b47')
    paint(added,(0,0,101.3,128.5),655,150,490,520,'#128dc2')
    draw.text((24,708),'Enlargement: keep the radial path; add material only along the named ribbon.',font=font(20),fill='#14212a')
    crop=(53,41,77,57)
    paint(body,crop,24,760,540,370,'#293b47');paint(after,crop,636,760,540,370,'#293b47');paint(added,crop,636,760,540,370,'#128dc2')
    draw.text((24,1160),'Cross-section budget (nominal mm; planned artwork positions):',font=font(20),fill='#14212a')
    draw.text((24,1200),'Before: 1.661 material - 0.700 clearances = 0.961 available; 1.282 required.',font=font(19),fill='#14212a')
    draw.text((24,1240),'After: 2.000 material; 0.358 + 0.251 gold + 0.251 ink + 0.280 gold',font=font(19),fill='#14212a')
    draw.text((24,1275),'       + 0.251 ink + 0.251 gold + 0.358 = 2.000.',font=font(19),fill='#14212a')
    draw.text((24,1330),'This diagram does not certify the guide transitions or the cutter path.',font=font(17),fill='#704527')
    im.save(HERE/'spider-rib-comparison.png')


if __name__=='__main__':
    report=measure()
    (HERE/'spider-rib-decision.json').write_text(json.dumps(report,indent=2)+'\n')
    render(report)
    print(json.dumps({'addedMaterialMm2':report['measuredInitialAdditionAreaMm2'],
        'affectedOriginalHoleIndices0':[p['originalGeometryHoleIndex0'] for p in report['affectedOriginalApertures']],
        'cumulativeApertureLossFraction':report['cumulativeApertureLossFraction'],
        'routingUnreachedAreaMm2':sum(p['unreachedAreaMm2'] for p in report['diagnosticToolSweeps'])}))
