# Four-series saved order candidates

Open the boards directly in KiCad PCB Editor, with their adjacent `.kicad_pro` files. No artifact download, Docker, or generation is needed to inspect this snapshot.

| Alternative | Direct PCB / preview / ZIP links | Purchase list | Order lines |
| --- | --- | --- | ---: |
| Individual: all 34 boards separate | [Open individual](OPEN-individual.md) | [ORDER](bundle/variants/individual/ORDER.md) | 34 |
| Grouped: red ten, 3 × 4 with two blank cells | [Open grouped](OPEN-grouped.md) | [ORDER](bundle/variants/grouped/ORDER.md) | 12 |
| Split-red: six plus four, no blank cells | [Open split-red](OPEN-split-red.md) | [ORDER](bundle/variants/split-red/ORDER.md) | 13 |

Coral Vault, Fault Line, Kumiko Void **wide**, and Spider Nest: 34 original boards, four standalone tops and 30 lowers. Strip Mine, Woven Maze and standard Kumiko are excluded. Groups match **both color and finish**; black ENIG and black lead-free HASL are separate. Purple/yellow/blue lowers remain standalone. The six-red sheet contains Spider L08, Coral L05/L07 and Kumiko L02/L05/L08; the four-red sheet contains Fault L02/L04/L06/L08.

Each alternative supplies 25 stacks per series. Choose **one** purchase list, never every ZIP in this directory. [Quote comparison](bundle/QUOTE-COMPARISON.md) · [Nominal stack sides](bundle/previews/nominal-stack-sides.png). Prices are unknown; local verification is not factory CAM/scoring approval or physical-fit confirmation. Existing FR-4, 1.6 mm, two copper layers, 1 oz, routing, scores and finish conditions are unchanged.

## Provenance and storage

- Original run: https://github.com/Takazudo/zudo-blanks/actions/runs/37833323671
- Tested source commit: `27481603195bb1318a0086d119294a5725dd36a0` (the tested PR merge, not the later main merge).
- [Original receipt](bundle/receipt.json), [original checksum inventory](bundle/SHA256SUMS), [retention mapping](retention.json).
- All 34 source boards/projects, both grouped native alternatives, order ZIPs, previews, settings and verification evidence remain in ordinary Git. No LFS or outer artifact ZIP.
- Original disposable KiCad local settings are encoded in the retention mapping, so opening a PCB does not modify tracked window settings. New local editor state and backups are ignored. Duplicate raw CAM bytes are restored from the unchanged order ZIPs for verification. `bundle/SHA256SUMS` describes the **restored full bundle**, not just the retained physical files. Every restored byte must match it. No native geometry or order ZIP is regenerated during retention.
- Stored bundle: 341,059,898 bytes in 601 files; original bundle: 522,195,553 bytes. Largest retained file: 52,841,655 bytes.

See [the storage/update procedure](../../../scripts/art-order/README.md#ordinary-git-storage) for verification and replacement. Treat this as a frozen snapshot until a newly verified bundle is explicitly retained and reviewed.
