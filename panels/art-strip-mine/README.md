# Strip Mine

A decorative 20HP Eurorack blank made from nine stacked PCBs. The top board carries gold (ENIG)
contour-line artwork with small building clusters around an open-pit mine. Each board below has
a smaller faceted cutout, so looking into the pit you see the terraces step down through
alternating black and red boards to a blue "lake" at the bottom. There are no electronics. Every
board is FR-4 with M3 stack holes. Boards 01–08 carry exposed copper; blue board 09 is copper-free.

- Epic: https://github.com/Takazudo/zudo-blanks/issues/2
- Interactive preview: [`preview/index.html`](preview/index.html). Open it directly over
  `file://`; it needs no server. The boards use preview pattern 5 ("Strata, blobs") with
  buildings on.

## Stack

Top to bottom. Each board is 1.6 mm thick and sits on 3 mm spacers, so the stack is
9 × 1.6 + 8 × 3 = **38.4 mm** deep.

| # | Board dir | Colour | Outline | Cutout | Cutout index (`openings[i]`) |
| --- | --- | --- | --- | --- | --- |
| 1 | `pcb-01-black` | Black | Full 20HP panel with the rail slots (art-ufo-v2 outline) | yes | 0 |
| 2 | `pcb-02-red` | Red | 101.3 × 94.3 mm, clear of the rails | yes | 1 |
| 3 | `pcb-03-black` | Black | same as 2 | yes | 2 |
| 4 | `pcb-04-red` | Red | same as 2 | yes | 3 |
| 5 | `pcb-05-black` | Black | same as 2 | yes | 4 |
| 6 | `pcb-06-red` | Red | same as 2 | yes | 5 |
| 7 | `pcb-07-black` | Black | same as 2 | yes | 6 |
| 8 | `pcb-08-red` | Red | same as 2 | yes | 7 |
| 9 | `pcb-09-blue` | Blue | same as 2 | no | none |

Only board 1 mounts to the rails, through the four slots copied verbatim from `art-ufo-v2`.
The lower boards hang from it on four M3 screws at (6.5, 23.6), (94.8, 23.6), (6.5, 104.9) and
(94.8, 104.9) mm. Those positions are identical on all nine boards.

## Hardware BOM

| Qty | Part |
| --- | --- |
| 4 | M3 × 45 mm screw |
| 32 | Spacer, 3 mm tall, Ø6 mm OD, Ø3.2 mm ID (8 gaps × 4 screws) |
| 4 | M3 nut |

The minimum screw length under the head is 38.4 mm of stack + 2.4 mm of nut + 1.0 mm of margin =
**41.8 mm**, so M3 × 45 is the shortest standard size that works. M3 × 40 is 1.8 mm too short
to engage a standard 2.4 mm nut fully, so don't use it with a standard nut.

## JLCPCB order notes

Order each of the nine boards as its own design, using the files in `pcb-NN-*/gerber/`:

- Base material FR-4, 2 layers, **1.6 mm**, 1 oz outer copper
- Boards 01–08: **ENIG** (the exposed copper artwork is the visible gold).
- Board 09: **no ENIG**, no copper on either side, four unplated Ø3.2 mm holes.
  Choose the vendor’s non-ENIG standard option (e.g. lead-free HASL if a finish is mandatory);
  there are no copper pads to finish. Ask CAM to retain the copper-free blue-mask design.
- Solder mask colour per board: black for 01/03/05/07, red for 02/04/06/08, blue for 09
- **No silkscreen** (the silkscreen gerbers are empty)
- Board 1 has four plated 3.2 × 10.28 mm slots. Boards 01–08 have four Ø3.2 mm plated holes; board 09 has four unplated holes.

Copper reaches the routed edge on purpose (edge band and pit rims), same as art-ufo-v2 which was
produced this way. Board 1’s outer copper and mask band is continuous across all four
rail slots and intentionally overlaps their pads, forming one exposed frame. KiCad reports
four clearance violations at these intentional no-net pad/frame joins.

## Regenerate and check

The boards are generated. Never edit the `.kicad_pcb` files by hand; change
`preview/geometry.js` (shared with the preview) or `scripts/build-pcbs.mjs` and regenerate:

