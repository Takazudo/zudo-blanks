# PCB Art Source and Revision 5 Handoff

This directory contains the retained source, immutable revision references, compact review evidence, and regeneration tools for the five layered 20HP PCB art panels. The 52 original native board IDs are preserved in pcb/manifest.json and pcb/manifest.csv.

## Current four-series order files

[Open saved KiCad boards, CAM previews and order ZIPs](../../order-packages/four-art-series/current/README.md). This ordinary-Git snapshot preserves the three verified four-series alternatives from PR #24. The source/history below also includes Woven Maze and standard Kumiko; those are excluded from the saved four-series order lists.

## Panel homes

- panels/art-spider-nest contains the selected eight-board Spider Nest set.
- panels/art-coral-vault contains the selected eight-board Coral Vault set.
- panels/art-fault-line contains the selected nine-board Fault Line set.
- panels/art-kumiko-void contains the selected nine-board wide Kumiko set. Its alternatives/standard directory holds all nine standard Kumiko boards as a complete alternative.
- panels/art-woven-maze contains the selected nine-board Woven Maze set.

The default five-design set is 43 boards: 11 ENIG boards and 32 mask-only boards. The nine standard Kumiko boards are a replacement set, not an additional stack. Use the original board IDs from the manifest when referring to any layer.

## Retained source

- preview-source/src and preview-source/scripts generate the canonical Revision 5 geometry and offline 3D viewer.
- preview-source/assets/geometry.json is the current millimetre geometry input. reference-revision3.json and reference-revision4.json are immutable comparison inputs.
- resources/images, resources/reference, and resources/manufacturing-review retain the curated reference and review images once.
- resources/order retains the draft quantity and hardware inputs. Supplier quantities are blank.
- docs-overlay/src/content/docs retains the curated English documentation source. Its public directory is generated during a site migration and is not copied here.
- tools and validation retain the source and compact records needed for local review. The import and geometry-source checks are summarized in validation/import-review.md.
- SOURCE_RESOURCE_MANIFEST.json and SOURCE_SHA256SUMS.txt retain the incoming bundle inventory and checksums. IMPORT_MANIFEST.json maps all 944 listed source files to imported, transformed, deduplicated, or deliberately omitted repository paths.

The bundle checksum file had SHA-256 268e1c329f94d2fa55d3641e0ca32b8698e8117ac91bc8dadb58263f643d39d8. All 944 listed source files matched it at intake. Run python tools/verify_import.py to verify the committed mapping and files. The optional --source-root argument checks the original handoff tree when it is available.

## Regeneration

Python source generation uses Shapely 2.1.2. The preview source also declares Pillow 12.3.0 and npm dependencies in package-lock.json. From the repository root, create the preview environment and build the geometry and offline HTML:

    cd artwork-resources/pcb-art/preview-source
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    npm ci
    npm run build

To regenerate native boards and vector review outputs, run from the repository root and use a new generated destination:

    python3 artwork-resources/pcb-art/tools/export_kicad.py --input artwork-resources/pcb-art/preview-source/assets/geometry.json --output artwork-resources/pcb-art/generated/rev5-export

The exporter output is a review artifact. It does not replace the committed panel-home boards. Preview HTML, generated vectors, local dependency trees, and generated review output are ignored by Git. Regeneration commands and input hashes are recorded in the manifest and source guides.

The pinned geometry generator completed from the imported source tree. Its raw Kumiko ring ordering differs from the retained JSON, but all 52 serialized board-layer polygons compared geometrically equal. One derived aperture-count statistic changed from 33 to 32 on standard Kumiko layer 5. The imported canonical geometry and validation records were kept unchanged; see validation/import-review.md before treating a future regeneration as a byte-for-byte replacement.

## Review status

The incoming records describe geometry, S-expression, and independent data checks. This import did not run KiCad's native parser, DRC, or CAM. No factory acceptance, quote, physical-fit, or production-order claim is made. Those checks remain pending and must be recorded against the selected files and an actual fabrication process before ordering.

The viewer source includes its upstream three.js MIT notice in preview-source/THIRD_PARTY_NOTICES.txt. No additional standalone license file was present in the incoming bundle; the import manifest preserves provenance without adding a license claim.
