#!/usr/bin/env python3
"""Render the captured Spider permission evidence; no manufacturing acceptance."""
from pathlib import Path
import json,shapely
from shapely.geometry import box
from shapely.ops import unary_union
from PIL import Image,ImageDraw,ImageFont
p=Path(__file__).resolve().parent;e=json.loads((p/'spider-channel-erratum.json').read_text());m=shapely.from_wkb(bytes.fromhex(e['preMergeMaskWkbHex']));body=shapely.from_wkb(bytes.fromhex(e['candidateBodyWkbHex']));patches=[shapely.from_wkb(bytes.fromhex(x['wkbHex'])) for x in e['implementationExample']['patches']];merged=m.union(unary_union(patches))
def font(n):
 for name in ['/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
  if Path(name).is_file():return ImageFont.truetype(name,n)
 return ImageFont.load_default(size=n)
im=Image.new('RGB',(1200,2130),'#edf0ed');draw=ImageDraw.Draw(im)
def polys(g):
 if g.is_empty:return []
 if g.geom_type=='Polygon':return [g]
 return [p for child in getattr(g,'geoms',[]) for p in polys(child)]
def render(art,bounds,x,y,w,h):
 x0,y0,x1,y1=bounds;scale=min(w/(x1-x0),h/(y1-y0))
 def paint(g,color,holecolor):
  def pts(r):return [(x+(xx-x0)*scale,y+(yy-y0)*scale) for xx,yy in r.coords]
  for shape in polys(g.intersection(box(*bounds))):
   draw.polygon(pts(shape.exterior),fill=color)
   for r in shape.interiors:draw.polygon(pts(r),fill=holecolor)
 paint(body,'#202429','#edf0ed');paint(art,'#d7ad51','#202429');paint(box(*bounds).difference(body),'#edf0ed','#edf0ed')
draw.text((25,18),'Spider L01: bounded channel-merge evidence',font=font(28),fill='#152025')
draw.text((25,61),'Before / proposed addition: 4 patches, 29.892211 mm2 total. Existing gold is retained.',font=font(18),fill='#152025')
draw.text((25,91),'Decision scope only. Final positive/negative width, trapped-pocket, native and CAM gates remain pending.',font=font(17),fill='#704527')
render(m,(0,0,101.3,128.5),100,140,410,450);render(merged,(0,0,101.3,128.5),700,140,410,450)
for n,pair in enumerate(e['pairs']):
 selected=[shapely.from_wkb(bytes.fromhex(x['wkbHex'])) for x in e['implementationExample']['patches'] if x['channelId']==pair['id']];bounds=unary_union(selected).bounds;bounds=(bounds[0]-1,bounds[1]-1,bounds[2]+1,bounds[3]+1);y=660+n*470
 draw.text((25,y),pair['id']+' / strokes '+str(pair['sourceStrokeIndices0']),font=font(20),fill='#152025')
 render(m,bounds,25,y+38,540,380);render(merged,bounds,635,y+38,540,380)
 draw.text((25,y+426),'Original narrow channels at left; same guide strands joined to the web at right.',font=font(17),fill='#31414a')
im.save(p/'spider-channel-erratum.png')
