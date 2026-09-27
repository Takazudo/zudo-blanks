# Native PCB manufacturing candidate

This directory contains a reproducible **candidate**, not a factory-approved
order. The approved Rev5 preview and historical Rev4/Rev5 tests remain separate
and unchanged. `manufacturing-geometry.json` is the corrected geometry used for
native output. `policy.json` and the decision evidence remain the frozen source
contract; `indexed-deltas.json` records the geometry changes.

## What was generated

- The selected inventory is 43 native boards in five `panels/art-*` homes. Nine
  standard Kumiko alternatives remain unchanged and non-orderable. The native
  manifest binds board/project hashes to the geometry, mask and copper inputs.
- Exactly 56 small apertures in selected Kumiko wide boards were closed. Every
  remaining decorative aperture received the indexed 1.0 mm cutter-envelope
  correction. The tool-access ledger covers 754 original aperture records,
  including separate center regions and plunges for Kumiko wide L05 hole 14
  and Woven L04 hole 0. Functional holes and slots remain NPTH.
- Spider L01 follows the current unfiltered-network decision: 34 source paths
  receive one ribbon union, adding 112.960935002 mm² before the indexed
  3.429195687 mm² routing cleanup; all 19 original decorative apertures change,
  and 68 indexed guide portions move. The earlier four channel patches remain
  distinct and bounded. The nine top rim cores and common drill centers remain.
- The repaired mask cache contains 11 ENIG artwork boards with 3,464 indexed
  local width edits and no unresolved entries from the local enforcement pass.
  The repaired copper cache/ledger contains 533 indexed hidden joins, 20 using
  inset anchors, 1,210 local copper width edits, and no unresolved entries from
  that pass. Copper is generated beneath mask openings; lower mask-only boards
  contain no decorative copper or mask openings.
- `art-resolution-ledger.json` cross-references all 715 inherited selected
  artwork findings by source hash, original polygon indices and coordinates.
  The nine standard alternatives retain their separate findings.

The numeric classes come from the process-class amendment: 0.13 mm black mask
web on Coral/Fault/Kumiko/Woven tops when ordered with unchanged mask, 0.25 mm
on Spider; 0.25 mm visible gold and other special copper/channel widths. Four
full-gold lower pours and isolated convex copper islands use the documented
0.10 mm general copper class. The source-bound local repairs and final candidate
unions are checked in the practical tests below. The optional exhaustive
opposing-boundary certificate has not been regenerated for this candidate.

## Native serialization and appearance

`generate_native.py` first checks every existing selected board and project
against approved or prior generated hashes, then writes the 43 selected
`.kicad_pcb` files and their `.kicad_pro` fabrication settings. It never
overwrites an unknown manual edit. Two split contours in Coral L01 F.Cu become
self-intersecting only after 1 nm native rounding; the candidate-only fallback
snaps and repartitions those two pieces, validates every emitted contour and
records a 0.000266718 mm² serialized union difference, below the existing
0.02 mm² exporter limit. The approved geometry and exporter are untouched.

`candidate-comparisons.json` binds before/after figures to the approved source,
manufacturing geometry and current mask hashes. The approved side is a visual
reference; the candidate side shows corrected unions, not verified CAM. The
five motifs remain recognizable in the full-board renders. Enlarged Spider
guide, Coral neck and Kumiko facet views expose visible local thickening and
retreats; inspect the actual plots before using the native boards.

## Verification scope

The default manufacturing tests check immutable-source bindings, inventory,
indexed geometry changes, support disks, drill registration, tool-center and
plunge records, source-bound local mask/copper repairs, protected top rims,
native file hashes, NPTH counts, and alternatives. The unchanged Rev5 history
tests still run against approved inputs. Targeted native KiCad DRC and CAM
checks are the next independent gate in issue #16; order, quote and physical
fit remain external checks.

`audit_final_width.py` and `audit_width_proof.py` remain available for an
optional exhaustive art-width investigation. Their outputs
`final-width-audit.json` and `width-proof.json` are intentionally ignored and
absent from the committed candidate because older copies were bound to stale
mask/copper hashes. `tests/exhaustive_width_proof.py` retains the strict proof
assertions for an explicit regenerated run; a local enforcement result is not
presented as that certificate. Its Spider outside-envelope attribution check
currently measures 0.00006427 mm² of aggregate residue across 17 tiny pieces,
above the frozen 0.00001 mm² area tolerance. That remains an open diagnostic,
not a passed manufacturing-width claim.

Run the practical checks from the repository root:

```sh
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -p 'test_*.py' -v
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/rev5_gold.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/revision_geometry.py
```

The full mask/copper regeneration is expensive and should use the repository's
guarded pipeline. `generate_native.py` also runs under the heavy guard; its
manifest hashes record the exact candidate inputs and output files.
