# Decision verification — 2026-09-25

Scope: issue 14 decision and representative comparisons. This is not a production-geometry, native KiCad, Gerber or factory pass. See `README.md` for the mandatory issue 15–17 gates.

Runtime: Python 3.13.15; Shapely 2.1.2 / GEOS 3.13.1; Pillow 12.3.0; NumPy 2.5.3 in the `uv` probe environment (the probe does not use NumPy). Policy tests used local Python 3.14. Images use the available Arial/DejaVu font; geometry metrics are independent of that font.

| Check | Result |
| --- | --- |
| `probe_decision.py` via the documented `uv` command | Passed for all 43 selected boards; exactly 56 indexed wide closures; maximum aperture loss 3.05419% at wide L01; support disks, strips, floor, backing, connectivity, Coral/Fault nesting and distinct-boundary material distances passed |
| Top-border geometric checks in that probe | All 45 adjusted top rims are closed annuli with a continuous 0.25 mm gold core; Coral collar and rail inner-edge adaptations included |
| `python3 -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -v` | 8 tests passed: immutable evidence/policy/probe hashes, 56/8 finding inventory, groups, dimensions/score spacing/waste, exact 1,075-piece yield, mechanical constants and probe coverage |
| Unchanged `preview-source/tests/rev5_gold.py` | Passed: 52 board records / 6 effective tops, physical geometry unchanged from Rev4 |
| Unchanged `preview-source/tests/revision_geometry.py` | Passed: all five growth ratios and existing Rev3/Rev4/Rev5 geometry/appearance assertions |
| `git diff --check` | Passed |
| GitHub #15/#16/#17 body-file updates | Read back and matched exactly; prior content retained. Receipt hashes in `dependent-issue-updates.json` |

Foreground self-review applied useful fixes before committing: a first draft aperture-loss budget did not accommodate the measured wide L01 tool envelope, so the explicit 3.5% exception was selected with 3.05419% evidence; a direct full-border-footprint preservation check exposed source rail clearance and three Coral collar setbacks; the final policy preserves closed 0.25 mm gold cores with the documented local repairs. The raster comparison renderer was corrected to redraw genuine board voids after overlapping gold-polygon holes. Probe output hashes now bind it to both the decision policy and the probe source.

Visual review completed by opening the actual `decision-comparisons.png` and `top-border-comparisons.png`: all five top motifs remain recognizable; Spider remains a radial web, Coral/Fault keep irregular openings, Kumiko retains wide angular structure and planar shadows, and Woven keeps its broad maze opening. The H11 closure fills the tiny adjacent aperture and removes the thin sliver. Enlarged border views retain the perimeter and rail/stack rings. The separate local Kumiko mask-retreat example preserves the existing black region and illustrates the operation only.

Remaining work is explicit: #15 must implement and validate every corrected board and artwork union, including final width/residue/access tests and indexed before/after comparisons; #16 must run native KiCad/DRC and actual CAM checks; #17 must generate and validate the scored combined packages. No heavy build, held server, browser or native suite ran in this issue. Factory CAM strategy, quote/finish availability, score handling and physical hardware fit remain pending external confirmation.
