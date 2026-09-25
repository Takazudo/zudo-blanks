# Indexed manufacturing candidate (incomplete)

`build_geometry.py` reads the immutable Rev5 `preview-source/assets/geometry.json`
and frozen `policy.json`, then writes `manufacturing-geometry.json` and
`indexed-deltas.json`. It closes exactly the 56 selected Kumiko wide apertures,
applies the 1.0 mm cutter sweep to every remaining decorative aperture, moves
the three specified Coral stack rims, and widens 680 selected sub-0.25 mm gold
source strokes to 0.251 mm. It relocates 19 Spider and three Woven guide
paths into retained material and widens 16 Woven bars to 0.251 mm. The ledger
indexes each changed original hole, stroke, fill and specified top rim
operation. Standard Kumiko remains an
unchanged, non-orderable alternative. The approved input and historical tests
are unaffected.

Two indexed Kumiko wide L07 fills (original indices 120 and 134) receive local
additive rectangles to widen tapered gold faces and clear four triangular
mask pockets. The printed gold union gains 1.2575552 mm², entirely in the
0.35 mm mask-safe region. The twelve Fault L01
strokes at exactly 0.25 mm remain unchanged: their nominal width meets the
frozen rule, and an erosion-at-threshold artifact alone does not justify a
source edit.

The geometry is **a routing candidate, not an orderable manufacturing release**.
`audit_art_candidate.py` preserves the original 715 selected copper/mask pair
findings by source hash, polygon pair and closest points. Its 804 mask pairs,
176 copper pairs and 289 no-disk gold components describe the **pre-repair**
candidate. Use the repaired mask/copper ledgers for subsequent measurements;
`art-resolution-ledger.json` cross-references every one of the 715 original
findings with the repaired distinct-component gap screen; 41 of the 65 original
copper findings have nearby indexed joins, while the rest disappear under
other local changes. Full within-component width proof is still open. Do not
use the Rev5 preview as proof of corrected CAM.

`repair_copper_candidate.py` derives F.Cu from the repaired mask and adds 365
indexed hidden 0.251 mm joins: 49 Coral L01, one Fault L01, and 315 across
three selected Kumiko layers. Nine Coral joins move their anchors inward to
keep the bridge inside the copper-safe region. The longest join centerline is
0.2668 mm, below the frozen 0.60 mm cap. No distinct finished copper components
remain closer than 0.25 mm in the candidate. The compact
`copper-repair-ledger.json` carries these source-bound joins; the full copper
polygon cache is local and ignored. This does not yet prove within-component
copper width.

`repair_mask_candidate.py` builds `mask-repair-candidate.json` from the
manufacturing geometry. It keeps the 56 closed Kumiko apertures mask-colored,
removes indexed isolated gold fragments that cannot contain a 0.25 mm disk,
and applies indexed local one-sided retreats to clear distinct-component mask
gaps. Three measured Spider guide-to-web slivers instead use exactly four
indexed closing patches with no original black paint; the patches add
29.892211 mm² of gold and retain the web. The complete Spider network
decision supersedes the earlier single rib: one exact union from the captured
pre-rib body adds 73.921152 mm², then the indexed cutter cleanup adds
2.208271 mm² across 15 original apertures. Fifty evidence-indexed guide
portions move, with the source central strokes and four earlier channel patches
retained. The serialized holes are valid and the finite cutter ledger still
covers all 754 original aperture records. The present network artwork remains
diagnostic: seven black components have no 0.25 mm disk, including three long
channels beside source strokes 12/20/22 omitted by the bounded decision survey.
These need a further design decision; the candidate does not pass black width
or transition checks. It preserves the nine protected top
rim cores and stays within each 30% gold-loss budget. Coral L01 has five
source-indexed neck-centerline relocations, 19 indexed unpainted rim-island
merges and a 0.251 mm local gold corridor bound to strokes 527/524. That
corridor adds 0.05877989 mm² and clears its measured positive and negative
local width wedges. Indexed terminal caps
reduce the tolerance-aware positive-gold miter residue below 0.00001 mm² on
Fault L01 and Kumiko wide L01/L04/L07, preserving their component and black
pocket counts. Three indexed Fault black pockets between source strokes
16/52, 20/52 and 16/57 are locally widened with compensating gold restoration
and caps; the composite adds 0.887012277 mm², removes 0.629928518 mm², keeps
six gold components and all rim cores, and leaves no no-disk ink component.
Two source-pair-indexed Fault butt/round joins at 24/29 and 19/23 add
0.014198 mm² gold and reconnect two eroded-core branches near the top cliff.
One Kumiko top black facet beside fill 137 and rail rim 7 receives an indexed
0.299323 mm² gold retreat; its lower 116/117 facet remains open.
Eight source-indexed unpainted Woven L01 terminal ink tips along strokes
8–11 receive 0.040917 mm² of bounded gold caps. Its serialized negative-mask
miter residue falls below 0.000001 mm² while retaining twelve gold paths,
their twelve openings, and all thirteen black components.
Other Coral width candidates, Spider network/transition widths, Fault/Kumiko
remaining black-mask necks, and copper within-component width remain open.
Direct erosion of Fault's artwork still splits one main gold core after the
indexed neck additions.

`generate_native.py` writes all 43 selected `.kicad_pcb` files and per-board
`.kicad_pro` configurations into the five panel homes. It checks every
preexisting board hash against the approved handoff or prior generated manifest
before writing; the nine standard alternatives remain untouched. The compact
`native-generation.json` binds output hashes to the manufacturing geometry,
mask and copper candidates. These are **candidate native boards** pending
the remaining art proof and issue 16's native/CAM verification.

`audit_tool_access.py` records 754 original decorative hole domains: exactly
56 indexed closures and two split center regions, each with separate valid
plunge points (Kumiko wide L05 hole 14 and Woven L04 hole 0). Every surviving
center component has a finite path made of its boundary loops and 0.50 mm
scanlines; the script proves its 1.0 mm swept union covers the candidate cutout
without leaving the original aperture. Actual machine CAM and cutter/plunge
availability remain external checks.
`audit_final_width.py` records positive gold, negative mask and copper
reconstruction residues from serialized candidate polygons, with source-art
indices for the largest findings; it is a diagnostic, not a pass. Five
`candidate-comparison-*.png` images show actual before/after ENIG unions in a
common coordinate frame and are tied to the source hashes in
`candidate-comparisons.json`. Five `candidate-geometry-*.png` images cover all
43 selected layers, and nine `candidate-detail-*.png` views enlarge local art
changes. Foreground visual inspection of these rendered unions found the five
motifs and all selected layer paths recognizable after routing adaptation,
including Coral/Fault nesting, Kumiko angular facets and seven distinct Woven
lower paths. The Spider guide-channel detail also exposes unresolved narrow
black channels; the visual comparison is not a width or CAM pass.

Run the lightweight candidate checks with:

```sh
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/build_geometry.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/audit_art_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/repair_mask_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/repair_copper_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/resolve_art_findings.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/audit_tool_access.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/audit_final_width.py
uv run --python 3.13 --with shapely==2.1.2 --with pillow python artwork-resources/pcb-art/manufacturing/render_candidate_comparisons.py
bash "$HOME/.codex/scripts/heavy-guard.sh" -- uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/generate_native.py
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -v
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/rev5_gold.py
```

The remaining implementation must finish the frozen decision's local positive
and negative art-width corrections, copper width and source-attributed
boundary-run checks, actual CNC path proof, and targeted visual comparisons
before these are selected
production boards. Native load/DRC and CAM parsing remain issue #16.
