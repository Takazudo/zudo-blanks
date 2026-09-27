#!/usr/bin/env python3
"""Copy only browser-facing handoff resources into a zudo-doc public tree."""
from pathlib import Path
import argparse
import json
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path, help='Generated zudo-doc project root, or docs-overlay')
    parser.add_argument('--handoff', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    handoff, site = args.handoff.resolve(), args.site.resolve()
    if not (site / 'zfb.config.ts').is_file():
        parser.error('The target must contain zfb.config.ts.')
    dest = site / 'public/assets/pcb-art'
    required = [
        handoff/'preview-source/dist/index.html',
        handoff/'resources/images/pcb-art-previews-overview.png',
        handoff/'resources/images/kumiko-void-variants.png',
        handoff/'resources/images/woven-maze-layers-01-08.png',
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        parser.error('Missing required handoff resources: ' + ', '.join(missing))
    copies = []
    for source, subdir, patterns in [
        (handoff/'preview-source/dist', 'previews', ['index.html']),
        (handoff/'resources/images', 'images', ['*.png','*.svg']),
        (handoff/'resources/manufacturing-review', 'manufacturing-review', ['*.png','*.svg','*.csv']),
        (handoff/'resources/vector', 'vector', ['**/*.svg','**/*.dxf']),
    ]:
        for pattern in patterns:
            for p in sorted(source.glob(pattern)):
                target = dest/subdir/p.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p,target)
                copies.append(str(target.relative_to(site)))
    for relative in ['pcb/manifest.json','pcb/manifest.csv','validation/fabrication-review.json','validation/fabrication-review.md','validation/export-art-review.json','validation/export-art-review.md','reports/native-independent-audit.json','resources/order/order-plan.csv','resources/order/hardware-plan.csv']:
        p = handoff/relative
        if p.is_file():
            target = dest/'records'/p.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p,target)
            copies.append(str(target.relative_to(site)))
    print(json.dumps({'copied': len(copies), 'files': copies},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
