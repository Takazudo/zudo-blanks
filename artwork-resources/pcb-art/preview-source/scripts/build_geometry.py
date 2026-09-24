#!/usr/bin/env python3
"""Build and validate real planar geometry used by the HTML preview.

This generates shapes and material art, not Gerbers or fabrication clearance approval.
"""
import json, math, sys
from pathlib import Path
from importlib import import_module
from shapely.geometry import Point, LineString, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from build_common import W,H,T,GAP,KEEP_OUT,SCREWS,SLOTS,SLOT_DRILL,plate,stroke,ensure_polygon
from finish_policy import apply_finish, summary as finish_summary

IDS=['spider_nest','coral_vault','fault_line','kumiko_void','woven_maze']
EXPECTED={
 'spider-nest':['black','white','gold','white','gold','white','gold','red'],
 'coral-vault':['black','green','purple','gold','red','yellow','red','blue'],
 'fault-line':['black','red','black','red','black','red','black','red','black'],
 'kumiko-void':['black','red','green','black','red','green','black','red','green'],
 'woven-maze':['black','white','black','white','black','white','black','white','black'],
}

def coords(ring):
    points=list(ring.coords)
    if points and points[0]==points[-1]: points=points[:-1]
    return [[round(x,4),round(y,4)] for x,y in points]

def drill_geometry(i):
    holes=[Point(x,y).buffer(1.6,quad_segs=16) for x,y in SCREWS]
    if i==0:
        hl=(SLOT_DRILL[0]-SLOT_DRILL[1])/2
        holes += [LineString([(x-hl,y),(x+hl,y)]).buffer(1.6,quad_segs=16) for x,y in SLOTS]
    return unary_union(holes)

def rounded_art(art):
    for kind in ['strokes','fills']:
        for a in art.get(kind,[]):
            a['pts']=[[round(float(x),4),round(float(y),4)] for x,y in a['pts']]
            if 'w' in a: a['w']=round(float(a['w']),4)
    return art


def border_footprint(item, angular):
    """The same stroke extent used by the preview, expressed as planar copper."""
    points=item['pts']
    if item.get('closed') and points[0]!=points[-1]:
        points=points+[points[0]]
    return LineString(points).buffer(item['w']/2,
        cap_style=2 if angular else 1,join_style=2 if angular else 1)


def top_gold_borders(did, drilled, art_style=None):
    """Flat front copper/mask artwork; never changes drills or Edge.Cuts.

    Stack-hole octagons fit inside the common radius-3.05 mounting islands.
    Larger square corners would leave those islands on the expanded designs.
    Rail-slot rims deliberately meet the perimeter line: the previous smaller
    rims left unmanufacturable-looking 0.02-0.04 mm mask slivers between them.
    These cosmetic rings do not imply plated holes or plated board edges.
    """
    angular=did in ('spider-nest','kumiko-void')
    borders=[]

    def add(points, width, feature, index=None):
        item=stroke(points,width,closed=True)
        item.update(purpose='top-gold-border',feature=feature)
        if index is not None: item['featureIndex']=index
        borders.append(item)

    inset=plate(0).buffer(-.55,join_style=2)
    add(list(inset.exterior.coords),.32,'perimeter')
    for index,(x,y) in enumerate(SCREWS):
        count=8 if angular else 64
        # A vertex-up octagon has straight diagonal and orthogonal facets.
        pts=[(x+2.70*math.cos(j*math.tau/count),
              y+2.70*math.sin(j*math.tau/count)) for j in range(count)]
        add(pts,.40,'stack-hole',index)
    hl=(SLOT_DRILL[0]-SLOT_DRILL[1])/2
    for index,(x,y) in enumerate(SLOTS):
        ring=(box(x-hl-2.10,y-2.10,x+hl+2.10,y+2.10).exterior if angular else
              LineString([(x-hl,y),(x+hl,y)]).buffer(2.10,quad_segs=16).exterior)
        add(list(ring.coords),.40,'rail-slot',index)

    rounded_art({'strokes':borders,'fills':[]})
    footprints=[border_footprint(item,art_style=='angular') for item in borders]
    for item,shape in zip(borders,footprints):
        if shape.difference(drilled).area>1e-7:
            raise ValueError(f'{did}: {item["feature"]} border leaves its PCB material')
    holes=drill_geometry(0)
    group=lambda role: unary_union([p for item,p in zip(borders,footprints) if item['feature']==role])
    stack=group('stack-hole')
    slots=group('rail-slot')
    perimeter=group('perimeter')
    if any(not p.intersects(perimeter) for item,p in zip(borders,footprints)
           if item['feature']=='rail-slot'):
        raise ValueError(f'{did}: rail-slot rim must meet the outside gold frame')
    measure=lambda value: round(value,4)
    metadata={
        'revision':5,'flatArtwork':True,'topOnly':True,'closedStrokeCount':9,
        'perimeter':{'centerlineInsetMm':.55,'strokeWidthMm':.32,
                     'minimumBoardEdgeClearanceMm':measure(perimeter.distance(plate(0).boundary))},
        'stackHoles':{'count':4,'outline':'octagonal' if angular else 'circular',
                     'centerlineRadiusMm':2.70,'strokeWidthMm':.40,
                     'supportRadiusMm':3.05,
                     'minimumDrillClearanceMm':measure(stack.distance(holes)),
                     'minimumBoardBoundaryClearanceMm':measure(stack.distance(drilled.boundary))},
        'railSlots':{'count':4,'outline':'rectangular' if angular else 'capsule',
                     'centerlineOffsetFromSlotAxisMm':2.10,'strokeWidthMm':.40,
                     'minimumDrillClearanceMm':measure(slots.distance(holes)),
                     'joinedToPerimeter':True},
        'allCopperInsideBoard':True,'drillsUnchanged':True,
        'platedHolesRequired':False,'edgePlatingRequired':False,
    }
    return borders,metadata


