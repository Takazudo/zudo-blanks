#!/usr/bin/env python3
"""Side-by-side actual WebGL captures from an identical Kumiko camera pose."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests'/'output'
font_path=next((p for p in [Path('/tmp/fonts/NotoSansCJKjp-Regular.otf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()),None)
def font(size):return ImageFont.truetype(str(font_path),size) if font_path else ImageFont.load_default(size=size)
images=[]
for variant in ['standard','wide']:
    im=Image.open(OUT/f'kumiko-void-{variant}-render.png').convert('RGBA')
    bounds=im.getchannel('A').getbbox()
    assert bounds is not None
    images.append(im.crop(bounds))
scale=min(610/max(im.width for im in images),660/max(im.height for im in images))
result=Image.new('RGB',(1440,900),'#171a1e')
d=ImageDraw.Draw(result)
d.text((25,19),'KUMIKO VOID / STANDARD + WIDE',font=font(28),fill='#eeeae2')
d.text((25,63),'Actual 3D renders / identical camera and display settings / same physical scale',font=font(15),fill='#a8adae')
for i,(im,label,detail) in enumerate(zip(images,['STANDARD / 標準','WIDE / 開口拡大'],['Original geometry + new common gold borders','Larger openings, same 9-PCB color / ENIG sequence'])):
    x=24+i*704
    d.rounded_rectangle((x,108,x+688,876),radius=9,fill='#24292f',outline='#3e444b')
    d.text((x+19,124),label,font=font(20),fill='#dec381')
    d.text((x+19,156),detail,font=font(13),fill='#a8adae')
    resized=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
    # Shared scale; leave a fixed title area above the actual renders.
    result.paste(resized,(x+(688-resized.width)//2,190+(674-resized.height)//2),resized)
path=OUT/'kumiko-void-variants.png'
result.save(path,optimize=True)
print(path)
