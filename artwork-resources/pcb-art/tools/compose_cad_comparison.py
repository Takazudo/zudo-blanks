#!/usr/bin/env python3
"""Render the existing exported SVGs; do not redraw or alter any PCB artwork.

Requires Inkscape (PATH or standard macOS application location) and Pillow. All six SVGs use the same millimetre viewBox
and the same export width, so the comparisons retain identical physical scale.
"""
import argparse
import json
import shutil
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = Path('/usr/share/fonts/truetype/dejavu')


def font(size, bold=False):
    candidates = [FONTS / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                  Path('/System/Library/Fonts/Supplemental') / ('Arial Bold.ttf' if bold else 'Arial.ttf')]
    for path in candidates:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vectors-root', type=Path, default=ROOT/'generated'/'rev5-export'/'resources'/'vector')
    ap.add_argument('--output', type=Path, default=ROOT/'generated'/'review'/'pcb-art-cad-gold-comparison.png')
    args = ap.parse_args()
    inkscape = shutil.which('inkscape')
    mac_app = Path('/Applications/Inkscape.app/Contents/MacOS/inkscape')
    if not inkscape and mac_app.is_file():
        inkscape = str(mac_app)
    if not inkscape:
        raise SystemExit('Inkscape was not found. Install it to regenerate this comparison image.')
    rows = [
        ('01-spider-nest', '01-spider-nest-L01-black-enig-art', '01  SPIDER NEST / L01 / TOP'),
        ('01-spider-nest', '01-spider-nest-L03-gold-enig-fill', '01  SPIDER NEST / L03 / FULL GOLD'),
        ('18-woven-maze', '18-woven-maze-L01-black-enig-art', '18  WOVEN MAZE / L01 / TOP'),
    ]
    canvas = Image.new('RGB', (1360, 2470), '#f1f3f5')
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 34), 'GOLD ARTWORK / EXPORT COMPARISON', font=font(35, True), fill='#19212b')
    draw.text((48, 87), 'Actual native-vector resources, rendered at the same physical scale', font=font(21), fill='#596573')
    for x, title, note in [(48, 'Approved preview gold', 'Rev5 approved artwork'),
                           (706, 'CAD candidate', 'Mask edge 0.35 mm / Cu edge 0.30 mm')]:
        draw.text((x + 18, 142), title, font=font(26, True), fill='#19212b')
        draw.text((x + 18, 181), note, font=font(20), fill='#596573')
    with tempfile.TemporaryDirectory(prefix='pcb-cad-comparison-') as scratch:
        for index, (family, board_id, title) in enumerate(rows):
            folder = args.vectors_root / 'selected' / family / board_id
            metadata = json.loads((folder / 'fabrication.json').read_text())
            metrics = metadata['metrics']
            removed = 100 * metrics['goldClippedFraction']
            top = 226 + index * 717
            draw.text((48, top), title, font=font(22, True), fill='#27323e')
            detail = f'Exposed gold removed: {removed:.2f}%'
            draw.text((706, top), detail, font=font(22, True), fill='#865815')
            for column, name in enumerate(['preview_front.svg', 'front.svg']):
                x = 48 + column * 658
                draw.rectangle((x, top + 38, x + 610, top + 699), fill='#e3e7eb')
                output = Path(scratch) / f'{index}-{column}.png'
                subprocess.run([inkscape, str(folder / name), '--export-type=png',
                    '--export-width=507', f'--export-filename={output}'], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                image = Image.open(output).convert('RGBA')
                assert image.width == 507 and image.height in (643, 644)
                canvas.paste(image, (x + (610-image.width)//2, top + 47), image)
    draw.text((48, 2403), 'Gray = cutouts. Board outlines and drills are unchanged; gold artwork is modified for export.',
              font=font(18), fill='#596573')
    draw.text((48, 2433), 'Percentages compare visible gold area, not all copper beneath solder mask. Review the CAD candidate before ordering.',
              font=font(17), fill='#596573')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)
    print(args.output)


if __name__ == '__main__':
    main()