def manufacture_layer(layer, did, full_face=False, art_style=None):
    i=layer['index']
    raw=ensure_polygon(layer.pop('body'),f'{did}/{i}')
    expected_plate=plate(i)
    if raw.difference(expected_plate).area>1e-5:
        raise ValueError(f'{did}/{i}: geometry outside panel envelope')
    if raw.symmetric_difference(expected_plate).area<1e-5 and not layer['solid']:
        raise ValueError(f'{did}/{i}: aperture sheet is unexpectedly solid')
    if not raw.covers(unary_union([Point(x,y).buffer(3.05) for x,y in SCREWS])):
        raise ValueError(f'{did}/{i}: a screw support lacks its full mounting island')
    # End bridges must be part of THIS layer, independent of every other layer.
    y0=0 if i==0 else KEEP_OUT
    y1=H if i==0 else H-KEEP_OUT
    bridge_top=box(1,y0+.5,W-1,y0+1.0)
    bridge_bottom=box(1,y1-1.0,W-1,y1-.5)
    if not raw.covers(bridge_top) or not raw.covers(bridge_bottom):
        raise ValueError(f'{did}/{i}: exterior top/bottom bridge disconnected')
    drilled=ensure_polygon(raw.difference(drill_geometry(i)),f'{did}/{i} after drills')
    drilled=orient(drilled,sign=1.0)
    erosion=drilled.buffer(-.5,quad_segs=6)
    erosion_parts=list(erosion.geoms) if hasattr(erosion,'geoms') else [erosion]
    significant=[p for p in erosion_parts if p.area>.02]
    erosion_ok=len(significant)==1 and not erosion.is_empty
    # Record exact boundary data; no raster-to-mesh approximation is used.
    layer['outer']=coords(drilled.exterior)
    # Boolean intersections may leave sub-resolution rings. At 0.0001 mm
    # serialization they can collapse to repeated points; these have no area
    # and must not be passed to triangulation as real apertures.
    hole_rings=[coords(r) for r in drilled.interiors]
    layer['holes']=[ring for ring in hole_rings
                    if len(set(map(tuple,ring)))>=3 and Polygon(ring).area>0]
    layer['surface']=layer.get('surface','mask')
    apply_finish(layer,did)
    art=layer.setdefault('art',{'strokes':[],'fills':[]})
    # Every top PCB is already ENIG. Shared gold borders now also surround the
    # full-face Spider, Coral and Kumiko graphics. No lower-board finish changes.
    if i==0:
        borders,metadata=top_gold_borders(did,drilled,art_style=art_style)
        art['strokes'].extend(borders)
        layer['goldBorders']=metadata
    if layer['finish']=='mask-only' and (art['strokes'] or art['fills'] or layer['surface']=='gold'):
        raise ValueError(f'{did}/{i}: a plain PCB unexpectedly contains exposed copper art')
    layer['art']=rounded_art(art)
    apertures=unary_union([Polygon(r) for r in raw.interiors])
    aperture_count=len(raw.interiors)
    if i==0 and apertures.difference(plate(1)).area>.001:
        raise ValueError(f'{did}/{i}: decorative apertures extend beyond the lower-board backing')
    layer['stats']={
      'areaMm2':round(drilled.area,3),'volumeMm3':round(drilled.area*T,3),
      'components':1,'apertures':aperture_count,'closedOutline':True,'valid':True,
      'neckTestMm':1.0,'erosionConnected':erosion_ok,'erosionComponents':len(significant),
      'topBottomConnected':True,'mountSupports':True,
      'apertureAreaMm2':round(sum(Polygon(r).area for r in raw.interiors),3),
      'apertureBoundsMm':[round(v,3) for v in apertures.bounds] if not apertures.is_empty else None,
      'exposedCopperArt':layer['finish']!='mask-only',
    }
    return layer

