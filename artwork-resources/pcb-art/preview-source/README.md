# Revision 5 Geometry and Offline Viewer

This package generates the five layered PCB art designs from editable Python sources and renders their geometry in an offline three.js viewer.

The canonical geometry is assets/geometry.json. The generator reads the design modules under src/designs, shared geometry in src/build_common.py, finish policy in src/finish_policy.py, and the immutable Revision 3 comparison snapshot in assets/reference-revision3.json. Revision 4 geometry is retained in assets/reference-revision4.json for regression comparison. Do not replace either reference snapshot with regenerated output.

The selected design family contains 43 boards, using wide Kumiko. The complete standard Kumiko alternative adds nine records, for 52 board records total. It is an alternative to the wide set, not an additional production quantity. Revision 5 adds flat copper artwork to the top of each design and Kumiko variant; it preserves the approved Revision 4 physical outlines and lower-layer artwork.

## Build

From this directory:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    npm ci
    npm run build

The build regenerates assets/geometry.json and assets/validation.json, then writes seven self-contained HTML files under dist. It needs Shapely 2.1.2, Pillow 12.3.0, Node.js, and the locked npm dependencies. The HTML files are generated outputs and are ignored in this repository.

The smaller geometry-only command is:

    .venv/bin/python scripts/build_geometry.py

Do not treat geometry validation or a browser render as KiCad DRC, CAM review, a physical-fit check, or factory acceptance. See src/CONTRACT.md and the central PCB art README for the outstanding review boundary.

Image references from the incoming preview-source/docs directory are retained once under ../resources/images.
