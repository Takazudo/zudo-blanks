# Source Import Review

Verified on 2026-09-25 from the repository copy of the Revision 5 source.

## Intake and mapping

The original SHA256SUMS.txt digest is 268e1c329f94d2fa55d3641e0ca32b8698e8117ac91bc8dadb58263f643d39d8. All 944 listed source hashes matched at intake. The local verifier checks each source entry against the archived bundle inventory, checks mapped repository-file hashes, and validates the panel paths and board metadata. With the original source root available, it also compares all 944 files and the original PCB manifest metadata. Without it, the committed source inventory and destination hashes are sufficient for a local check.

## Geometry generator

From artwork-resources/pcb-art/preview-source, the command .venv/bin/python scripts/build_geometry.py completed using Python 3.14.7, Shapely 2.1.2, and GEOS 3.13.1. The retained geometry.json SHA-256 is 00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e; the generated serialization was 33517961687d0e547c8cb4a3b789baeadc6572dd9398afe2ad1a4aa6c1ef4c89.

All 52 selected and alternative board-layer polygon sets were geometrically equivalent to the retained Revision 5 geometry after normalizing ring order. The generated JSON used a different Kumiko ring order, and one derived aperture-count statistic for standard Kumiko layer 5 changed from 33 to 32.

The retained validation.json SHA-256 is 74984119e23222186b693161df7038be9fa5fdb8313dfef05c81ae3d43f49ff2. Both imported geometry.json and validation.json were restored after comparing generated outputs, so their handoff checksums remain unchanged. Keep the imported canonical data and immutable Revision 3 and Revision 4 references intact when reviewing a future source regeneration.

## Manufacturing review boundary

This check covered source intake, geometry generation, and import paths. It did not run the native KiCad parser, DRC, Gerber/drill export, CAM viewer, supplier review, quote, order, or physical-fit check. No factory-acceptance claim is made.