def pattern_coverage(design):
    """Check actual copper graphics reach every region of the remaining face."""
    layer=design['layers'][0]
    body=Polygon(layer['outer'],layer['holes'])
    art=layer['art']
    pieces=[Polygon(f['pts']) for f in art['fills'] if not f.get('color')]
    angular=design.get('artStyle')=='angular'
    pieces += [LineString(s['pts']+([s['pts'][0]] if s.get('closed') else [])).buffer(
        s['w']/2,cap_style=2 if angular else 1,join_style=2 if angular else 1)
        for s in art['strokes'] if not s.get('color') and len(s['pts'])>1]
    copper=unary_union(pieces).intersection(body)
    regions={
      'top':box(0,0,W,27), 'bottom':box(0,H-27,W,H),
      'left':box(0,27,10.5,H-27), 'right':box(W-10.5,27,W,H-27),
      'center':box(10.5,27,W-10.5,H-27),
    }
    areas={key:round(copper.intersection(region).area,4) for key,region in regions.items()}
    covered=all(area>.05 for area in areas.values())
    if not covered: raise ValueError(f'{design["id"]}: all-over artwork misses a face region: {areas}')
    return {'allRegions':True,'regionsMm2':areas,'coverage':'full-face'}

def decorative_apertures(layer):
    centers=[Point(*xy) for xy in SCREWS+SLOTS]
    return unary_union([Polygon(ring) for ring in layer['holes']
                        if not any(Polygon(ring).covers(p) for p in centers)])


