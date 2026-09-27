#!/usr/bin/env python3
"""Write quantities per complete five-design set. Does not place any order."""
from pathlib import Path
import argparse
import csv
import json

ROOT = Path(__file__).resolve().parents[1]

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sets', type=int, default=1)
    p.add_argument('--kumiko', choices=['wide', 'standard'], default='wide')
    p.add_argument('--output', type=Path, default=ROOT/'generated'/'order-plan')
    args = p.parse_args()
    if args.sets < 1:
        p.error('--sets must be at least 1')
    manifest = json.loads((ROOT/'pcb/manifest.json').read_text())
    selected = [b for b in manifest['boards'] if
                (b['designId'] != 'kumiko-void' and b['category'] == 'selected') or
                (b['designId'] == 'kumiko-void' and b['variant'] == args.kumiko)]
    if len(selected) != 43:
        raise RuntimeError('Expected exactly 43 boards for the selected complete set')
    rows = []
    for board in selected:
        rows.append({
            'board_id': board['id'], 'design': board['designId'],
            'kumiko_variant': board['variant'] or '', 'front_to_back_layer': board['layerNumber'],
            'mask_color': board['maskColor'], 'surface_intent': board['finish'],
            'thickness_mm': board['thicknessMm'],
            'required_quantity': args.sets, 'supplier_order_quantity': '',
            'native_board': board['nativeBoard'],
            'fabrication_status': 'EDITABLE DRAFT - resolve routing, local KiCad DRC and CAM before order',
        })
    write_csv(args.output/'order-plan.csv', rows)
    hardware = [
        {'part': 'M3 x 40 mm stack screw', 'quantity_per_set': 8, 'quantity': 8*args.sets,
         'dimensions_or_basis': 'Two 8-PCB stacks; 33.8 mm + assumed 2.4 mm nut + 1.0 mm allowance = 37.2 mm',
         'status': 'Length candidate; confirm actual nut/washer and case clearance'},
        {'part': 'M3 x 45 mm stack screw', 'quantity_per_set': 12, 'quantity': 12*args.sets,
         'dimensions_or_basis': 'Three 9-PCB stacks; 38.4 mm + assumed 2.4 mm nut + 1.0 mm allowance = 41.8 mm',
         'status': 'Length candidate inherited from Strip Mine; confirm actual hardware'},
        {'part': 'Unthreaded spacer', 'quantity_per_set': 152, 'quantity': 152*args.sets,
         'dimensions_or_basis': 'Height 3.0 mm, OD 6.0 mm, ID 3.2 mm; 2 x 7 gaps x 4 + 3 x 8 gaps x 4',
         'status': 'Confirm material, tolerance and actual fit'},
        {'part': 'M3 nut', 'quantity_per_set': 20, 'quantity': 20*args.sets,
         'dimensions_or_basis': 'Four stack nuts per design; 2.4 mm thickness is the screw-length calculation assumption',
         'status': 'Confirm purchased nut dimensions; no specific supplier item selected'},
        {'part': 'Rail mounting screw', 'quantity_per_set': 20, 'quantity': 20*args.sets,
         'dimensions_or_basis': 'Four rail slots per top; thread and length depend on the actual Eurorack case',
         'status': 'Select for actual rail/nut; separate from the stack screws'},
    ]
    write_csv(args.output/'hardware-plan.csv', hardware)
    (args.output/'README.md').write_text(
        '# Draft Order Preparation\n\n'
        f'This plan lists the required quantities for {args.sets} five-design set(s). Kumiko variant: `{args.kumiko}`.\n\n'
        '`order-plan.csv` lists the 43 PCB board types and required quantities. It does not estimate factory minimum lots, spares, panelization, or discounts. '
        'Fill in `supplier_order_quantity` only after receiving a quote. This script does not place an order.\n\n'
        'The screw lengths in `hardware-plan.csv` are candidates based on board and spacer thickness plus an assumed nut thickness. '
        'Confirm washer allowance, spacer tolerances, actual screw and nut dimensions, rear protrusion, and case depth before use.\n\n'
        'To change the quantity or Kumiko variant, write to a separate destination, for example: '
        '`python3 artwork-resources/pcb-art/tools/make_order_plan.py --sets 2 --kumiko standard --output artwork-resources/pcb-art/generated/order-standard-2sets`.\n',
        encoding='utf-8')
    print(json.dumps({'boards': len(selected), 'sets': args.sets, 'kumiko': args.kumiko,
                      'requiredPcbQuantity': len(selected)*args.sets, 'output': str(args.output)}))

if __name__ == '__main__':
    main()
