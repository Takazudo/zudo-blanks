#!/usr/bin/env python3
"""Review board showing real front-view renders and enlarged flat ENIG frames."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests' / 'output'
fonts = [Path('/tmp/fonts/NotoSansCJKjp-Regular.otf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
font_path = next((p for p in fonts if p.exists()), None)
def font(size):
    return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default(size=size)

items = [('spider-nest','01 / SPIDER NEST'), ('coral-vault','03 / CORAL VAULT'), ('fault-line','13 / FAULT LINE'), ('kumiko-void','17 / KUMIKO VOID — WIDE'), ('woven-maze','18 / WOVEN MAZE')]
width, margin, gap, card_w, header, card_h = 2080, 24, 18, 392, 112, 604
sheet = Image.new('RGB', (width, 1135), '#171a1e')
draw = ImageDraw.Draw(sheet)
draw.text((margin,21), 'REV 05 / TOP PCB GOLD BORDERS', font=font(29), fill='#eeeae2')
draw.text((margin,67), 'Actual WebGL renders / hardware hidden / unchanged cutouts / flat front copper and solder-mask openings', font=font(17), fill='#afb4b5')
models = {}
for i, (key, title) in enumerate(items):
    source = Image.open(OUT / f'{key}-top-render.png').convert('RGBA')
    bbox = source.getchannel('A').getbbox()
    assert bbox
    crop = source.crop(bbox)
    models[key] = crop
    left = margin + i * (card_w + gap)
    draw.rounded_rectangle((left,header,left+card_w,header+card_h),radius=9,fill='#24292f',outline='#41484e')
    draw.text((left+17,header+16),title,font=font(18),fill='#e9d399')
    outline = 'OCTAGONAL SCREW RIMS' if key in ['spider-nest','kumiko-void'] else 'ROUND SCREW RIMS'
    draw.text((left+17,header+49),outline,font=font(13),fill='#afb4b5')
    target_w = 350
    target_h = round(target_w * crop.height / crop.width)
    target = crop.resize((target_w,target_h),Image.Resampling.LANCZOS)
    sheet.paste(target,(left+(card_w-target_w)//2,header+91),target)
    draw.text((left+17,header+card_h-46),'1 outside frame + 4 screw rims + 4 slot rims',font=font(12),fill='#afb4b5')
    draw.text((left+17,header+card_h-24),'101.3 × 128.5 mm / top only',font=font(12),fill='#afb4b5')

# Crops remain images of the actual model; annotations do not invent geometry.
examples = [
    ('spider-nest',(0,0,24,15),'OUTSIDE FRAME + RAIL SLOT','Flat gold lines meet around the actual mounting slot.'),
    ('spider-nest',(1.4,18.5,11.6,28.7),'ANGULAR SCREW RIM / SPIDER','The screw hole stays round; its gold frame has 8 facets.'),
    ('woven-maze',(1.4,18.5,11.6,28.7),'ROUND SCREW RIM / WOVEN','Matching width; same top-only ENIG finish policy.'),
]
y = 744
for i,(key,(x0,y0,x1,y1),title,note) in enumerate(examples):
    left = margin+i*686
    draw.rounded_rectangle((left,y,left+668,1111),radius=9,fill='#24292f',outline='#41484e')
    draw.text((left+19,y+17),title,font=font(18),fill='#e9d399')
    im=models[key]
    crop=im.crop((round(x0/101.3*im.width),round(y0/128.5*im.height),round(x1/101.3*im.width),round(y1/128.5*im.height)))
    scale=min(600/crop.width,248/crop.height)
    enlarged=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
    sheet.paste(enlarged,(left+(668-enlarged.width)//2,y+55+(248-enlarged.height)//2),enlarged)
    draw.text((left+19,y+324),note,font=font(13),fill='#afb4b5')

path=OUT/'pcb-art-top-gold-borders.png'
sheet.save(path,optimize=True)
print(path)