def process_design(d, reference, variant=False):
    if [l['colorKey'] for l in d['layers']] != EXPECTED[d['id']]:
        raise ValueError(f'{d["id"]}: incorrect color order')
    n=len(d['layers'])
    if not d['layers'][-1]['solid']:
        raise ValueError(f'{d["id"]}: missing solid floor')
    if any(l['solid'] for l in d['layers'][:-1]):
        raise ValueError(f'{d["id"]}: opaque sheet before floor')
    full_face=d['id'] in ('spider-nest','coral-vault','kumiko-void')
    d['layers']=[manufacture_layer(l,d['id'],full_face=full_face,art_style=d.get('artStyle')) for l in d['layers']]
    d['revision']=5
    d['topGoldBorders']=d['layers'][0]['goldBorders']
    if full_face: d['patternCoverage']=pattern_coverage(d)
    d['finishSummary']=finish_summary(d['id'],n)
    d['stackDepth']=round(n*T+(n-1)*GAP,1)
    d['totalAreaMm2']=round(sum(l['stats']['areaMm2'] for l in d['layers']),2)
    erode=all(l['stats']['erosionConnected'] for l in d['layers'])
    d['checks']=[
      {'label':'各層が1枚のPCBとして接続','ok':True,'detail':f'{n}/{n} 層、穴を差し引いた後も単一の連結形状'},
      {'label':'上辺・下辺の連続性','ok':True,'detail':'全層で上下の外周がつながっています'},
      {'label':'実寸とレールの逃げ','ok':True,'detail':'前面 101.3 ×128.5 mm／下層 101.3 ×94.3 mm'},
      {'label':'固定穴と支持部','ok':True,'detail':'4軸共通、穴径3.2 mm／支持部径6.1 mm以上'},
      {'label':'トップ外周と固定穴の金縁','ok':True,'detail':'外周1本・積層穴4個・レール長穴4個、板面内の平面ENIG装飾'},
      {'label':'指定した層順','ok':True,'detail':'マスク色・全面ENIG・底板の順番を確認'},
      {'label':'層ごとのENIG使用方針','ok':True,'detail':f'ENIG {d["finishSummary"]["enigCount"]}枚／露出銅箔なし {d["finishSummary"]["maskOnlyCount"]}枚'},
      {'label':'細い接続部の形状チェック','ok':erode,'detail':'0.5 mm内側へオフセットした形状の接続性（製造DRCの代替ではありません）'},
    ]
    if d['id'] in ('fault-line','coral-vault'):
        # A branching rift may split into several apertures at depth. Check
        # their entire union, not only the largest opening in each sheet.
        holes=[decorative_apertures(l) for l in d['layers'][:-1]]
        nested=all(b.difference(a.buffer(.0002)).area<.002 and b.area<a.area for a,b in zip(holes,holes[1:]))
        if not nested: raise ValueError(f'{d["id"]} serialized apertures must stay strictly nested')
        d['checks'].append({'label':'奥へ狭まる開口','ok':True,'detail':'各段の開口は手前の開口の内側にあり、面積が順に減少します'})
    if full_face:
        d['checks'].append({'label':'トップ全面の模様','ok':True,'detail':'上・下・左・右・中央の板面すべてに銅箔模様があります'})
    d.setdefault('sources',[])
    previous=decorative_apertures(reference['layers'][0])
    current=decorative_apertures(d['layers'][0])
    d['comparisonToRevision3']={
        'previousAreaMm2':round(previous.area,3),'currentAreaMm2':round(current.area,3),
        'areaScale':round(current.area/previous.area,4),
        'previousBoundsMm':[round(v,3) for v in previous.bounds],
        'currentBoundsMm':[round(v,3) for v in current.bounds],
    }
    unchanged_standard=d['id']=='kumiko-void' and not variant
    if not unchanged_standard and current.area<=previous.area*1.05:
        raise ValueError(f'{d["id"]}: requested larger opening has not increased meaningfully')
    if not erode: raise ValueError(f'{d["id"]}: a PCB disconnects under the 0.5 mm neck check')
    label=d['id']+('/'+d['variantId'] if d.get('variantId') else '')
    print(f'{label}: {n} connected PCBs, {d["stackDepth"]} mm, opening {current.area/previous.area:.2f}x, erosion PASS',file=sys.stderr)
    return d

def build_all():
    reference=json.loads((ROOT/'assets'/'reference-revision3.json').read_text())
    old={d['id']:d for d in reference['designs']}
    designs=[]
    for module in IDS:
        source=import_module('designs.'+module)
        d=source.build()
        d=process_design(d,old[d['id']])
        if d['id']=='kumiko-void':
            d.update(variantId='standard',variantLabel='標準',defaultVariant='wide')
            wide=process_design(source.build_wide(),old[d['id']],variant=True)
            wide.update(variantId='wide',variantLabel='開口拡大')
            d['variants']=[wide]
        designs.append(d)
    data={'schemaVersion':4,'revision':5,'spec':{
      'width':W,'height':H,'thickness':T,'gap':GAP,'keepout':KEEP_OUT,
      'slots':SLOTS,'slotDrill':SLOT_DRILL,'screws':SCREWS,'screwDiameter':3.2,
      'padDiameter':6,'spacerOD':6,'railTall':12.59,'railDeep':20.13,'railNutFromOuter':6.37,
      'referenceUrl':'https://github.com/Takazudo/zudo-blanks/tree/main/panels/art-strip-mine/preview',
    },'designs':designs}
    (ROOT/'assets').mkdir(exist_ok=True)
    (ROOT/'assets'/'geometry.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    def validation_entry(d):
        item={k:d[k] for k in ['id','number','name','stackDepth','totalAreaMm2','checks','finishSummary','comparisonToRevision3','topGoldBorders']}
        item['layers']=[{k:l[k] for k in ['index','colorKey','surface','finish','finishLabel','solid','stats']} for l in d['layers']]
        if d.get('variantId'): item.update(variantId=d['variantId'],variantLabel=d['variantLabel'])
        if d.get('variants'): item['variants']=[validation_entry(v) for v in d['variants']]
        return item
    summary={'schemaVersion':4,'revision':5,'spec':data['spec'],'designs':[validation_entry(d) for d in designs]}
    (ROOT/'assets'/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return data

if __name__=='__main__': build_all()