```sh
node panels/art-strip-mine/scripts/build-pcbs.mjs
```

The pattern is chosen in the generator: `PATTERN = 4` in `build-pcbs.mjs` is preview pattern 5
(`TOP_VARIANTS` is zero-based).

Then run the fabrication checks:

```sh
node panels/art-strip-mine/scripts/check-pcbs.mjs
```

It prints PASS/FAIL per check and exits 1 on any failure:

1. KiCad DRC on every board with all severities. The only ignored rules that differ from the
   art-ufo-v2 template are `copper_edge_clearance`, `shorting_items` and `solder_mask_bridge`
   (the artwork breaks these on purpose), plus `lib_footprint_issues` and
   `lib_footprint_mismatch` (the repo has no fp-lib-table for the Takazudo library).
2. Gerbers (Protel extensions) and Excellon drills written into each `pcb-NN-*/gerber/`
   (gitignored). The check asserts empty silkscreens, 4 × Ø3.2 holes, the 4 slots on board 1
   only, and closed Edge.Cuts contours (2 on boards 01–08, 1 on board 09).
3. Output-level copper: each F.Cu layer is plotted to SVG. The script requires ≥ 0.35 mm between
   separate copper islands, measured exactly on the plotted primitives. It also requires every
   copper feature to be ≥ 0.25 mm wide, tested by morphological opening of a 20 px/mm raster.
4. Each pit cutout lies inside the one above it with a step of at least 2 mm.
5. Board 1's slot footprints equal the art-ufo-v2 ones (uuids aside).
6. Every board is 1.6 mm thick, the colour order matches `LAYERS`, and the screw pads line up.

Check 3 needs Python 3 with Pillow, numpy and scipy. Keep the venv outside the repo and point
the script at it:

```sh
python3 -m venv /tmp/strip-mine-venv
/tmp/strip-mine-venv/bin/pip install pillow numpy scipy
STRIP_MINE_PYTHON=/tmp/strip-mine-venv/bin/python node panels/art-strip-mine/scripts/check-pcbs.mjs
```

`KICAD_CLI` overrides the kicad-cli path (default: the macOS KiCad.app bundle). Unit tests for the
shared code: `node panels/art-strip-mine/preview/geometry.test.mjs` and
`node panels/art-strip-mine/scripts/emit.test.mjs`.

## Combined lower-board panels

The board dimensions and screw positions are unchanged. Keep top board 01 separate for its
clean outer edge, and blue board 09 separate to avoid ENIG. Alternative quote packages:

| Package | Contents per panel | Size | Finish |
| --- | --- | --- | --- |
| panel-black | 03, 05, 07, left to right | 303.9 × 94.3 mm | ENIG, black |
| panel-red | 02, 04 top row; 06, 08 bottom row | 202.6 × 188.6 mm | ENIG, red |
| pcb-09-blue | 09 | 101.3 × 94.3 mm | No ENIG, blue |

Use **Panel by customer**, declaring **3 different designs** for black and **4** for red.
Each panel produces one stack's boards of that colour. Do not also order the individual
lower boards unless intentionally buying extras. Panelization savings are not confirmed;
compare quotes including the different-design fees.

The separate **User_Drawings.gbr** contains full-span V-score lines, not milling or
silkscreen. Edge_Cuts contains only the panel perimeter and routed pit openings.
Break only the scored outer seams; the visible pit edges stay routed. The ZIP includes
FABRICATION.txt with these instructions. CAM must confirm scoring and the intentional
copper at routed pit edges before manufacture. Reference:
https://jlcpcb.com/help/article/pcb-panelization

Regenerate panel sources, export both panels and the blue board, then verify:
```sh
node panels/art-strip-mine/scripts/build-panels.mjs
python3 panels/art-strip-mine/scripts/export-panels.py
node panels/art-strip-mine/scripts/panels.test.mjs
```

Each output directory contains its own `*-gerbers.zip` (local, gitignored). The original
individual board sources remain available. The interactive stack preview also shows
board 09 without gold mounting pads.
