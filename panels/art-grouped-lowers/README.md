# Combined lower-board fabrication packages

These native KiCad projects reproduce the five multi-board lower grids in the
frozen [fabrication policy](../../artwork-resources/pcb-art/manufacturing/policy.json).
They place the verified lower boards in sorted ID, row-major order using
translation only. Every decorative aperture stays on `Edge.Cuts`; each member's
outer rectangle is a `Dwgs.User` score boundary. The panel has one routed outer
profile and 5 mm sacrificial rails on all sides. Unoccupied grid cells contain
no duplicate artwork or drills and are declared waste.

KiCad 10's outline stitcher was sensitive to the initial primitive of three
translated decorative loops. The builder rotates those loops' serialized line
order at recorded witnesses. It retains the exact contour segment multiset;
the verifier compares every native and CAM segment against the source geometry.

| Grid | Cells | Members | Blank cells | Finished sheet (mm) |
| --- | ---: | ---: | ---: | ---: |
| white lead-free HASL | 2 × 4 | 7 | 1 | 212.6 × 387.2 |
| black ENIG | 3 × 2 | 6 | 0 | 313.9 × 198.6 |
| red lead-free HASL | 3 × 4 | 10 | 2 | 313.9 × 387.2 |
| green lead-free HASL | 2 × 2 | 4 | 0 | 212.6 × 198.6 |
| black lead-free HASL | 2 × 4 | 8 | 0 | 212.6 × 387.2 |

The three purple, yellow and blue lower boards are individually routed
singletons. The five black ENIG tops also remain standalone. Their original
native sources and verified issue 16 CAM ZIPs are referenced by the order
manifest; they are not purchased again as part of a scored sheet.

From the repository root, regenerate the native grids:

```sh
uv run --python 3.13 --with shapely==2.1.2 --with pillow \
  python artwork-resources/pcb-art/manufacturing/build_lower_panels.py
```

KiCad 10 is required for native DRC and actual Gerber/Excellon verification.
The output path below is local and ignored. The prior issue 16 path holds the
43 individually verified ZIPs, of which eight are directly orderable here.

```sh
uv run --python 3.13 --with shapely==2.1.2 --with pillow \
  python artwork-resources/pcb-art/manufacturing/verify_lower_panels.py \
  --output /tmp/zudo-blanks-issue17-panel-cam \
  --prior-output /tmp/zudo-blanks-issue16-native-cam-release \
  --kicad-cli /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
```

For a resumed CAM export, `--reuse-drc-reports /path/to/mapping.json` accepts
an exact mapping of all five panel IDs to `nativeBoardSha256`, `reportPath` and
`reportSha256`. The verifier checks each native hash and raw KiCad 10 JSON
report, including its source name, units, severities and clean findings,
before reusing the DRC result. Omitting this option runs fresh DRC.

The build record `lower-panels-native.json` binds source hashes, placements,
score lines and measured clearance. A `null` copper or visible-gold clearance
means that the mask-only group has no corresponding front artwork. The CAM
report binds DRC results and local
ZIP hashes. `lower-panels-order-manifest.json` accounts for 25 complete stacks
of each of the five designs: 43 selected IDs × 25 = 1,075 useful pieces,
75 blank waste cells, and 325 ordered sheets or standalone boards across
13 packages. Hardware totals are 500 screws, 3,800 spacers and 500 nuts.

The `FABRICATION.txt` in each grid ZIP instructs the fabricator to V-score all
full-length `Dwgs.User` lines (exported as `User_Drawings.gbr`), route only
the panel outer edge and decorative apertures from `Edge.Cuts`, and drill the
NPTH Excellon hits. Score lines do not
appear on silkscreen. The published scored-edge tolerance is ±0.4 mm; the
separately drilled mount centers determine stack registration.

**Pending external checks:** factory CAM approval, residual score-web depth,
perforated-sheet handling, actual color/finish availability and quote,
physical stack fit, washer/nut tolerances and usable screw length. Local DRC
and CAM evidence is not a purchase or factory acceptance.
