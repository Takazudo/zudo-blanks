#!/usr/bin/env python3
"""Same-scale before/after top silhouettes drawn from exact serialized polygons."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests' / 'output'
old = json.loads((ROOT / 'assets' / 'reference-revision3.json').read_text())
new = json.loads((ROOT / 'assets' / 'geometry.json').read_text())
metrics = json.loads((OUT / 'revision-geometry-report.json').read_text())['growth']
previous = {d['id']: d for d in old['designs']}
current = {d['id']: next((v for v in d.get('variants', []) if v['variantId'] == d.get('defaultVariant')), d) for d in new['designs']}
ids = ['spider-nest','coral-vault','fault-line','kumiko-void','woven-maze']
labels = ['Spider Nest','Coral Vault','Fault Line','Kumiko Void','Woven Maze']
font_path = next((p for p in [Path('/tmp/fonts/NotoSansCJKjp-Regular.otf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()), None)
def font(size):
    return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default(size=size)

margin, gap, cell_w, cell_h, header, row_gap = 24, 16, 370, 465, 132, 27
image = Image.new('RGB', (margin*2+5*cell_w+4*gap,header+2*cell_h+row_gap+24), '#171a1e')
draw = ImageDraw.Draw(image)
draw.text((margin,19), f'TOP OPENINGS / REVISION 3 + REVISION {new["revision"]}', fill='#eeeae2', font=font(27))
draw.text((margin,62), 'Exact PCB silhouettes at the same physical scale. Light areas are openings; artwork is omitted.', fill='#b1b5b5', font=font(15))
draw.text((margin,89), 'Current Kumiko shows the wide variant; the original standard geometry is preserved.', fill='#b1b5b5', font=font(14))
scale, supersample = 2.74, 3
for col, key in enumerate(ids):
    for row, design in enumerate([previous[key], current[key]]):
        x, y = margin+col*(cell_w+gap),header+row*(cell_h+row_gap)
        draw.rounded_rectangle((x,y,x+cell_w,y+cell_h),radius=8,fill='#24292f',outline='#3e444b')
        draw.text((x+16,y+11), labels[col],fill='#eeeae2',font=font(18))
        if row == 0:
            label = f"REV 3 / {metrics[key]['beforeAreaMm2']:,.0f} mm²"
        else:
            pct = (metrics[key]['ratio']-1)*100
            label = f"REV {new['revision']} / {metrics[key]['afterAreaMm2']:,.0f} mm² / +{pct:.1f}%"
        draw.text((x+16,y+39),label,fill='#a8adae' if row==0 else '#dec381',font=font(13))
        layer=design['layers'][0]
        panel_w=round(new['spec']['width']*scale)
        panel_h=round(new['spec']['height']*scale)
        canvas=Image.new('RGB',(panel_w*supersample,panel_h*supersample),'#e9e4da')
        cd=ImageDraw.Draw(canvas)
        points=lambda pts:[(round(px*scale*supersample),round(py*scale*supersample)) for px,py in pts]
        cd.polygon(points(layer['outer']),fill='#0c0e11')
        for hole in layer['holes']:cd.polygon(points(hole),fill='#e9e4da')
        canvas=canvas.resize((panel_w,panel_h),Image.Resampling.LANCZOS)
        image.paste(canvas,(x+(cell_w-panel_w)//2,y+76))
        if row==1 and key=='kumiko-void':draw.text((x+16,y+cell_h-27),'WIDE VARIANT',fill='#dec381',font=font(12))
path=OUT/'pcb-art-openings-before-after.png'
image.save(path,optimize=True)
print(path)
