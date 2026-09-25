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
additive rectangles to widen tapered gold faces. The printed gold union gains
1.1963052 mm², entirely in the 0.35 mm mask-safe region. The twelve Fault L01
strokes at exactly 0.25 mm remain unchanged: their nominal width meets the
frozen rule, and an erosion-at-threshold artifact alone does not justify a
source edit.

The geometry is **a routing candidate, not an orderable manufacturing release**.
`audit_art_candidate.py` inventories all 715 original selected copper/mask pair
findings by source hash, original polygon pair and closest points. Every one is
marked unresolved until a finished-union printability proof and local repair
ledger exist. The same diagnostic inventories 805 distinct finished-union mask
pairs and 175 copper pairs below the frozen 0.25 mm gap rule. Another 289 gold
components fail the necessary test of containing a 0.25 mm disk. This is a
failure screen, not a sufficient width proof; it does not test necks or webs
within one connected component. Copper joins, mask-web repairs and remaining
width repairs have not been implemented or exported to native project boards.
In particular, do not
use a Rev5 preview or the legacy
panel-home boards as proof of corrected CAM.

A straight 0.25 mm hidden copper join fits the safe region for 167 of the 175
pair findings. Eight Coral top pairs need a different local path or motif
adjustment. This is feasibility evidence only; no joins are emitted.

`repair_mask_candidate.py` builds `mask-repair-candidate.json` from the
manufacturing geometry. It keeps the 56 closed Kumiko apertures mask-colored,
removes indexed isolated gold fragments that cannot contain a 0.25 mm disk,
and applies indexed local one-sided retreats to clear distinct-component mask
gaps. Three measured Spider guide-to-web slivers instead use exactly four
indexed closing patches with no original black paint; the patches add
29.892211 mm² of gold and retain the web. It preserves the nine protected top
rim cores and stays within each 30% gold-loss budget. **This is not a mask
printability pass:** within-component width still needs indexed tip/neck
repairs on Coral, Fault and Kumiko plus full visual proof. Direct erosion of
Fault's artwork splits its main gold component, so it is only a diagnostic.
Copper joins and native board exports therefore remain pending.

Run the lightweight candidate checks with:

```sh
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/build_geometry.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/audit_art_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/repair_mask_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -v
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/rev5_gold.py
```

The next implementation must use the frozen decision's indexed local art
corrections, finished-union width/gap tests, visual comparisons, source hash
tracking, and deterministic native generation before these boards are called
selected production boards. Native load/DRC and CAM parsing remain issue #16.
