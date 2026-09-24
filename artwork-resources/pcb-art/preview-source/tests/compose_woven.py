#!/usr/bin/env python3
"""Arrange actual WebGL layer captures at one physical-width scale."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests' / 'output'
fonts = [Path('/tmp/fonts/NotoSansCJKjp-Regular.otf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
font_path = next((p for p in fonts if p.exists()), None)
def font(size):
    return ImageFont.truetype(str(font_path), size) if font_path else ImageFont.load_default(size=size)

width, margin, gutter, tile_h, header = 1560, 24, 20, 460, 100
tile_w = (width - margin * 2 - gutter * 3) // 4
sheet = Image.new('RGB', (width, header + tile_h * 2 + gutter + margin), '#15181c')
draw = ImageDraw.Draw(sheet)
draw.text((margin, 21), 'WOVEN MAZE / INDIVIDUAL PCB LAYERS', fill='#eeeae2', font=font(26))
draw.text((margin, 63), 'L1-L8 / Same physical scale: 101.3 mm wide / L9 is the solid floor', fill='#a6aaa9', font=font(14))
for index in range(8):
    x = margin + (index % 4) * (tile_w + gutter)
    y = header + (index // 4) * (tile_h + gutter)
    draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=9, fill='#202429', outline='#373b3f', width=1)
    color = 'BLACK' if index % 2 == 0 else 'WHITE'
    draw.text((x + 17, y + 13), f'L{index + 1:02d} / {color}', fill='#eeeae2', font=font(18))
    finish = 'ENIG ART / TOP' if index == 0 else 'MASK ONLY'
    draw.text((x + 17, y + 40), finish, fill='#d8b76d' if index == 0 else '#a6aaa9', font=font(12))
    source = Image.open(OUT / f'woven-maze-layer-{index + 1:02d}.png').convert('RGBA')
    bounds = source.getchannel('A').getbbox()
    if bounds is None:
        raise ValueError(f'Layer {index + 1} capture has no rendered pixels')
    crop = source.crop(bounds)
    # All PCB bodies have the same physical width; cropped render widths share
    # this fixed pixel scale. The taller front PCB therefore remains taller.
    target_w = 292
    target_h = round(crop.height * target_w / crop.width)
    assert target_h <= tile_h - 77, f'Layer {index + 1} image unexpectedly exceeds its cell'
    crop = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    left = x + (tile_w - target_w) // 2
    top = y + 69 + (tile_h - 79 - target_h) // 2
    sheet.paste(crop, (left, top), crop)

output = OUT / 'woven-maze-layers-01-08.png'
sheet.save(output, optimize=True)
print(output)
