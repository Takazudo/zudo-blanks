# PCB Art Source and Revision 5 Handoff

This directory contains the retained source, immutable revision references, compact review evidence, and regeneration tools for the five layered 20HP PCB art panels. The 52 original native board IDs are preserved in pcb/manifest.json and pcb/manifest.csv.

## Completed four-series order

[Open the completed four-series order](../../order-packages/four-art-series/ordered/README.md). The owner reported completion on 2026-10-10 JST: compact grouped lowers with red6+4, 25 stacks per series, 13 lines each quantity 25. Exact fabrication bytes from PR #24 / storage PR #26 remain in ordinary Git; abandoned candidate exports were removed. The source/history below also includes Woven Maze and standard Kumiko, outside the completed order.

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
- [`doc/src/content/docs`](../../doc/src/content/docs) is the maintained English documentation source. All 28 former overlay pages were reconciled into it; [`doc/data/route-migration.json`](../../doc/data/route-migration.json) records each destination and disposition. The duplicate overlay configuration and bootstrap/check scripts are retired.
- tools and validation retain the source and compact records needed for local review. The import and geometry-source checks are summarized in validation/import-review.md.
- SOURCE_RESOURCE_MANIFEST.json and SOURCE_SHA256SUMS.txt retain the incoming bundle inventory and checksums. IMPORT_MANIFEST.json maps all 944 listed source files to imported, transformed, deduplicated, or deliberately omitted repository paths.

The bundle checksum file had SHA-256 268e1c329f94d2fa55d3641e0ca32b8698e8117ac91bc8dadb58263f643d39d8. All 944 listed source files matched it at intake. The original intake verifier applies to the import snapshot, not the evolving working tree; see the verification boundary below. Its optional `--source-root` argument checks the original handoff tree when available.

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

## Review status and historical boundaries

The incoming records describe the original geometry, S-expression and independent data checks. Later manufacturing work recorded native KiCad 10 DRC/CAM and grouped-sheet checks. The completed four-series archive above records the owner's completion report and last verified quote, not a receipt or supplier acceptance. Strip Mine has separate owner-reported physical assembly experience; assembly results for the four newer series remain unrecorded. Keep each historical record's original scope separate from the newer order evidence.

The viewer source includes its upstream three.js MIT notice in preview-source/THIRD_PARTY_NOTICES.txt. No additional standalone license file was present in the incoming bundle; the import manifest preserves provenance without adding a license claim.

## Verify the appropriate boundary

`tools/verify_import.py` is a historical intake verifier. It compares the original mapped documentation, tools and boards against their intake hashes. The parent commit `f31c49d3cad0364033c18d4f91d07139ea4872f5` already differs from that snapshot (the central README is one verified mismatch); current documentation edits and the retired overlay also intentionally differ. A current-tree import-verifier failure is not reported as a pass, and the original import manifest/checksums remain unchanged.

To inspect the intake snapshot without changing the active checkout, use a detached disposable worktree at the original import commit:

```sh
git worktree add --detach /tmp/zudo-blanks-import-check b3e3f35b658bba2bad0400c1ee94b511857d5484
python3 /tmp/zudo-blanks-import-check/artwork-resources/pcb-art/tools/verify_import.py
```

The verifier reads that snapshot; it does not regenerate native boards or CAM. The completed order instead uses the independent `manufacturing/verify_ordered.py` with the setup in [`scripts/art-order/README.md`](../../scripts/art-order/README.md). Current documentation checks cover the recursive panel inventory and SHA256 metadata, generated page drift, local assets, links and frozen viewer geometry. These checks have different scopes; no one result implies supplier approval or physical assembly.
