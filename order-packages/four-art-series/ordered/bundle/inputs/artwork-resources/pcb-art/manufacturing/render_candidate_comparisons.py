#!/usr/bin/env python3
"""Render actual approved and corrected ENIG unions in common coordinates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import shapely
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, box

from repair_mask_candidate import HERE, ROOT, board_id, export, source_body

SCALE=4
BOARD_W=round(101.3*SCALE)
BOARD_H=round(128.5*SCALE)
PAD=20
HEADER=48
ROW_H=BOARD_H+58
GOLD='#c8a754'
DETAILS={
    'spider-nest':[(0,'guide-channels',(55,43,74,56))],
    'coral-vault':[(0,'outer-neck',(0.5,100,4,106)),
                   (0,'middle-neck',(24.5,46.5,27.5,49.5)),
                   (0,'inner-neck',(83.5,60,86,63))],
    'fault-line':[(0,'terminal-cliff',(75,110,79,113))],
    'kumiko-void':[(0,'top-facets',(20,0.5,55,15)),
                   (6,'l07-upper',(89.5,20.5,92.5,27)),
                   (6,'l07-lower',(89.5,102,92.5,109))],
    'woven-maze':[(0,'top-maze',(20,20,80,60))],
}


def selected(data):
    for family in data['designs']:
        yield (next(d for d in family['variants'] if d.get('variantId')=='wide')
               if family['id']=='kumiko-void' else family)


def draw_geometry(draw,geom,color):
    for part in export.ordered(geom):
        draw.polygon([(round(x*SCALE),round(y*SCALE)) for x,y in part.exterior.coords],
                     fill=color)


def board_image(layer,body,gold):
    image=Image.new('RGB',(BOARD_W,BOARD_H),'#ffffff')
    draw=ImageDraw.Draw(image)
    color='#15161a' if layer['colorKey']=='gold' else layer['mask']
    draw_geometry(draw,body,color)
    draw_geometry(draw,gold,GOLD)
    for hole in body.interiors:
        draw.polygon([(round(x*SCALE),round(y*SCALE)) for x,y in hole.coords],
                     fill='#ffffff')
    return image


def detail_image(layer,body,gold,bounds,scale=40):
    x0,y0,x1,y1=bounds
    width=round((x1-x0)*scale)
    height=round((y1-y0)*scale)
    image=Image.new('RGB',(width,height),'#ffffff')
    draw=ImageDraw.Draw(image)
    clip=box(*bounds)
    color='#15161a' if layer['colorKey']=='gold' else layer['mask']
    for geom,fill in ((body,color),(gold,GOLD)):
        for part in export.ordered(geom.intersection(clip)):
            draw.polygon([(round((x-x0)*scale),round((y-y0)*scale))
                          for x,y in part.exterior.coords],fill=fill)
    for hole in body.interiors:
        for part in export.ordered(Polygon(hole).intersection(clip)):
            draw.polygon([(round((x-x0)*scale),round((y-y0)*scale))
                          for x,y in part.exterior.coords],fill='#ffffff')
    return image


def run():
    approved_path=ROOT/'preview-source/assets/geometry.json'
    corrected_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    approved=json.loads(approved_path.read_text())
    corrected=json.loads(corrected_path.read_text())
    masks=json.loads(mask_path.read_text())
    before_hash=hashlib.sha256(approved_path.read_bytes()).hexdigest()
    after_hash=hashlib.sha256(corrected_path.read_bytes()).hexdigest()
    mask_hash=hashlib.sha256(mask_path.read_bytes()).hexdigest()
    by_mask={b['boardId']:b for b in masks['boards']}
    records=[]
    details=[]
    geometry_records=[]
    for original,design in zip(selected(approved),selected(corrected)):
        rows=[]
        geometry_rows=[]
        for old_layer,layer in zip(original['layers'],design['layers']):
            old_body=source_body(old_layer,approved['spec'])
            new_body=source_body(layer,corrected['spec'])
            if layer['finish']=='mask-only':
                old_gold=Polygon();new_gold=Polygon()
            else:
                old_gold=export.paint_gold(old_layer,original,old_body)
                new_gold=shapely.from_wkb(bytes.fromhex(
                    by_mask[board_id(design,layer)]['afterMaskWkbHex']))
            small_size=(BOARD_W//2,BOARD_H//2)
            geometry_rows.append((layer,
                board_image(old_layer,old_body,old_gold).resize(small_size),
                board_image(layer,new_body,new_gold).resize(small_size)))
            if layer['finish']=='mask-only':
                continue
            rows.append((layer,board_image(old_layer,old_body,old_gold),
                         board_image(layer,new_body,new_gold),old_gold,new_gold))
            for target_layer,slug,bounds in DETAILS[design['id']]:
                if target_layer!=layer['index']:
                    continue
                before=detail_image(old_layer,old_body,old_gold,bounds)
                after=detail_image(layer,new_body,new_gold,bounds)
                detail=Image.new('RGB',(before.width*2+24,before.height+36),'#f2f3f4')
                detail.paste(before,(8,28));detail.paste(after,(before.width+16,28))
                ImageDraw.Draw(detail).text((8,7),
                    f'{design["id"]} L{layer["index"]+1:02d} {slug}: approved / candidate',
                    fill='#202020')
                detail_path=HERE/f'candidate-detail-{design["id"]}-L{layer["index"]+1:02d}-{slug}.png'
                detail.save(detail_path,optimize=True)
                details.append({'designId':design['id'],'layerNumber':layer['index']+1,
                                'regionBoundsMm':bounds,'image':detail_path.name,
                                'imageSha256':hashlib.sha256(detail_path.read_bytes()).hexdigest()})
        width=2*BOARD_W+3*PAD
        height=HEADER+len(rows)*ROW_H+PAD
        sheet=Image.new('RGB',(width,height),'#f2f3f4')
        draw=ImageDraw.Draw(sheet)
        draw.text((PAD,8),f'{design["name"]}: approved Rev5 / manufacturing candidate',
                  fill='#202020')
        draw.text((PAD,25),f'source {before_hash[:12]}  geometry {after_hash[:12]}  mask {mask_hash[:12]}',
                  fill='#555555')
        for i,(layer,before,after,old_gold,new_gold) in enumerate(rows):
            y=HEADER+i*ROW_H
            sheet.paste(before,(PAD,y))
            sheet.paste(after,(BOARD_W+2*PAD,y))
            draw.text((PAD,y+BOARD_H+4),f'L{layer["index"]+1:02d} approved  gold {old_gold.area:.2f} mm2',
                      fill='#202020')
            draw.text((BOARD_W+2*PAD,y+BOARD_H+4),
                      f'L{layer["index"]+1:02d} candidate  gold {new_gold.area:.2f} mm2',
                      fill='#202020')
        path=HERE/f'candidate-comparison-{design["id"]}.png'
        sheet.save(path,optimize=True)
        records.append({'designId':design['id'],'selectedEnigLayers':len(rows),
                        'image':path.name,
                        'imageSha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        small_w,small_h=geometry_rows[0][1].size
        geometry_sheet=Image.new('RGB',(2*small_w+3*PAD,
                                        HEADER+len(geometry_rows)*(small_h+30)+PAD),
                                 '#f2f3f4')
        gdraw=ImageDraw.Draw(geometry_sheet)
        gdraw.text((PAD,8),f'{design["name"]}: all selected layers approved / candidate',
                   fill='#202020')
        gdraw.text((PAD,25),f'source {before_hash[:12]}  geometry {after_hash[:12]}  mask {mask_hash[:12]}',
                   fill='#555555')
        for i,(layer,before,after) in enumerate(geometry_rows):
            y=HEADER+i*(small_h+30)
            geometry_sheet.paste(before,(PAD,y))
            geometry_sheet.paste(after,(small_w+2*PAD,y))
            gdraw.text((PAD,y+small_h+3),f'L{layer["index"]+1:02d} approved',fill='#202020')
            gdraw.text((small_w+2*PAD,y+small_h+3),
                       f'L{layer["index"]+1:02d} candidate',fill='#202020')
        geometry_path=HERE/f'candidate-geometry-{design["id"]}.png'
        geometry_sheet.save(geometry_path,optimize=True)
        geometry_records.append({'designId':design['id'],'selectedLayers':len(geometry_rows),
                                 'image':geometry_path.name,
                                 'imageSha256':hashlib.sha256(geometry_path.read_bytes()).hexdigest()})
        print(path.name,flush=True)
    report={'status':'visual candidate; inspected art-width gates still pending',
            'approvedGeometrySha256':before_hash,
            'manufacturingGeometrySha256':after_hash,
            'maskCandidateSha256':mask_hash,
            'designs':records,'details':details,
            'allSelectedLayerComparisons':geometry_records}
    (HERE/'candidate-comparisons.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    run()
