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
findings by source hash, polygon pair and closest points. Its 805 mask pairs,
175 copper pairs and 289 no-disk gold components describe the **pre-repair**
candidate. Use the repaired mask/copper ledgers for subsequent measurements;
the original finding dispositions and full width proof are still open. Do not
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
29.892211 mm² of gold and retain the web. It preserves the nine protected top
rim cores and stays within each 30% gold-loss budget. Indexed terminal caps
reduce the tolerance-aware positive-gold miter residue below 0.00001 mm² on
Fault L01 and Kumiko wide L01/L04/L07, preserving their component and black
pocket counts. Coral still needs local neck repairs, and negative mask width,
copper width and full visual proof remain open. Direct erosion of Fault's
artwork splits its main gold component, so it remains only a diagnostic.

`generate_native.py` writes all 43 selected `.kicad_pcb` files and per-board
`.kicad_pro` configurations into the five panel homes. It checks every
preexisting board hash against the approved handoff or prior generated manifest
before writing; the nine standard alternatives remain untouched. The compact
`native-generation.json` binds output hashes to the manufacturing geometry,
mask and copper candidates. These are **candidate native boards** pending
the remaining art proof and issue 16's native/CAM verification.

Run the lightweight candidate checks with:

```sh
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/build_geometry.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/audit_art_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/repair_mask_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/repair_copper_candidate.py
bash "$HOME/.codex/scripts/heavy-guard.sh" -- uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/generate_native.py
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -v
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/rev5_gold.py
```

The remaining implementation must finish the frozen decision's local Coral
art corrections, negative/positive width checks, selected-finding disposition
ledger and actual full/targeted visual comparisons before these are selected
production boards. Native load/DRC and CAM parsing remain issue #16.
