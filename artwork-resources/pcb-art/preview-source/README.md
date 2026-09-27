# Revision 5 Geometry and Offline Viewer

This package retains the five layered PCB art designs in editable Python sources and renders the frozen Revision 5 geometry in an offline three.js viewer.

The canonical geometry is assets/geometry.json. The generator reads the design modules under src/designs, shared geometry in src/build_common.py, finish policy in src/finish_policy.py, and the immutable Revision 3 comparison snapshot in assets/reference-revision3.json. Revision 4 geometry is retained in assets/reference-revision4.json for regression comparison. Do not replace either reference snapshot with regenerated output.

The selected design family contains 43 boards, using wide Kumiko. The complete standard Kumiko alternative adds nine records, for 52 board records total. It is an alternative to the wide set, not an additional production quantity. Revision 5 adds flat copper artwork to the top of each design and Kumiko variant; it preserves the approved Revision 4 physical outlines and lower-layer artwork.

## Build

From this directory:

    npm ci
    npm run build

The viewer build verifies the approved SHA256 of `assets/geometry.json`, leaves frozen geometry and validation untouched, then writes seven self-contained HTML files under ignored `dist/`. It needs Node.js and the locked npm dependencies. The documentation site stages only `dist/index.html`: URL query parameters select each design and Kumiko variant without publishing six duplicate copies.

Regenerating design geometry is a separate, intentional source change. It needs Shapely 2.1.2 and Pillow 12.3.0:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python scripts/build_geometry.py

Do not replace the frozen geometry merely to refresh the viewer. A geometry change requires a reviewed policy update and fresh native/CAM comparisons.

Do not treat geometry validation or a browser render as KiCad DRC, CAM review, a physical-fit check, or factory acceptance. The selected native and grouped board local checks are recorded under `../manufacturing/`; factory CAM, quote and physical fit remain pending.

Image references from the incoming preview-source/docs directory are retained once under ../resources/images.
