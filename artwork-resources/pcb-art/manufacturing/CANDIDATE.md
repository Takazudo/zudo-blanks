# Indexed manufacturing candidate (incomplete)

`build_geometry.py` reads the immutable Rev5 `preview-source/assets/geometry.json`
and frozen `policy.json`, then writes `manufacturing-geometry.json` and
`indexed-deltas.json`. It closes exactly the 56 selected Kumiko wide apertures,
applies the 1.0 mm cutter sweep to every remaining decorative aperture, and
moves the three specified Coral stack rims. The ledger indexes each changed
original hole and all specified top rim operations. Standard Kumiko remains an
unchanged, non-orderable alternative. The approved input and historical tests
are unaffected.

The geometry is **a routing candidate, not an orderable manufacturing release**.
`audit_art_candidate.py` inventories all 715 original selected copper/mask pair
findings by source hash, original polygon pair and closest points. Every one is
marked unresolved until a finished-union printability proof and local repair
ledger exist. The copper/mask artwork has not been repaired or exported to
native project boards. In particular, do not use a Rev5 preview or the legacy
panel-home boards as proof of corrected CAM.

Run the lightweight candidate checks with:

```sh
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/build_geometry.py
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/manufacturing/audit_art_candidate.py
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -v
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/rev5_gold.py
```

The next implementation must use the frozen decision's indexed local art
corrections, finished-union width/gap tests, visual comparisons, source hash
tracking, and deterministic native generation before these boards are called
selected production boards. Native load/DRC and CAM parsing remain issue #16.
